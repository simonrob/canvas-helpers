"""Canvas sometimes seems to try quite hard to hide the fact that students typically have an institutional identifier
(i.e., student number) that is different to their Canvas ID. This script adds a new custom column in a course's
Gradebook that shows student numbers. Note: by default, courses often have a hidden custom column called 'Notes' that
is private to the course teacher. Only one private column is allowed per course, so this column will be replaced (*and
any existing data lost*) if it is present."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-06-28'  # ISO 8601 (YYYY-MM-DD)

import json
import sys

import requests

from canvashelpers import Args, Utils

parser = Args.ArgumentParser()
parser.add_argument('url', nargs=1,
                    help='Please provide the URL of the course to add an identifier column for')
parser.add_argument('--individual-upload', action='store_true',
                    help='In some cases the default of bulk uploading custom Gradebook column data fails. Set this '
                         'option to try an alternative approach')
parser.add_argument('--add-group-name', default=None,
                    help='Add the name/number of a group that the student is part of (limit: one group set at once). '
                         'To do this, please pass the URL of the groups page that shows the group set you wish to use '
                         '(e.g., https://canvas.swansea.ac.uk/courses/[course-id]/groups#tab-[set-id])')
parser.add_argument('--dry-run', action='store_true',
                    help='Preview the script\'s actions without actually making any changes. Highly recommended!')
args = Args.parse_args(parser, __version__)  # if no URL: interactively requests arguments if `isatty`; exits otherwise

COURSE_URL = Utils.course_url_to_api(args.url[0])
print('%screating identifier column for course %s' % ('DRY RUN: ' if args.dry_run else '', args.url[0]))

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
    group_set_id = args.add_group_name.split('#tab-')[-1]
    try:
        group_set_id = int(group_set_id)
    except ValueError:
        print('ERROR: unable to get group set ID from given URL', args.add_group_name)
        sys.exit()

    api_root = COURSE_URL.split('/courses')[0]
    group_set_response = Utils.canvas_multi_page_request('%s/group_categories/%d/groups' % (api_root, group_set_id),
                                                         type_hint='group sets')
    if not group_set_response:
        print('ERROR: unable to load group sets; aborting')
        sys.exit()

    group_set_json = json.loads(group_set_response)
    for group in group_set_json:
        group_members_response = Utils.canvas_multi_page_request('%s/groups/%d/users' % (api_root, group['id']),
                                                                 type_hint='group')
        if not group_members_response:
            print('WARNING: unable to load group members; skipping group', group)
            continue

        group_members_json = json.loads(group_members_response)
        for member in group_members_json:
            try:
                user_id = int(member['login_id'])  # ignore non-students, who often have non-numeric IDs
            except ValueError:
                print('WARNING: skipping non-numeric group member', member['login_id'])
                continue
            group_name_map[user_id] = group['name']

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
        group_name = group_name_map[user_identifier]
        if ' ' in group_name:
            group_name = 'Gr: %s' % group_name.split(' ')[-1]  # use only the group number if possible (to fit column)
        column_value = '%d (%s)' % (user_identifier, group_name)
    return column_value


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
            column_content = get_column_content(user_id)
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
            user_id = int(user['login_id'])  # ignore non-students, who often have non-numeric IDs
        except ValueError:
            print('WARNING: skipping non-numeric student login_id', user['login_id'])
            continue
        column_content = get_column_content(user_id)

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
