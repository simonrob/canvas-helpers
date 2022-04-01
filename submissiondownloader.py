"""Canvas allows bulk assignment submission downloading, but does not provide any control over file naming. This
script downloads an assignment's submissions and names them according to the submitter's Login ID (typically their
institutional student number) or group name."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2022 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2022-04-01'  # ISO 8601 (YYYY-MM-DD)

import argparse
import json
import os

import requests

from canvashelpers import Config, Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1, help='Please pass the URL of the assignment to download submissions for')
parser.add_argument('--groups', action='store_true', help='Use this option if the assignment is completed in groups')
parser.add_argument('--multiple-attachments', action='store_true',
                    help='Use this option if there are multiple assignment attachments per student or group. This '
                         'will change the behaviour of the script so that a new subfolder is created for each '
                         'submission, named as the student\'s number or the group\'s name. The original filename '
                         'will be used for each attachment that is downloaded')
args = parser.parse_args()  # exits if no assignment URL is provided

ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
ASSIGNMENT_ID = ASSIGNMENT_URL.split('/')[-1]  # used only for output directory
OUTPUT_DIRECTORY = '%s/%s' % (os.path.dirname(os.path.realpath(__file__)), ASSIGNMENT_ID)
if os.path.exists(OUTPUT_DIRECTORY):
    print('ERROR: assignment output directory', OUTPUT_DIRECTORY, 'already exists - please remove or rename')
    exit()
os.mkdir(OUTPUT_DIRECTORY)
output_format = '[student number].[uploaded file extension]'
if args.groups:
    output_format = '[group name].[uploaded file extension]'
if args.multiple_attachments:
    output_format = '[group name]/[original uploaded filename]'
print('Downloading all submission documents from', args.url[0], 'named as', output_format, 'to', OUTPUT_DIRECTORY)

submission_list_response = Utils.get_assignment_submissions(ASSIGNMENT_URL)
if not submission_list_response:
    print('Error in submission list retrieval - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    exit()

submission_list_json = json.loads(submission_list_response)

filtered_submission_list = Utils.filter_assignment_submissions(submission_list_json, args.groups)

for submission in filtered_submission_list:
    submitter = Utils.get_submitter_details(submission, args.groups)
    if not submitter:
        print('ERROR: submitter details not found for submission; skipping:', submission)
        continue

    if 'attachments' in submission:
        submission_output_directory = OUTPUT_DIRECTORY
        if args.multiple_attachments:
            submission_output_directory = '%s/%s' % (
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
                    output_filename = '%s/%s' % (submission_output_directory, document['filename'])
                else:
                    output_filename = '%s/%s.%s' % (
                        submission_output_directory, submitter['group_name' if args.groups else 'student_number'],
                        document['filename'].split('.')[-1])

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
