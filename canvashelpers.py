"""Utility functions for Canvas helper scripts."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2022 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2022-04-01'  # ISO 8601 (YYYY-MM-DD)

import json
import os

import configparser

import requests.structures


class Config:
    FILE_PATH = '%s/canvashelpers.config' % os.path.dirname(os.path.realpath(__file__))

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
    def get_assignment_id(assignment_url):
        return assignment_url.rstrip('/').split('/')[-1]

    @staticmethod
    def canvas_api_headers():
        submission_list_headers = requests.structures.CaseInsensitiveDict()
        submission_list_headers['accept'] = 'application/json'
        submission_list_headers['authorization'] = 'Bearer %s' % Config.API_TOKEN
        return submission_list_headers

    @staticmethod
    def canvas_multi_page_request(current_request_url, type_hint='API'):
        """Retrieve a full (potentially multi-page) response from the Canvas API. If the initial response refers to
        subsequent pages of results, these are loaded and concatenated automatically. For (slightly) more specific
        progress/error messages, set type_hint to a string describing the API call that is being made """
        # TODO: do this better!
        response = '[]'
        while True:
            print('Requesting', type_hint, 'page:', current_request_url)
            current_response = requests.get(current_request_url, headers=Utils.canvas_api_headers())
            if current_response.status_code != 200:
                print('ERROR: unable to load complete', type_hint, 'response - status code',
                      current_response.status_code)
                return None

            response = response[:-1] + ',' + current_response.text[1:]

            # see: https://canvas.instructure.com/doc/api/file.pagination.html
            page_links = current_response.headers['Link']
            if 'rel="next"' in page_links:
                current_request_url = page_links.split('>; rel="next",<')[0].split('>; rel="current",<')[-1]
            else:
                return '[' + response[2:]

    @staticmethod
    def get_assignment_submissions(assignment_url):
        """Get a list of assignment submissions, returning a string that can be parsed as JSON. This function is simply
        a wrapper around Utils.canvas_multi_page_request, but is kept to separate the API parameter complexity from
        the scripts that use this method"""
        # TODO: handle variants (include[]=submission_history): canvas.instructure.com/doc/api/submissions.html
        # TODO: does requesting group option when there are no groups cause any problems? (no issues seen so far)
        # see: https://canvas.instructure.com/doc/api/submissions.html#method.submissions_api.index
        return Utils.canvas_multi_page_request(
            '%s/submissions?include%%5B%%5D=group&include%%5B%%5D=user&per_page=100' % assignment_url,
            type_hint='assignment submissions list')

    @staticmethod
    def filter_assignment_submissions(submission_list_json, groups_mode=False, include_unsubmitted=False):
        """Filter a list of submissions (in parsed JSON format). Setting groups_mode to True will remove any users who
        are not in a group, and skip any duplicates (which occur because Canvas associates group submissions with each
        group member individually). Setting include_unsubmitted to True will include all entries, even those that do
        not actually have a submission"""
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

            if not ignored_submission:
                filtered_submission_list.append(submission)
        print('Loaded', len(filtered_submission_list), 'valid submissions (discarded',
              (len(submission_list_json) - len(filtered_submission_list)), 'duplicate, invalid or incomplete)')
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
                submitter = {'canvas_user_id': submission['user_id'], 'canvas_group_id': submission['group']['id'],
                             'group_name': submission['group']['name']}
        elif 'user' in submission:
            submitter = {'canvas_user_id': submission['user_id'], 'student_number': submission['user']['login_id'],
                         'student_name': submission['user']['name']}
        return submitter

    @staticmethod
    def get_assignment_student_list(assignment_url):
        """For a given assignment, get the list students it is assigned to. In most cases it is better to use
        Utils.get_assignment_submissions, which returns users as part of its main response. However, the New Quizzes
        API does not return Login IDs, so for that script this method is used to match submissions instead"""
        user_list_response = Utils.canvas_multi_page_request(
            '%s/users?include%%5B%%5D=enrollments&per_page=100' % assignment_url.split('/assignments')[0],
            type_hint='assignment student list')
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
                            user_profile_json = json.loads(user_profile_response.text)
                            student_number = user_profile_json['login_id']
                    submission_student_map.append({'student_number': student_number, 'user_id': user['id']})
        return submission_student_map
