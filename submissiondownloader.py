"""Canvas allows bulk assignment submission downloading, but does not provide any control over file naming. This
script downloads an assignment's submissions and names them according to the submitter's Login ID (typically their
institutional student number) or group name."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-02-21'  # ISO 8601 (YYYY-MM-DD)

import argparse
import csv
import json
import os

import openpyxl.utils
import requests

from canvashelpers import Config, Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please pass the URL of the assignment to download submissions for. Files will be saved in a '
                         'folder named [assignment ID] (see the `--working-directory` option to configure this)')
parser.add_argument('--working-directory', default=None,
                    help='The location to use for output (which will be created if it does not exist). '
                         'Default: the same directory as this script')
parser.add_argument('--speedgrader-file', default=None,
                    help='Set this option to `XLSX` or `CSV` to create a file in the specified format containing '
                         'students\' (or groups\') names, IDs (both Canvas and institutional) and a link to the '
                         'SpeedGrader page for the assignment, which is useful when marking activities such as '
                         'presentations or ad hoc tasks. No attachments are downloaded in this mode')
parser.add_argument('--groups', action='store_true', help='Use this option if the assignment is completed in groups')
parser.add_argument('--multiple-attachments', action='store_true',
                    help='Use this option if there are multiple assignment attachments per student or group. This '
                         'will change the behaviour of the script so that a new subfolder is created for each '
                         'submission, named as the student\'s number or the group\'s name. The original filename '
                         'will be used for each attachment that is downloaded. Without this option, any additional '
                         'attachments will be ignored, and only the first file found will be downloaded')
args = parser.parse_args()  # exits if no assignment URL is provided

ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
ASSIGNMENT_ID = Utils.get_assignment_id(ASSIGNMENT_URL)  # used only for output directory
working_directory = os.path.dirname(
    os.path.realpath(__file__)) if args.working_directory is None else args.working_directory
os.makedirs(working_directory, exist_ok=True)
OUTPUT_DIRECTORY = '%s/%d' % (working_directory, ASSIGNMENT_ID)
if os.path.exists(OUTPUT_DIRECTORY):
    print('ERROR: assignment output directory', OUTPUT_DIRECTORY, 'already exists - please remove or rename')
    exit()
os.mkdir(OUTPUT_DIRECTORY)

speedgrader_file = None
speedgrader_output = []
if args.speedgrader_file and args.speedgrader_file.lower() in ['xlsx', 'csv']:
    speedgrader_file = '%s/speedgrader.%s' % (OUTPUT_DIRECTORY, args.speedgrader_file.lower())
    print('Creating a course roster file with SpeedGrader links from', args.url[0], 'at', speedgrader_file)
else:
    output_format = '[student number].[uploaded file extension]'
    if args.groups:
        output_format = '[group name].[uploaded file extension]'
    if args.multiple_attachments:
        output_format = '[group name]/[original uploaded filename]'
    print('Downloading all submission documents from', args.url[0], 'named as', output_format, 'to', OUTPUT_DIRECTORY)

submission_list_response = Utils.get_assignment_submissions(ASSIGNMENT_URL)
if not submission_list_response:
    print('ERROR: unable to retrieve submission list - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    exit()

submission_list_json = json.loads(submission_list_response)
filtered_submission_list = Utils.filter_assignment_submissions(submission_list_json, groups_mode=args.groups,
                                                               sort_entries=True)

for submission in filtered_submission_list:
    submitter = Utils.get_submitter_details(submission, groups_mode=args.groups)
    if not submitter:
        print('ERROR: submitter details not found for submission; skipping:', submission)
        continue

    if speedgrader_file:
        speedgrader_link = Utils.course_url_to_speedgrader(args.url[0], submitter['canvas_user_id'])
        if speedgrader_file.endswith('xlsx'):
            speedgrader_link = '=hyperlink("%s")' % speedgrader_link
        if args.groups:
            speedgrader_output.append([submitter['group_name'], submitter['canvas_group_id'], speedgrader_link])
        else:
            speedgrader_output.append(
                [submitter['student_number'], submitter['student_name'], submitter['canvas_user_id'], speedgrader_link])
        continue

    if 'attachments' in submission:
        submission_output_directory = OUTPUT_DIRECTORY
        if args.multiple_attachments:
            submission_output_directory = os.path.join(
                OUTPUT_DIRECTORY, submitter['group_name' if args.groups else 'student_number'])
            if os.path.exists(submission_output_directory):
                print('ERROR: output directory', submission_output_directory,
                      'already exists - please remove or rename the root assignment output folder')
                exit()
            os.mkdir(submission_output_directory)

        submission_documents = submission['attachments']
        for document in submission_documents:
            file_download_response = requests.get(document['url'])
            if file_download_response.status_code == 200:
                if args.multiple_attachments:
                    output_filename = os.path.join(submission_output_directory, document['filename'])
                else:
                    output_filename = os.path.join(submission_output_directory, '%s.%s' % (
                        submitter['group_name' if args.groups else 'student_number'],
                        document['filename'].split('.')[-1]))

                with open(output_filename, 'wb') as output_file:
                    output_file.write(file_download_response.content)
                print('Saved %s as %s' % (document['url'], output_filename.replace(OUTPUT_DIRECTORY + '/', '')))

            else:
                print('ERROR: download failed for submission from', submitter, 'at', document['url'], '; aborting')
                break  # TODO: try next attachment instead? (if one exists)

            if len(submission_documents) > 1 and not args.multiple_attachments:
                print('WARNING: ignoring all attachments after the first item for submission from', submitter,
                      '- did you mean to enable --multiple-attachments mode?')
                break
    else:
        print('ERROR: unable to locate attachment for submission from', submitter, '- skipping')

if speedgrader_file:
    if args.groups:
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
