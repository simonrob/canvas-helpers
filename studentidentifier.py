"""Canvas sometimes seems to try quite hard to hide the fact that students typically have an institutional identifier
(i.e., student number) that is different to their Canvas ID. This script adds a new custom column in a course's
Gradebook that shows student numbers. Note: by default, courses often have a hidden custom column called 'Notes' that
is private to the course teacher. Only one private column is allowed per course, so this column will be replaced (*and
any existing data lost*) if it is present."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-02-24'  # ISO 8601 (YYYY-MM-DD)

import argparse
import json

import requests

from canvashelpers import Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please pass the URL of the course to add a Student Number column for')
parser.add_argument('--individual-upload', action='store_true',
                    help='In some cases the default of bulk uploading custom Gradebook column data fails. Set this '
                         'option to try an alternative approach')
parser.add_argument('--dry-run', action='store_true',
                    help='Preview the script\'s actions without actually making any changes. Highly recommended!')
args = parser.parse_args()  # exits if no assignment URL is provided

COURSE_URL = Utils.course_url_to_api(args.url[0])
print('%sCreating Student Number column for course %s' % ('DRY RUN: ' if args.dry_run else '', args.url[0]))

# need to check existing columns - only one private ('teacher_notes') column is allowed per course
# example: {'title': 'Notes', 'position': 1, 'teacher_notes': True, 'read_only': False, 'id': 100, 'hidden': False}
# https://canvas.instructure.com/doc/api/custom_gradebook_columns.html#method.custom_gradebook_columns_api.create
existing_private_column_id = -1
custom_column_response = requests.get('%s/custom_gradebook_columns' % COURSE_URL, headers=Utils.canvas_api_headers())
if custom_column_response.status_code == 200:
    existing_custom_columns = json.loads(custom_column_response.text)
    for column in existing_custom_columns:
        if column['teacher_notes']:
            existing_private_column_id = column['id']
            print('Found existing private column "%s" (ID: %d) - replacing' % (
                column['title'], existing_private_column_id))

if args.dry_run:
    custom_column_id = -1
    print('DRY RUN: skipping custom column creation/replacement')
else:
    new_column_data = {
        'column[title]': 'Student Number',
        'column[position]': 1,
        'column[hidden]': False,
        'column[teacher_notes]': True,
        'column[read_only]': True
    }

    column_request_url = '%s/custom_gradebook_columns/' % COURSE_URL
    request_type = requests.post
    if existing_private_column_id >= 0:
        column_request_url += str(existing_private_column_id)
        request_type = requests.put
    custom_column_request_response = request_type(column_request_url, data=new_column_data,
                                                  headers=Utils.canvas_api_headers())
    if custom_column_request_response.status_code != 200:
        print('\tERROR: unable to create/update custom column; aborting')
        exit()

    custom_column_id = json.loads(custom_column_request_response.text)['id']
    print('Successfully %s custom column %d; now adding user data' % (
        'updated' if existing_private_column_id >= 0 else 'created', custom_column_id))

# only users with a 'student' enrolment are part of a course's Gradebook
course_user_response = Utils.get_course_users(COURSE_URL, enrolment_types=['student'])
if not course_user_response:
    print('ERROR: unable to retrieve course student list; aborting')
    exit()

course_user_json = json.loads(course_user_response)

# bulk upload - doesn't always work with every enrolment type; if that is the case we need the alternative below
if not args.individual_upload:
    column_user_data = []
    for user in course_user_json:
        if 'login_id' in user:
            try:
                user_id = int(user['login_id'])  # ignore non-students, who often have non-numeric IDs
            except ValueError:
                print('WARNING: skipping non-numeric student login_id', user['login_id'])
                continue
            column_user_data.append({'column_id': custom_column_id, 'user_id': user['id'], 'content': user_id})

    if args.dry_run:
        print('DRY RUN: would bulk upload', len(column_user_data), 'records')
        exit()

    column_data_response = requests.put('%s/custom_gradebook_column_data' % COURSE_URL,
                                        json={'column_data': column_user_data}, headers=Utils.canvas_api_headers())

    if column_data_response.status_code != 200:
        print(column_data_response.text)
        print('ERROR: unable to save custom column user data; aborting')
    else:
        print('Successfully submitted bulk data update for column', custom_column_id)
    exit()

# individual upload, submitting a separate request for each user and recovering from errors
for user in course_user_json:
    if 'login_id' in user:
        try:
            user_id = int(user['login_id'])  # ignore non-students, who often have non-numeric IDs
        except ValueError:
            print('WARNING: skipping non-numeric student login_id', user['login_id'])
            continue

        if args.dry_run:
            print('DRY RUN: would set column', custom_column_id, 'for user', user['id'], 'to', user_id)
            continue

        column_data_response = requests.put(
            '%s/custom_gradebook_columns/%d/data/%d' % (COURSE_URL, custom_column_id, user['id']),
            data={'column_data[content]': user_id}, headers=Utils.canvas_api_headers())

        if column_data_response.status_code != 200:
            print('ERROR: unable to save custom column user data: ', column_data_response.text, '- skipping', user)
        else:
            print('Successfully added student ID', user_id, 'for', user['name'], '(%d)' % user['id'])
