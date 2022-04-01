"""Instructure recently enforced a switch from "Classic Quizzes" to "New Quizzes". The new version has far fewer
features (see comparison: https://docs.google.com/document/d/11nSS2EP0UpSM6dcuEFnoF-hC6lyqWbE9JSHELNmfG2A/) and is
far harder to use for some tasks that were previously simple, but there seems to be little interest in improving it
(see repeated forum complaints). Critically, it is not possible to export responses in bulk, meaning that tasks which
previously took minutes can now take hours for larger class sizes. This script uses the Canvas API to work around that
limitation, exporting all responses to a single spreadsheet."""

import argparse
import json
import re

import openpyxl.utils
import requests.structures

from canvashelpers import Config, Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please pass the URL of the assignment to retrieve quiz responses for. Output will be saved '
                         'as [assignment ID].xlsx')
args = parser.parse_args()  # exits if no assignment URL is provided

config_settings = Config.get_settings()
LTI_INSTITUTION_SUBDOMAIN = config_settings['lti_institution_subdomain']
LTI_BEARER_TOKEN = config_settings['lti_bearer_token']
ROOT_INSTRUCTURE_DOMAIN = 'https://%s.quiz-%s-dub-prod.instructure.com/api'
LTI_API_ROOT = ROOT_INSTRUCTURE_DOMAIN % (LTI_INSTITUTION_SUBDOMAIN, 'lti')
QUIZ_API_ROOT = ROOT_INSTRUCTURE_DOMAIN % (LTI_INSTITUTION_SUBDOMAIN, 'api')

ASSIGNMENT_URL = Utils.course_url_to_api(args.url[0])
ASSIGNMENT_ID = ASSIGNMENT_URL.split('/')[-1]  # used only for output spreadsheet title and filename
OUTPUT_FILE = '%s.xlsx' % ASSIGNMENT_ID
print('Exporting quiz results from assignment', args.url[0], 'to', OUTPUT_FILE)

HTML_REGEX = re.compile('<.*?>')  # used to filter out HTML formatting from retrieved responses

# TODO: add CSV export as an alternative
workbook = openpyxl.Workbook()
spreadsheet = workbook.active
spreadsheet.title = 'Quiz results (%s)' % ASSIGNMENT_ID
spreadsheet.freeze_panes = 'A2'  # set the first row as a header
spreadsheet_headers = ['Student number', 'Student name']
spreadsheet_headers_set = False
spreadsheet_row = 2  # 1-indexed; row 1 = headers

submission_list_response = Utils.get_assignment_submissions(ASSIGNMENT_URL)
if not submission_list_response:
    print('Error in submission list retrieval - did you set a valid Canvas API token in %s?' % Config.FILE_PATH)
    exit()

submission_list_json = json.loads(submission_list_response)
user_session_ids = []
for submission in submission_list_json:
    if 'external_tool_url' in submission:
        user_session_ids.append({'user_id': submission['user_id'],
                                 'link': submission['external_tool_url'].split('participant_session_id=')[1].split('&')[
                                     0]})
    else:
        pass  # normally a test student
print('Loaded', len(user_session_ids), 'submission IDs:', user_session_ids)

student_number_map = Utils.get_assignment_student_list(ASSIGNMENT_URL)
print('Loaded', len(student_number_map), 'student number mappings:', student_number_map)

token_headers = requests.structures.CaseInsensitiveDict()
token_headers['accept'] = 'application/json'
token_headers['authorization'] = ('%s' if 'Bearer ' in LTI_BEARER_TOKEN else 'Bearer %s') % \
                                 LTI_BEARER_TOKEN  # in case the heading 'Bearer ' is copied as well as the token itself

for user_session_id in user_session_ids:
    print('Requesting quiz sessions for participant', user_session_id)
    token_response = requests.get('%s/participant_sessions/%s/grade' % (LTI_API_ROOT, user_session_id['link']),
                                  headers=token_headers)
    if token_response.status_code != 200:
        # TODO: there doesn't seem to be an API to get this token, but is there a better alternative to the current way?
        print('Error in quiz session retrieval - did you set a valid browser Bearer token in %s?' % Config.FILE_PATH)
        exit()

    # first we get a per-submission access token
    attempt_json = json.loads(token_response.text)
    quiz_session_headers = requests.structures.CaseInsensitiveDict()
    quiz_session_headers['accept'] = 'application/json'
    quiz_session_headers['authorization'] = attempt_json['token']
    quiz_session_id = attempt_json['quiz_api_quiz_session_id']
    print('Loaded quiz session', quiz_session_id)

    # then a summary of the submission session and assignment overview
    submission_response = requests.get('%s/quiz_sessions/%d/' % (QUIZ_API_ROOT, quiz_session_id),
                                       headers=quiz_session_headers)
    if submission_response.status_code != 200:
        print('Error in quiz metadata retrieval - aborting')
        exit()

    submission_summary_json = json.loads(submission_response.text)
    results_id = submission_summary_json['authoritative_result']['id']
    student_name = submission_summary_json['metadata']['user_full_name']
    student_details = [s for s in student_number_map if s['user_id'] == user_session_id['user_id']]
    spreadsheet['A%d' % spreadsheet_row] = student_details[0]['student_number'] if len(student_details) == 1 else '-1'
    spreadsheet['B%d' % spreadsheet_row] = student_name
    print('Loaded submission summary for', student_name, '-', results_id)

    # then the actual quiz questions
    quiz_questions_response = requests.get('%s/quiz_sessions/%d/session_items' % (QUIZ_API_ROOT, quiz_session_id),
                                           headers=quiz_session_headers)
    quiz_questions_json = json.loads(quiz_questions_response.text)

    # and finally the responses that were submitted
    quiz_answers_response = requests.get(
        '%s/quiz_sessions/%d/results/%s/session_item_results' % (QUIZ_API_ROOT, quiz_session_id, results_id),
        headers=quiz_session_headers)
    quiz_answers_json = json.loads(quiz_answers_response.text)

    current_column = 3  # in our spreadsheet, column 1 is always the student's number; column 2 is always their name
    for question in quiz_questions_json:
        question_id = question['item']['id']
        question_type = question['item']['user_response_type']
        question_title = question['item']['title']

        if not spreadsheet_headers_set:
            spreadsheet_headers.append(question_title)

        print()
        print(question_title)

        current_answer = None
        for answer in quiz_answers_json:
            if answer['item_id'] == question_id:
                current_answer = answer
                break

        if current_answer:
            if question_type == 'Text':
                # text-based responses are simply recorded in the scored data
                raw_answer = current_answer['scored_data']['value']
                if raw_answer:
                    answer_text = re.sub(HTML_REGEX, '', raw_answer)
                    print(answer_text)
                    spreadsheet[
                        '%s%d' % (openpyxl.utils.get_column_letter(current_column), spreadsheet_row)] = answer_text

            elif question_type == 'Uuid':
                # for other response types we have to cross-reference the list of choices available
                matched_answer = None
                for value in current_answer['scored_data']['value']:
                    if current_answer['scored_data']['value'][value]['user_responded']:
                        matched_answer = value

                if matched_answer:
                    for choice in question['item']['interaction_data']['choices']:
                        if choice['id'] == matched_answer:
                            answer_text = re.sub(HTML_REGEX, '', choice['item_body'])
                            print(answer_text)
                            spreadsheet['%s%d' % (
                                openpyxl.utils.get_column_letter(current_column), spreadsheet_row)] = answer_text

            elif question_type == 'MultipleResponse':
                # (note that choice lists are unhelpfully stored in a range of different formats/structures...)
                matched_answer = None
                for value in current_answer['scored_data']['value']:
                    for response in current_answer['scored_data']['value'][value]['value']:
                        if current_answer['scored_data']['value'][value]['value'][response]['user_responded']:
                            matched_answer = response

                if matched_answer:
                    for choice in question['item']['interaction_data']['blanks'][0]['choices']:
                        if choice['id'] == matched_answer:
                            answer_text = re.sub(HTML_REGEX, '', choice['item_body'])
                            print(answer_text)
                            spreadsheet['%s%d' % (
                                openpyxl.utils.get_column_letter(current_column), spreadsheet_row)] = answer_text

            else:
                # TODO: handle any other response types
                print('WARNING: quiz response type', question_type, 'not currently handled - skipping')
                spreadsheet['%s%d' % (
                    openpyxl.utils.get_column_letter(current_column),
                    spreadsheet_row)] = 'DATA MISSING - NOT YET EXPORTED'
                pass

            current_column += 1

    if not spreadsheet_headers_set:
        for header_number in range(1, len(spreadsheet_headers) + 1):  # spreadsheet indexes are 1-based
            column_letter = openpyxl.utils.get_column_letter(header_number)
            spreadsheet['%s1' % column_letter] = spreadsheet_headers[header_number - 1]
        spreadsheet_headers_set = True
    spreadsheet_row += 1

workbook.save(OUTPUT_FILE)
print('Saved', (spreadsheet_row - 1), 'quiz responses to', OUTPUT_FILE)
