"""Utility functions for Canvas helper scripts."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-05-12'  # ISO 8601 (YYYY-MM-DD)

import configparser
import json
import os
import re

import requests.structures


class Config:
    FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'canvashelpers.config')

    configparser = configparser.ConfigParser()
    configparser.read(FILE_PATH)
    SETTINGS = configparser[configparser.sections()[0]]

    API_TOKEN = SETTINGS['canvas_api_token']  # all scripts need this token; only a subset need the full settings below

    @staticmethod
    def get_settings():
        return Config.SETTINGS


class Utils:
    @staticmethod
    def course_url_to_api(url):
        return url.replace('/courses', '/api/v1/courses')

    @staticmethod
    def course_url_to_speedgrader(url, add_student_id=None):
        speedgrader_url = url.replace('assignments/', 'gradebook/speed_grader?assignment_id=')
        if add_student_id:
            speedgrader_url += '&student_id=' + str(add_student_id)
        return speedgrader_url

    @staticmethod
    def get_course_id(course_url):
        return int(course_url.split('courses/')[-1].split('/')[0])

    @staticmethod
    def get_assignment_id(assignment_url):
        return int(assignment_url.rstrip('/').split('/')[-1])

    @staticmethod
    def get_user_details(api_root, user_id='self'):
        user_details_response = requests.get('%s/users/%s/' % (api_root, user_id), headers=Utils.canvas_api_headers())
        if user_details_response.status_code != 200:
            return user_id, 'UNKNOWN NAME'
        user_details_json = user_details_response.json()
        return user_details_json['id'], user_details_json['name']

    @staticmethod
    def ordered_strings(text):
        # used to sort a list of numbers and/or names in a more natural order
        return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]

    @staticmethod
    def canvas_api_headers():
        submission_list_headers = requests.structures.CaseInsensitiveDict()
        submission_list_headers['accept'] = 'application/json'
        submission_list_headers['authorization'] = 'Bearer %s' % Config.API_TOKEN
        return submission_list_headers

    @staticmethod
    def canvas_multi_page_request(current_request_url, params=None, type_hint='API'):
        """Retrieve a full (potentially multi-page) response from the Canvas API. If the initial response refers to
        subsequent pages of results, these are loaded and concatenated automatically. For (slightly) more specific
        progress/error messages, set type_hint to a string describing the API call that is being made """
        if not params:
            params = {}
        params['per_page'] = 100
        response = '[]'
        while True:
            print('Requesting', type_hint, 'page:', current_request_url)
            current_response = requests.get(current_request_url, params=params, headers=Utils.canvas_api_headers())
            if current_response.status_code != 200:
                print('ERROR: unable to load complete', type_hint, 'response - status code',
                      current_response.status_code)
                return None

            response = response[:-1] + ',' + current_response.text[1:]

            # see: https://canvas.instructure.com/doc/api/file.pagination.html
            page_links = current_response.headers['Link'] if 'Link' in current_response.headers else ''
            next_page_match = re.search(r',\s*<(?P<next>.*?)>;\s*rel="next"', page_links)
            if next_page_match:
                current_request_url = next_page_match.group('next')
            else:
                return '[' + response[2:]

    @staticmethod
    def get_course_users(course_url, includes=None, enrolment_types=None):
        """Get a list of users in a course, returning a string that can be parsed as JSON. This function is simply
        a wrapper around Utils.canvas_multi_page_request, but is kept to separate the API parameter complexity from
        the scripts that use this method"""
        params = {'enrollment_type[]': ['student'] if not enrolment_types else enrolment_types}
        if includes:
            params['include[]'] = []
            for param in includes:
                params['include[]'].append(param)
        return Utils.canvas_multi_page_request('%s/users' % course_url, params=params,
                                               type_hint='course users list')

    @staticmethod
    def get_course_enrolments(course_url, includes=None, enrolment_types=None):
        """Get a list of enrolments in a course, which is slightly different to get_course_users in that it allows us to
        identify the inbuilt test student via their enrolment type 'StudentViewEnrollment'. This function is simply
        a wrapper around Utils.canvas_multi_page_request, but is kept to separate the API parameter complexity from
        the scripts that use this method"""
        params = {'type[]': ['StudentViewEnrollment'] if not enrolment_types else enrolment_types}
        return Utils.canvas_multi_page_request('%s/enrollments' % course_url, params=params,
                                               type_hint='filtered course enrolments list')

    @staticmethod
    def get_assignment_submissions(assignment_url, includes=None):
        """Get a list of assignment submissions, returning a string that can be parsed as JSON. This function is simply
        a wrapper around Utils.canvas_multi_page_request, but is kept to separate the API parameter complexity from
        the scripts that use this method"""
        # TODO: handle variants (include[]=submission_history): canvas.instructure.com/doc/api/submissions.html
        # TODO: does requesting group option when there are no groups cause any problems? (no issues seen so far)
        # see: https://canvas.instructure.com/doc/api/submissions.html#method.submissions_api.index
        params = {'include[]': []}
        includes = ['user', 'group'] + (includes if includes else [])
        for param in includes:
            params['include[]'].append(param)
        return Utils.canvas_multi_page_request('%s/submissions' % assignment_url, params=params,
                                               type_hint='assignment submissions list')

    @staticmethod
    def filter_assignment_submissions(submission_list_json, groups_mode=False, include_unsubmitted=False,
                                      ignored_users=None, sort_entries=False):
        """Filter a list of submissions (in parsed JSON format). Setting groups_mode to True will remove any users who
        are not in a group, and skip any duplicates (which occur because Canvas associates group submissions with each
        group member individually). Setting include_unsubmitted to True will include all entries, even those that do
        not actually have a submission. The ignored_users parameter is an array of Canvas user IDs, and is used to
        remove specific submitters (typically the inbuilt test users)"""
        filtered_submission_list = []
        for submission in submission_list_json:
            ignored_submission = False
            # TODO: sometimes groups without submissions do not appear at all in the submission list - is this fixable?
            if ('workflow_state' in submission and submission['workflow_state'] == 'unsubmitted') \
                    or 'workflow_state' not in submission:
                if not include_unsubmitted:
                    ignored_submission = True

            if groups_mode and not ignored_submission:
                if submission['group']['id'] is None:
                    ignored_submission = True
                else:
                    for parsed_submission in filtered_submission_list:
                        if submission['group']['id'] == parsed_submission['group']['id']:
                            ignored_submission = True
                            break

            if ignored_users and submission['user_id'] in ignored_users:
                ignored_submission = True

            if not ignored_submission:
                filtered_submission_list.append(submission)

        if sort_entries:
            filtered_submission_list = sorted(filtered_submission_list,
                                              key=lambda entry: Utils.ordered_strings(
                                                  entry['group']['name'] if groups_mode else entry['user']['login_id']))

        print('Loaded', 'and sorted' if sort_entries else '', len(filtered_submission_list), 'valid submissions',
              '(discarded', (len(submission_list_json) - len(filtered_submission_list)),
              'filtered, duplicate, invalid/incomplete or missing)')
        return filtered_submission_list

    @staticmethod
    def get_submitter_details(submission, groups_mode=False):
        """For a given submission object (in parsed JSON format), return the submitter's details (the Canvas ID of
        the user who submitted, their Login ID (typically institutional student number), and their name). Setting
        groups_mode to True will return the Canvas group ID and the group name instead of Login ID and student name.
        There is currently no handling of users who are not part of a group (whose group attributes will be None);
        however, if Utils.filter_assignment_submissions is used (with groups_mode=True) beforehand then these users
        will not be present regardless"""
        submitter = None
        if groups_mode:
            if 'group' in submission:
                submitter = {'canvas_user_id': submission['user_id'], 'student_number': submission['user']['login_id'],
                             'canvas_group_id': submission['group']['id'], 'group_name': submission['group']['name']}
        elif 'user' in submission:
            submitter = {'canvas_user_id': submission['user_id'], 'student_number': submission['user']['login_id'],
                         'student_name': submission['user']['name']}
        return submitter

    @staticmethod
    def get_assignment_student_list(assignment_url):
        """For a given assignment, get the list of students it is assigned to. In most cases it is better to use
        Utils.get_assignment_submissions, which returns users as part of its main response. However, the New Quizzes
        API does not return Login IDs, so for that script this method is used to match submissions instead"""
        params = {'include[]': ['enrollments']}
        user_list_response = Utils.canvas_multi_page_request('%s/users' % assignment_url.split('/assignments')[0],
                                                             params=params, type_hint='assignment student list')
        if not user_list_response:
            return None

        user_list_json = json.loads(user_list_response)
        submission_student_map = []
        for user in user_list_json:
            for role in user['enrollments']:
                if role['type'] == 'StudentEnrollment' and role['enrollment_state'] == 'active':
                    if 'login_id' in user:
                        student_number = user['login_id']
                    else:
                        # Canvas has a bug where login_id is missing in some requests - need to get manually (slowly...)
                        print('WARNING: encountered Canvas bug in user list; requesting profile for', user['id'],
                              'manually')
                        user_profile_response = requests.get(
                            '%s/users/%s/profile' % (assignment_url.split('/courses')[0], user['id']),
                            headers=Utils.canvas_api_headers())
                        if user_profile_response.status_code != 200:
                            print('ERROR: unable to load user profile for', user['id'], '- resorting to email')
                            student_number = user['email'].split('@')[0]
                        else:
                            student_number = user_profile_response.json()['login_id']
                    submission_student_map.append({'student_number': student_number, 'user_id': user['id']})
        return submission_student_map

    @staticmethod
    def parse_marks_file_row(marks_map, row):
        # ultra-simplistic check to avoid any header rows (headers are not normally numeric)
        try:
            grade = float(row[1])
        except (ValueError, TypeError):
            return

        student_number_or_group_name = str(row[0])
        marks_map_entry = {'mark': grade}
        if len(row) > 2 and row[2]:  # individual comment is optional
            marks_map_entry['comment'] = row[2]

        if student_number_or_group_name:
            marks_map[student_number_or_group_name] = marks_map_entry
