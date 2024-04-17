"""Canvas Studio is a useful tool for avoiding file size limits when embedding videos as part of courses. But inserting
a large number of videos on a single page can be tediously repetitive. The other alternative (sharing a collection) does
not support sharing with a course; only individual users. This script helps you generate the embed code for all videos
in a Studio video collection at the same time."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2024 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2024-04-17'  # ISO 8601 (YYYY-MM-DD)

import argparse
import sys
import urllib.parse

import requests.structures

from canvashelpers import Args, Config, Utils


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs=1,
                        help='Please provide the URL of the course you will embed videos into')
    parser.add_argument('--collection', default=None, required=True,
                        help='Please provide the name of the Canvas Studio video collection to gather videos from')
    return parser.parse_args()


args = Args.interactive(get_args)
COURSE_ID = Utils.get_course_id(args.url[0])

config_settings = Config.get_settings()
LTI_INSTITUTION_SUBDOMAIN = config_settings['studio_lti_subdomain']
LTI_BEARER_TOKEN = config_settings['studio_lti_bearer_token']
ROOT_INSTRUCTURE_DOMAIN = 'https://%s/api/media_management/' % LTI_INSTITUTION_SUBDOMAIN
if LTI_INSTITUTION_SUBDOMAIN.startswith('*** your') or LTI_BEARER_TOKEN.startswith('*** your'):
    print('WARNING: studio_lti_subdomain or studio_lti_bearer_token in', Config.FILE_PATH,
          'seems to contain the example value. See the configuration file instructions for further help')

token_headers = requests.structures.CaseInsensitiveDict()
token_headers['accept'] = 'application/json'
token_headers['authorization'] = ('%s' if 'Bearer ' in LTI_BEARER_TOKEN else 'Bearer %s') % \
                                 LTI_BEARER_TOKEN  # in case the heading 'Bearer ' is copied as well as the token itself

search_response_params = {
    'page': 1,  # TODO: proper paging for collection and video list requests
    'per_page': 1000,
    'sort_by': 'created_at',
    'filter': 'all'
}

print('Searching for Studio collections with title', args.collection)
collection_response = requests.get('%s/tiles/user' % ROOT_INSTRUCTURE_DOMAIN, params=search_response_params,
                                   headers=token_headers)
if collection_response.status_code != 200:
    # TODO: there doesn't seem to be an API to get this token, but is there a better alternative to the current way?
    print('ERROR: unable to load Studio collections - did you set a valid studio_lti_subdomain and',
          'studio_lti_bearer_token in %s?' % Config.FILE_PATH)
    sys.exit()

collection_id = None
collection_response_json = collection_response.json()
for collection in collection_response_json['tiles']:
    collection_data = collection['data']
    if collection_data['name'] == args.collection:
        collection_id = collection_data['id']
        break

if collection_id is None:
    print('Unable to find requested collection', args.collection, '- please make sure the name is correct')
    sys.exit()

print('Found collection', args.collection, 'with ID', collection_id, '- requesting titles')
search_response_params['collection_id'] = collection_id
video_response = requests.get('%stiles' % ROOT_INSTRUCTURE_DOMAIN, params=search_response_params,
                              headers=token_headers)
if video_response.status_code != 200:
    print('ERROR: unable to load Collection videos', '-', video_response.text)
    sys.exit()

collection_videos = []
video_response_json = video_response.json()
for video in video_response_json['tiles']:
    collection_videos.append(video['data']['id'])

print('Found', len(collection_videos), 'videos:', collection_videos)
output_html = ''
embed_response_params = {
    'course_id': COURSE_ID,
    'embed_type': 'bare_embed',
    'start_at': 0
}
for video_id in collection_videos:
    embed_response = requests.post(
        '%s/perspectives/%s/create_embed' % (ROOT_INSTRUCTURE_DOMAIN, video_id), params=embed_response_params,
        headers=token_headers)
    if embed_response.status_code != 200:
        print('ERROR: unable to load embed code for video', video_id, '-', embed_response.text)
        continue

    embed_url = embed_response.json()['embed_url']
    print('Generated embed URL for video', video_id, '-', embed_url)
    output_html += '<iframe class="lti-embed" src="/courses/%s/external_tools/retrieve?display=borderless&amp;url=' % COURSE_ID
    output_html += urllib.parse.quote_plus(embed_url)
    output_html += '"></iframe>\n'

print('\nSuccessfully created video embed containers. Copy the following into the HTML editor view of a Canvas page:\n')
print(output_html)
