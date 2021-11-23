"""Utility functions for Canvas helper scripts."""

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
    def canvas_api_headers():
        submission_list_headers = requests.structures.CaseInsensitiveDict()
        submission_list_headers['accept'] = 'application/json'
        submission_list_headers['authorization'] = 'Bearer %s' % Config.API_TOKEN
        return submission_list_headers

    @staticmethod
    def get_assignment_submissions(assignment_url):
        # TODO: properly handle pagination: https://canvas.instructure.com/doc/api/file.pagination.html
        # TODO: handle variants (submission_history parameter): canvas.instructure.com/doc/api/submissions.html
        return requests.get('%s/submissions/?include[]=submission_history&per_page=1000' % assignment_url,
                            headers=Utils.canvas_api_headers())

    @staticmethod
    def get_assignment_student_list(assignment_url, filter_submission_list=None):
        # TODO: as above, properly handle pagination etc
        # TODO: handle URLs properly (rather than splitting etc)
        user_list_response = requests.get(
            '%s/users?include[]=enrollments&per_page=1000' % assignment_url.split('/assignments')[0],
            headers=Utils.canvas_api_headers())
        if user_list_response.status_code != 200:
            print('ERROR: unable to load assignment student list')
            return

        user_list_json = json.loads(user_list_response.text)
        submission_student_map = []
        for user in user_list_json:
            for role in user['enrollments']:
                if role['type'] == 'StudentEnrollment' and role['enrollment_state'] == 'active' and (
                        filter_submission_list is None or user['id'] in filter_submission_list):
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
