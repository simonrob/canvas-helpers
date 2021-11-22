import argparse
import json
import os

import requests

from canvashelpers import Config, Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please pass the URL of the assignment to download submissions for')
args = parser.parse_args()  # exits if no assignment URL is provided

ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
ASSIGNMENT_ID = ASSIGNMENT_URL.split('/')[-1]  # used only for output directory
OUTPUT_DIRECTORY = '%s/%s' % (os.path.dirname(os.path.realpath(__file__)), ASSIGNMENT_ID)
if os.path.exists(OUTPUT_DIRECTORY):
    print('ERROR: output directory', OUTPUT_DIRECTORY, 'already exists - please remove or rename')
    exit()
os.mkdir(OUTPUT_DIRECTORY)
print('Downloading all submission documents from', args.url[0],
      'named as [student number].[file extension] and saved to', OUTPUT_DIRECTORY)

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

for submission in submission_list_json:
    if 'workflow_state' in submission and submission['workflow_state'] != 'unsubmitted' and 'attachments' in submission:
        student_details = [s for s in submission_student_map if s['user_id'] == submission['user_id']]
        if len(student_details) == 1:
            student_details = student_details[0]
            submission_documents = submission['attachments']
            for document in submission_documents:
                file_download_response = requests.get(document['url'])
                if submission_list_response.status_code == 200:
                    extension = document['filename'].split('.')[-1]
                    with open('%s/%s.%s' % (OUTPUT_DIRECTORY, student_details['student_number'], extension),
                              'wb') as output_file:
                        output_file.write(file_download_response.content)
                    print('Saved %s as %s.%s' % (document['url'], student_details['student_number'], extension))
                else:
                    print('ERROR: download failed for submission from student', student_details, 'at', document['url'])

                if len(submission_documents) > 1:
                    print('WARNING: ignoring all attachments after the first item for student', student_details)
                    break
        else:
            print('ERROR: unable to locate student details for submission from user', submission['user_id'],
                  '- skipping')
