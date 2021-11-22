import argparse
import json
import mimetypes
import os

import openpyxl
import requests

from canvashelpers import Config, Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please pass the URL of the assignment to upload bulk feedback attachments for')
parser.add_argument('--attachment-extension', default='pdf',
                    help='The file extension of the attachments to upload (without the dot separator). These files '
                         'should be placed in the same directory as the script, named following the format '
                         '[student number].[extension]. Default: \'pdf\'')
parser.add_argument('--marks-file', default=None,
                    help='An XLSX file containing a minimum of two columns: student number and mark. A third column '
                         'can be added for per-student feedback that will be added as a text comment, overriding the '
                         'global attachment comment')
parser.add_argument('--attachment-comment', default='See attached file',
                    help='The comment to add when attaching the feedback file. Overridden by any individual comments '
                         'in the imported marks file. Default: \'See attached file\'')
parser.add_argument('--dry-run', action='store_true',
                    help='Preview the script\'s actions without actually making any changes')
args = parser.parse_args()  # exits if no assignment URL is provided

ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
print('%sUploading %s assignment feedback attachments to assignment %s with comment \'%s\'' % (
    'DRY RUN: ' if args.dry_run else '', args.attachment_extension.upper(), args.url[0], args.attachment_comment))

marks_map = {}
if args.marks_file is not None:
    marks_file = '%s/%s' % (os.path.dirname(os.path.realpath(__file__)), args.marks_file)
    if os.path.exists(marks_file):
        marks_workbook = openpyxl.load_workbook(args.marks_file)
        marks_sheet = marks_workbook[marks_workbook.sheetnames[0]]
        for row in marks_sheet.iter_rows():
            if type(row[1].value) is int:  # ultra-simplistic check to avoid any header rows: check mark is an integer
                student_number = str(row[0].value)
                marks_map[student_number] = {'mark': row[1].value}
                if len(row) > 2:  # individual comment is optional
                    marks_map[student_number]['comment'] = row[2].value
        print('Loaded marks/feedback mapping for', len(marks_map), 'submissions:', marks_map)
    else:
        print('Ignoring marks file argument', args.marks_file, '- not found in current directory at', marks_file)

submission_list_response = Utils.get_assignment_submissions(ASSIGNMENT_URL)
if submission_list_response.status_code != 200:
    print('Error in submission list retrieval - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    exit()

submission_list_json = json.loads(submission_list_response.text)
submission_user_ids = []
for submission in submission_list_json:
    if 'workflow_state' in submission and submission['workflow_state'] != 'unsubmitted':
        submission_user_ids.append(submission['user_id'])
    else:
        pass  # no submission (or test student)
print('Loaded', len(submission_user_ids), 'submission user IDs:', submission_user_ids)

submission_student_map = Utils.get_assignment_student_list(ASSIGNMENT_URL, submission_user_ids)
print('Mapped', len(submission_student_map), 'student numbers to submission IDs:', submission_student_map)

for user in submission_student_map:
    print('\nProcessing submission from', user)
    user_submission_url = '%s/submissions/%d' % (ASSIGNMENT_URL, user['user_id'])

    attachment_file = '%s.%s' % (user['student_number'], args.attachment_extension)
    attachment_path = '%s/%s' % (os.path.dirname(os.path.realpath(__file__)), attachment_file)
    attachment_mime_type = mimetypes.guess_type(attachment_path)[0]

    if os.path.exists(attachment_path) and attachment_mime_type is not None:
        print('Found submission attachment file', attachment_file, 'type', attachment_mime_type)
    else:
        print('Attachment %s at %s not found (or has unrecognised MIME type: %s); skipping attachment upload for this '
              'submission' % (attachment_file, attachment_path, attachment_mime_type))
        attachment_file = None

    attachment_comment = args.attachment_comment
    attachment_mark = None
    if user['student_number'] in marks_map:
        attachment_mark = marks_map[user['student_number']]['mark']
        if 'comment' in marks_map[user['student_number']]:
            attachment_comment = marks_map[user['student_number']]['comment']
    elif attachment_file is None:
        print('Could not find attachment, mark or comment for submission (at least one item is required); skipping')
        continue

    if args.dry_run:
        summary = 'post comment: \'%s\'' % attachment_comment
        if user['student_number'] in marks_map:
            summary = 'set mark to %d and %s' % (marks_map[user['student_number']]['mark'], summary)
        if attachment_file is not None:
            summary = 'upload file %s and %s' % (attachment_file, summary)
        print('DRY RUN: Student %s – would %s' % (user['student_number'], summary))
        continue

    # TODO: test with group submissions (e.g., 'comment[group_comment]': True)
    comment_association_data = {'comment[text_comment]': attachment_comment}

    if attachment_mark:
        print('Adding submission mark/comment from spreadsheet:', attachment_mark, ' / ', attachment_comment)
        comment_association_data['submission[posted_grade]'] = attachment_mark

    if attachment_file is not None:
        submission_form_data = {'name': attachment_file, 'content_type': attachment_mime_type}
        file_submission_url_response = requests.post('%s/comments/files' % user_submission_url,
                                                     data=submission_form_data, headers=Utils.canvas_api_headers())
        if file_submission_url_response.status_code != 200:
            print('\tERROR: unable to retrieve attachment upload URL; skipping submission')
            continue

        file_submission_url_json = json.loads(file_submission_url_response.text)
        print('\tUploading feedback attachment to', file_submission_url_json['upload_url'].split('?')[0], '[truncated]')

        files_data = {'file': (attachment_file, open(attachment_path, 'rb'))}
        file_submission_upload_response = requests.post(file_submission_url_json['upload_url'],
                                                        data=submission_form_data, files=files_data,
                                                        headers=Utils.canvas_api_headers())

        if file_submission_upload_response.status_code != 201:  # note: 201 Created
            print('\tERROR: unable to upload attachment file; skipping submission')
            continue

        file_submission_upload_json = json.loads(file_submission_upload_response.text)
        print('\tAssociating uploaded file', file_submission_upload_json['id'], 'with new attachment comment')
        comment_association_data['comment[file_ids][]'] = file_submission_upload_json['id']

    comment_association_response = requests.put(user_submission_url,
                                                data=comment_association_data,
                                                headers=Utils.canvas_api_headers())
    if comment_association_response.status_code != 200:
        print('\tERROR: unable to add assignment mark/comment and associate attachment; skipping submission')
        continue

    print('\tFeedback created and associated successfully at', user_submission_url)
