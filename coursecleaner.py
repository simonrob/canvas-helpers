"""Canvas supports the use of course templates that are often used to fill new courses with example content. While this
can be useful, if over-used it tends to be more of an annoyance than a helpful starting point. This script allows you to
easily delete some or all course content before starting again or importing from an existing course."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-06-05'  # ISO 8601 (YYYY-MM-DD)

import argparse
import json
import sys

import requests

from canvashelpers import Utils

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs=1, help='Please pass the URL of the course to be cleaned')
parser.add_argument('--all', action='store_true', help='Delete all of a course\'s content (equivalent to passing '
                                                       'every other available option)')
parser.add_argument('--pages', action='store_true', help='Delete all of a course\'s pages (including the front page)')
parser.add_argument('--modules', action='store_true', help='Delete all of a course\'s modules')
parser.add_argument('--assignments', action='store_true', help='Delete all of a course\'s assignments')
parser.add_argument('--quizzes', action='store_true', help='Delete all of a course\'s quizzes')
parser.add_argument('--discussions', action='store_true', help='Delete all of a course\'s discussions')
parser.add_argument('--announcements', action='store_true', help='Delete all of a course\'s announcements')
parser.add_argument('--events', action='store_true', help='Delete all of a course\'s events')
parser.add_argument('--files', action='store_true', help='Delete all of a course\'s files and folders')
args = parser.parse_args()  # exits if no course URL is provided

COURSE_URL = Utils.course_url_to_api(args.url[0])

course_details_response = requests.get(COURSE_URL, headers=Utils.canvas_api_headers())
if course_details_response.status_code != 200:
    print('ERROR: unable to retrieve course details; aborting')
    sys.exit()
course_details_json = course_details_response.json()
COURSE_ID = course_details_json['id']
COURSE_CODE = course_details_json['course_code']
COURSE_NAME = course_details_json['original_name']


def confirm_deletion(type_hint):
    print()
    if input('Confirm deleting ALL %s for course "%s: %s"? (type yes or no) ' % (
            type_hint, COURSE_CODE, COURSE_NAME)).lower() != 'yes':
        sys.exit('ERROR: aborting deletion; confirmation refused')


# for many content types the basic listing and deletion process follows a very similar pattern
def delete_items(content_list_path, type_hint, params=None):
    content_list_response = Utils.canvas_multi_page_request(content_list_path, params=params,
                                                            type_hint='course %s list' % type_hint)
    if not content_list_response:
        print('ERROR: unable to retrieve course', type_hint, 'list; aborting')
        sys.exit()
    content_list_json = json.loads(content_list_response)

    for content_item in content_list_json:
        content_item_deletion_url = '%s/%d' % (content_list_path, content_item['id'])
        content_item_deletion_response = requests.delete(content_item_deletion_url, headers=Utils.canvas_api_headers())
        if content_item_deletion_response.status_code == 200:
            print('\tDeleted %s at %s:' % (type_hint, content_item_deletion_url), content_item)
        else:
            print('\tWARNING: unable to delete', type_hint, 'at %s:' % content_item_deletion_url,
                  content_item_deletion_response.text, '-', content_item)
    print('Deleted', len(content_list_json), type_hint, 'items')


if args.pages or args.all:
    confirm_deletion(type_hint='pages')

    course_content_path = '%s/pages' % COURSE_URL
    course_content_response = Utils.canvas_multi_page_request(course_content_path, type_hint='course pages')
    if not course_content_response:
        print('ERROR: unable to retrieve course pages list; aborting')
        sys.exit()
    course_content_json = json.loads(course_content_response)

    # the front page cannot be deleted, so we must unset this property first
    for item in course_content_json:
        if item['front_page']:
            front_page_url = '%s/%d' % (course_content_path, item['page_id'])
            front_page_response = requests.put(front_page_url, params={'wiki_page[front_page]': False},
                                               headers=Utils.canvas_api_headers())
            if front_page_response.status_code == 200:
                print('\tDeactivated front page at %s:' % front_page_url, item)
            else:
                print('\tWARNING: unable to unset front page at %s:' % front_page_url,
                      '- will not be able to delete page:', front_page_response.text, '-', item)

    for item in course_content_json:
        item_deletion_url = '%s/%d' % (course_content_path, item['page_id'])
        item_deletion_response = requests.delete(item_deletion_url, headers=Utils.canvas_api_headers())
        if item_deletion_response.status_code == 200:
            print('\tDeleted page at %s:' % item_deletion_url, item)
        else:
            print('\tWARNING: %sunable to delete page at %s:' % (
                'Canvas does not allow deleting the front page; ' if item[
                    'front_page'] else '', item_deletion_url), item_deletion_response.text, '-', item)
    print('Deleted', len(course_content_json), 'pages')

if args.modules or args.all:
    confirm_deletion(type_hint='modules')

    course_content_path = '%s/modules' % COURSE_URL
    course_content_response = Utils.canvas_multi_page_request(course_content_path, type_hint='course modules')
    if not course_content_response:
        print('ERROR: unable to retrieve course modules list; aborting')
        sys.exit()
    course_content_json = json.loads(course_content_response)

    for item in course_content_json:
        content_item_path = '%s/%d/items' % (course_content_path, item['id'])
        content_item_response = Utils.canvas_multi_page_request(content_item_path, type_hint='course module items')
        if not content_item_response:
            print('ERROR: unable to retrieve course module item list; aborting')
            sys.exit()
        content_item_json = json.loads(content_item_response)

        for sub_item in content_item_json:
            sub_item_deletion_url = '%s/%d' % (content_item_path, sub_item['id'])
            sub_item_deletion_response = requests.delete(sub_item_deletion_url, headers=Utils.canvas_api_headers())
            if sub_item_deletion_response.status_code == 200:
                print('\tDeleted module item at %s:' % sub_item_deletion_url, sub_item)
            else:
                print('\tWARNING: unable to delete module item at %s:' % sub_item_deletion_url,
                      sub_item_deletion_response.text, '-', sub_item)
        print('Deleted', len(content_item_json), 'module items')

        item_deletion_url = '%s/%s' % (course_content_path, item['id'])
        item_deletion_response = requests.delete(item_deletion_url, headers=Utils.canvas_api_headers())
        if item_deletion_response.status_code == 200:
            print('\tDeleted module at %s:' % item_deletion_url, item)
        else:
            print('\tWARNING: unable to delete module item at %s:' % item_deletion_url, item_deletion_response.text,
                  '-', item)
    print('Deleted', len(course_content_json), 'modules')

if args.assignments or args.all:
    confirm_deletion(type_hint='assignments')

    # assignments are split into groups, but unlike modules their APIs are not linked
    delete_items(content_list_path='%s/assignments' % COURSE_URL, type_hint='assignment')

    # note: Canvas will auto-create a new assignment group to ensure at least one remains
    delete_items(content_list_path='%s/assignment_groups' % COURSE_URL, type_hint='assignment group')

if args.quizzes or args.all:
    confirm_deletion(type_hint='quizzes')
    delete_items(content_list_path='%s/quizzes' % COURSE_URL, type_hint='quiz')

    # "New Quizzes" have a completely different API path (of course they do)
    delete_items(content_list_path='%s/quizzes' % COURSE_URL.replace('/api/v1', '/api/quiz/v1'), type_hint='new quiz')

if args.discussions or args.all:
    confirm_deletion(type_hint='discussions')
    delete_items(content_list_path='%s/discussion_topics' % COURSE_URL, type_hint='discussion')

if args.announcements or args.all:
    confirm_deletion(type_hint='announcements')

    # announcements are retrieved via the discussions API with a special parameter
    delete_items(content_list_path='%s/discussion_topics' % COURSE_URL, type_hint='announcement',
                 params={'only_announcements': True})

if args.events or args.all:
    confirm_deletion(type_hint='events')
    delete_items('%s/calendar_events' % COURSE_URL.split('/courses')[0], type_hint='event',
                 params={'all_events': True, 'context_codes[]': ['course_%d' % COURSE_ID]})

if args.files or args.all:
    confirm_deletion(type_hint='files')

    # first we delete all folders (forcing deletion of non-empty items and their content)
    course_content_path = '%s/folders' % COURSE_URL
    course_content_response = Utils.canvas_multi_page_request(course_content_path, type_hint='course folders')
    if not course_content_response:
        print('ERROR: unable to retrieve course folders list; aborting')
        sys.exit()
    course_content_json = json.loads(course_content_response)

    for item in course_content_json:
        if item['parent_folder_id'] is None:
            continue  # don't try to delete the root folder (which will fail anyway)
        item_deletion_url = '%s/folders/%d' % (course_content_path.split('/courses')[0], item['id'])
        item_deletion_response = requests.delete(item_deletion_url, params={'force': 'true'},  # note: must be a string
                                                 headers=Utils.canvas_api_headers())
        if item_deletion_response.status_code == 200:
            print('\tDeleted folder at %s:' % item_deletion_url, item)
        else:
            print('\tWARNING: unable to delete folder at %s:' % item_deletion_url, item_deletion_response.text,
                  '-', item)
    print('Deleted', len(course_content_json), 'folders')

    course_content_path = '%s/files' % COURSE_URL
    course_content_response = Utils.canvas_multi_page_request(course_content_path, type_hint='course files')
    if not course_content_response:
        print('ERROR: unable to retrieve course files list; aborting')
        sys.exit()
    course_content_json = json.loads(course_content_response)

    for item in course_content_json:
        item_deletion_url = '%s/files/%d' % (course_content_path.split('/courses')[0], item['id'])
        item_deletion_response = requests.delete(item_deletion_url, headers=Utils.canvas_api_headers())
        if item_deletion_response.status_code == 200:
            print('\tDeleted file at %s:' % item_deletion_url, item)
        else:
            print('\tWARNING: unable to delete file at %s:' % item_deletion_url, item_deletion_response.text, '-', item)
    print('Deleted', len(course_content_json), 'files')