"""Canvas allows bulk assignment submission downloading, but does not provide any control over file naming. This
script downloads an assignment's submissions and names them according to the submitter's Login ID (typically their
institutional student number) or group name."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-08-03'  # ISO 8601 (YYYY-MM-DD)

import argparse
import csv
import datetime
import functools
import json
import os
import re
import sys

import openpyxl.utils
import requests

from canvashelpers import Args, Config, Utils


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs=1,
                        help='Please provide the URL of the assignment to download submissions for. Files will be '
                             'saved in a folder named [assignment ID] (see the `--working-directory` option to '
                             'configure this)')
    parser.add_argument('--working-directory', default=None,
                        help='The location to use for output (which will be created if it does not exist). Default: '
                             'the same directory as this script')
    parser.add_argument('--speedgrader-file', default=None, choices=['XLSX', 'CSV'], type=str.upper,
                        help='Set this option to `XLSX` or `CSV` to create a file in the specified format containing '
                             'students\' (or groups\') names, IDs (both Canvas and institutional) and a link to the '
                             'SpeedGrader page for the assignment, which is useful when marking activities such as '
                             'presentations or ad hoc tasks. No attachments are downloaded in this mode')
    parser.add_argument('--submitter-pattern', default=None,
                        help='Use this option to pass a (case-insensitive) regular expression pattern that will be '
                             'used to filter and select only submitters whose names *or* student numbers match. For '
                             'example, `^Matt(?:hew)?\\w*` will match only students whose first name is `Matt` or '
                             '`Matthew`, whereas `^123\\d{3}$` will match six–digit student numbers starting with '
                             '`123`. In groups mode this pattern is used to match *group names* only')
    parser.add_argument('--multiple-attachments', action='store_true',
                        help='Use this option if there are multiple assignment attachments per student or group. This '
                             'will change the behaviour of the script so that a new subfolder is created for each '
                             'submission, named as the student\'s number or the group\'s name. The original filename '
                             'will be used for each attachment that is downloaded. Without this option, any additional '
                             'attachments will be ignored, and only the first file found will be downloaded')
    return parser.parse_args()


args = Args.interactive(get_args)
ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
ASSIGNMENT_ID = Utils.get_assignment_id(ASSIGNMENT_URL)  # used only for output directory
working_directory = os.path.dirname(
    os.path.realpath(__file__)) if args.working_directory is None else args.working_directory
os.makedirs(working_directory, exist_ok=True)
OUTPUT_DIRECTORY = '%s/%d' % (working_directory, ASSIGNMENT_ID)
if os.path.exists(OUTPUT_DIRECTORY):
    print('ERROR: assignment output directory', OUTPUT_DIRECTORY, 'already exists - please remove or rename')
    sys.exit()
os.mkdir(OUTPUT_DIRECTORY)

assignment_details_response = requests.get(ASSIGNMENT_URL, headers=Utils.canvas_api_headers())
if assignment_details_response.status_code != 200:
    print('ERROR: unable to get assignment details - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    sys.exit()
GROUP_ASSIGNMENT = True if assignment_details_response.json()['group_category_id'] else False
print('Retrieved assignment details - group assignment:', GROUP_ASSIGNMENT)

speedgrader_file = None
speedgrader_output = []
if args.speedgrader_file and args.speedgrader_file.lower() in ['xlsx', 'csv']:
    speedgrader_file = '%s/speedgrader.%s' % (OUTPUT_DIRECTORY, args.speedgrader_file.lower())
    print('Creating a course roster file with SpeedGrader links from', args.url[0], 'at', speedgrader_file)
else:
    output_format = '[student number].[uploaded file extension]'
    if GROUP_ASSIGNMENT:
        output_format = '[group name].[uploaded file extension]'
    if args.multiple_attachments:
        output_format = '[group name]/[original uploaded filename]'
    print('Downloading all submission documents from', args.url[0], 'named as', output_format, 'to', OUTPUT_DIRECTORY)

submission_list_response = Utils.get_assignment_submissions(ASSIGNMENT_URL)
if not submission_list_response:
    print('ERROR: unable to retrieve submission list - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    sys.exit()

submission_list_json = json.loads(submission_list_response)
filtered_submission_list = Utils.filter_assignment_submissions(ASSIGNMENT_URL, submission_list_json,
                                                               groups_mode=GROUP_ASSIGNMENT, sort_entries=True)


def compare_attachment_dates(a1, a2):
    a1_created = int(datetime.datetime.fromisoformat(a1['created_at'].replace('Z', '+00:00')).timestamp())
    a2_created = int(datetime.datetime.fromisoformat(a2['created_at'].replace('Z', '+00:00')).timestamp())
    return a2_created - a1_created  # sort in descending order of creation date


def filter_matched_submissions(single_submission):
    submitter_details = Utils.get_submitter_details(ASSIGNMENT_URL, single_submission, groups_mode=GROUP_ASSIGNMENT)
    if GROUP_ASSIGNMENT:
        return submitter_matcher.match(submitter_details['group_name'])
    return submitter_matcher.match(submitter_details['student_number']) or submitter_matcher.match(
        submitter_details['student_name'])


submitter_matcher = None
if args.submitter_pattern:
    submitter_matcher = re.compile(args.submitter_pattern, flags=re.IGNORECASE)
    matched_submissions = list(filter(filter_matched_submissions, filtered_submission_list))
    print('Filtered', len(filtered_submission_list), 'valid submissions using pattern "%s"' % args.submitter_pattern,
          '-', len(matched_submissions), 'valid submissions remaining')
    filtered_submission_list = matched_submissions

download_count = 0
download_total = len(filtered_submission_list)
for submission in filtered_submission_list:
    download_count += 1
    submitter = Utils.get_submitter_details(ASSIGNMENT_URL, submission, groups_mode=GROUP_ASSIGNMENT)
    if not submitter:
        print('ERROR: submitter details not found for submission; skipping:', submission)
        continue

    if speedgrader_file:
        speedgrader_link = Utils.course_url_to_speedgrader(args.url[0], submitter['canvas_user_id'])
        if speedgrader_file.endswith('xlsx'):
            speedgrader_link = '=hyperlink("%s")' % speedgrader_link
        if GROUP_ASSIGNMENT:
            speedgrader_output.append([submitter['group_name'], submitter['canvas_group_id'], speedgrader_link])
        else:
            speedgrader_output.append(
                [submitter['student_number'], submitter['student_name'], submitter['canvas_user_id'], speedgrader_link])
        continue

    if 'attachments' in submission:
        submission_output_directory = OUTPUT_DIRECTORY
        if args.multiple_attachments:
            submission_output_directory = os.path.join(
                OUTPUT_DIRECTORY, submitter['group_name' if GROUP_ASSIGNMENT else 'student_number'])
            if os.path.exists(submission_output_directory):
                print('ERROR: output directory', submission_output_directory,
                      'already exists - please remove or rename the root assignment output folder')
                sys.exit()
            os.mkdir(submission_output_directory)

        submission_documents = submission['attachments']
        submission_documents.sort(key=functools.cmp_to_key(compare_attachment_dates))  # newest attachment is now first
        for document in submission_documents:
            file_download_response = requests.get(document['url'])
            if file_download_response.status_code == 200:
                if args.multiple_attachments:
                    output_filename = os.path.join(submission_output_directory, document['filename'])
                else:
                    output_filename = os.path.join(submission_output_directory, '%s.%s' % (
                        submitter['group_name' if GROUP_ASSIGNMENT else 'student_number'],
                        document['filename'].split('.')[-1].lower()))

                with open(output_filename, 'wb') as output_file:
                    output_file.write(file_download_response.content)
                late_status = ' (LATE: %d seconds)' % submission['seconds_late'] if submission['late'] else ''
                print('Saved %s[truncated] as %s (%d of %d)%s' % (document['url'].split('download?')[0],
                                                                  output_filename.replace(OUTPUT_DIRECTORY, '')[1:],
                                                                  download_count, download_total, late_status))

            else:
                print('ERROR: download failed for submission from', submitter, 'at', document['url'], '- aborting')
                break  # TODO: try next attachment instead? (if one exists)

            if len(submission_documents) > 1 and not args.multiple_attachments:
                print('WARNING: ignoring all attachments after the newest item for submission from', submitter,
                      '- did you mean to enable --multiple-attachments mode?')
                break
    else:
        print('ERROR: unable to locate attachment for submission from', submitter, '- skipping')

if speedgrader_file:
    if GROUP_ASSIGNMENT:
        spreadsheet_headers = ['Group name', 'Canvas group ID', 'Speedgrader link']
    else:
        spreadsheet_headers = ['Student number', 'Student name', 'Canvas user ID', 'Speedgrader link']

    if speedgrader_file.endswith('xlsx'):
        workbook = openpyxl.Workbook()
        spreadsheet = workbook.active
        spreadsheet.title = 'Course roster (%d)' % ASSIGNMENT_ID
        spreadsheet.freeze_panes = 'A2'  # set the first row as a header
        spreadsheet.append(spreadsheet_headers)
        for row in speedgrader_output:
            spreadsheet.append(row)
        workbook.save(speedgrader_file)

    elif speedgrader_file.endswith('csv'):
        with open(speedgrader_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(spreadsheet_headers)
            writer.writerows(speedgrader_output)
