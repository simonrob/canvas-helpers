"""Canvas sometimes seems to try quite hard to hide the fact that students typically have an institutional identifier
(i.e., student number; also often called login ID) that is different to their Canvas ID. This script adds a new custom
column in a course's Gradebook that shows student numbers and, optionally, group names.

Notes:
    - Canvas courses have a hidden custom gradebook column called 'Notes' that is private to the course teacher, and
      this is where the script adds its annotations. Only one private column is allowed per course, however, so this
      column will be replaced (*and any existing data lost*) if it is present.
    - In recent versions of Canvas it is now possible to show the information added by this script in the default grade
      book view (see the "secondary info" options in the dropdown menu for the student name column), though currently
      only the student ID *or* group name can be shown, not both at once.
"""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2024 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2025-06-23'  # ISO 8601 (YYYY-MM-DD)

import argparse
import json
import sys

import requests

from canvashelpers import Args, Utils


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs=1,
                        help='Please provide the URL of the course to add an identifier column for')
    parser.add_argument('--individual-upload', action='store_true',
                        help='In some cases the default of bulk uploading custom Gradebook column data fails. Set this '
                             'option to try an alternative approach')
    parser.add_argument('--add-group-name', default=None,
                        help='Add the name/number of a group that the student is part of (limit: one group set at '
                             'once). To do this, please pass the URL of the groups page that shows the group set you '
                             'wish to use (e.g., https://canvas.swansea.ac.uk/courses/[course-id]/groups#tab-[set-id])')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview the script\'s actions without actually making any changes. Highly recommended!')
    return parser.parse_args()


args = Args.interactive(get_args)
COURSE_URL = Utils.course_url_to_api(args.url[0])
# noinspection SpellCheckingInspection
print('%sreating identifier column for course %s' % ('DRY RUN: c' if args.dry_run else 'C', args.url[0]))

# need to check existing columns - only one private ('teacher_notes') column is allowed per course
# example: {'title': 'Notes', 'position': 1, 'teacher_notes': True, 'read_only': False, 'id': 100, 'hidden': False}
# https://canvas.instructure.com/doc/api/custom_gradebook_columns.html#method.custom_gradebook_columns_api.create
existing_private_column_id = -1
custom_column_response = requests.get('%s/custom_gradebook_columns' % COURSE_URL, headers=Utils.canvas_api_headers())
if custom_column_response.status_code == 200:
    existing_custom_columns = custom_column_response.json()
    for column in existing_custom_columns:
        if column['teacher_notes']:
            existing_private_column_id = column['id']
            print('Found existing private column "%s" (ID: %d) - replacing' % (
                column['title'], existing_private_column_id))

group_name_map = {}
if args.add_group_name:
    _, group_name_map = Utils.get_course_groups(args.add_group_name, group_by='student_number')

if args.dry_run:
    custom_column_id = -1
    print('DRY RUN: skipping custom column creation/replacement')
else:
    new_column_data = {
        'column[title]': 'Identifier',
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
        sys.exit()

    custom_column_id = custom_column_request_response.json()['id']
    print('Successfully %s custom column %d; now adding user data' % (
        'updated' if existing_private_column_id >= 0 else 'created', custom_column_id))

# only users with a 'student' enrolment are part of a course's Gradebook
course_user_response = Utils.get_course_users(COURSE_URL, enrolment_types=['student'])
if not course_user_response:
    print('ERROR: unable to retrieve course student list; aborting')
    sys.exit()

course_user_json = json.loads(course_user_response)


# add a group number where requested - separated for easier format customisation
def get_column_content(user_identifier):
    column_value = user_identifier
    if args.add_group_name and user_identifier in group_name_map:
        column_value = '%s (Gr. %s)' % (user_identifier, group_name_map[user_identifier]['group_number'])
    else:
        print('WARNING: no group found for user', user_identifier)
    return column_value


# bulk upload - doesn't always work with every enrolment type; if that is the case we need the alternative below
if not args.individual_upload:
    column_user_data = []
    for user in course_user_json:
        if 'login_id' in user:
            try:
                int(user['login_id'])  # ignore non-students, who often have non-numeric IDs
            except ValueError:
                print('WARNING: skipping non-numeric student login_id', user['login_id'])
                continue
            column_content = get_column_content(str(user['login_id']))
            column_user_data.append({'column_id': custom_column_id, 'user_id': user['id'], 'content': column_content})

    if args.dry_run:
        print('DRY RUN: would bulk upload', len(column_user_data), 'records')
        sys.exit()

    column_data_response = requests.put('%s/custom_gradebook_column_data' % COURSE_URL,
                                        json={'column_data': column_user_data}, headers=Utils.canvas_api_headers())

    if column_data_response.status_code != 200:
        print(column_data_response.text)
        print('ERROR: unable to save custom column user data; aborting')
    else:
        print('Successfully submitted bulk data update for column', custom_column_id)
    sys.exit()

# individual upload, submitting a separate request for each user and recovering from errors
for user in course_user_json:
    if 'login_id' in user:
        try:
            int(user['login_id'])  # ignore non-students, who often have non-numeric IDs
        except ValueError:
            print('WARNING: skipping non-numeric student login_id', user['login_id'])
            continue
        column_content = get_column_content(str(user['login_id']))

        if args.dry_run:
            print('DRY RUN: would set column', custom_column_id, 'for user', user['id'], 'to', column_content)
            continue

        column_data_response = requests.put(
            '%s/custom_gradebook_columns/%d/data/%d' % (COURSE_URL, custom_column_id, user['id']),
            data={'column_data[content]': column_content}, headers=Utils.canvas_api_headers())

        if column_data_response.status_code != 200:
            print('ERROR: unable to save custom column user data: ', column_data_response.text, '- skipping', user)
        else:
            print('Successfully added identifier', column_content, 'for', user['name'], '(%d)' % user['id'])
