"""Canvas already allows you to upload multiple files at once, but setting their configuration can be time-consuming.
This script lets you upload the contents of a folder (selectively, if needed), set licence types and publish in bulk.
The script also has an option to list direct media links, which is useful when embedding a set of files in a page."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2024 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2024-02-21'  # ISO 8601 (YYYY-MM-DD)

import argparse
import json
import mimetypes
import os
import re
import sys
import uuid

import requests

from canvashelpers import Args, Utils


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs=1,
                        help='Please provide the URL of the course folder in which you would like to store the '
                             'uploaded files')
    parser.add_argument('--working-directory', default=None,
                        help='The root directory to use for the script\'s operation. *All* files within this directory '
                             'that match `--filename-pattern` will be uploaded to the given Canvas folder')
    parser.add_argument('--filename-pattern', default='.*',
                        help='Use this option to pass a (case-insensitive) regular expression pattern that will be '
                             'used to filter and select only files whose names match. For example, `^.*\\.mp[34]$` '
                             'will match all mp3 or mp4 files in the directory, whereas `^Coursework` will match any '
                             'files whose names start with `Coursework`. If not provided, *all* files will be included '
                             '(equivalent to `.*`)')
    parser.add_argument('--file-mime-type', default=None,
                        help='Canvas requires a hint about the MIME type of the attachment file you are uploading. The '
                             'script is able to guess the correct value in most cases, but if you are uploading files '
                             'with an unusual extension or format then you can specify a value here. If set, this '
                             'will be used for *all* files uploaded')
    parser.add_argument('--license', default=None,
                        choices=['own_copyright', 'used_by_permission', 'fair_use', 'public_domain',
                                 'creative_commons'],
                        help='The license type to set for uploaded files')
    parser.add_argument('--publish', action='store_true',
                        help='Whether to publish the uploaded files. In order to publish files, `--license` must also '
                             'be provided. Default: False')
    parser.add_argument('--randomise-names', action='store_true',
                        help='If set, the script will rename the uploaded files with a random UUID (keeping the same '
                             'file extension)')
    parser.add_argument('--get-media-ids', action='store_true',
                        help='When uploading media, Canvas converts files into its own formats before providing a '
                             'media ID (which is needed when using files in, e.g., Pages). This option instructs the '
                             'script to simply list all media IDs in a given folder (then exit). The `--filename-'
                             'pattern` option can be used if needed to filter the output')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview the script\'s actions without actually uploading any files. Highly recommended!')
    return parser.parse_args()


args = Args.interactive(get_args)
COURSE_URL = Utils.course_url_to_api(args.url[0]).split('/files')[0]
COURSE_ROOT, FOLDER_ROOT = args.url[0].split('/files/folder/')

# first we need to locate the remote folder
folder_path_response = requests.get('%s/folders/by_path/%s' % (COURSE_URL, FOLDER_ROOT),
                                    headers=Utils.canvas_api_headers())
if folder_path_response.status_code != 200:
    print('ERROR: unable to find folder', FOLDER_ROOT)
    sys.exit()

selected_folder = folder_path_response.json()[-1]  # this API provides the requested folder last
selected_folder_api_path = '%s/folders/%s/files' % (COURSE_URL.split('/courses')[0], selected_folder['id'])
print('Found requested Canvas folder:', selected_folder)

# getting media IDs is a single-purpose option
if args.get_media_ids:
    print('\nMedia ID mode: searching for existing media in', FOLDER_ROOT)
    existing_files = Utils.canvas_multi_page_request(selected_folder_api_path, type_hint='files')
    if not existing_files:
        print('No files found in the given folder; nothing to do')
        sys.exit()

    folder_json = json.loads(existing_files)
    file_matcher = re.compile(args.filename_pattern, flags=re.IGNORECASE)
    match_count = 0
    print('Found', len(folder_json), 'files total; filtering against pattern', args.filename_pattern)
    for file in folder_json:
        if file['folder_id'] == selected_folder['id'] and file_matcher.match(file['display_name']):
            print('\t', file['display_name'], ':', '%s/files/%s/file_preview' % (COURSE_ROOT, file['id']), ':',
                  file['media_entry_id'])
            match_count += 1
    print('Found', match_count, 'matching files; exiting')
    sys.exit()

# in normal mode, the next step is to filter the list of local files
if not os.path.exists(args.working_directory):
    print('ERROR: unable to find working directory', args.working_directory)
    sys.exit()

selected_files = [f for f in os.listdir(args.working_directory) if
                  re.match(args.filename_pattern, f, flags=re.IGNORECASE)]
print('Found', len(selected_files), 'files to upload:', selected_files)

# finally, we upload and, if requested, set the licence type and publish the files
for file in selected_files:
    file_path = os.path.join(args.working_directory, file)
    file_mime_type = args.file_mime_type or mimetypes.guess_type(file_path)[0]
    _, file_extension = os.path.splitext(file_path)
    file_name = '%s%s' % (uuid.uuid4().hex, file_extension) if args.randomise_names else file
    print('Uploading', file, 'with MIME type', file_mime_type, 'and random name' if args.randomise_names else '',
          file_name)

    uploaded_file_id = None
    if not args.dry_run:
        # if there is an attachment we first need to request an upload URL, then associate with a submission comment
        submission_form_data = {
            'name': file_name,
            'content_type': file_mime_type
        }
        file_upload_url_response = requests.post(selected_folder_api_path, data=submission_form_data,
                                                 headers=Utils.canvas_api_headers())
        if file_upload_url_response.status_code != 200:
            print('\tERROR: unable to retrieve file upload URL; skipping')
            continue

        file_upload_url_json = file_upload_url_response.json()
        print('\tUploading file to', file_upload_url_json['upload_url'].split('?')[0], '[truncated]')

        files_data = {'file': (file_name, open(file_path, 'rb'))}
        file_upload_response = requests.post(file_upload_url_json['upload_url'],
                                             data=submission_form_data, files=files_data,
                                             headers=Utils.canvas_api_headers())

        if file_upload_response.status_code != 201:  # note: 201 Created
            print('\tERROR: unable to upload file; skipping')
            continue

        file_upload_json = file_upload_response.json()
        uploaded_file_id = file_upload_json['id']
        print('\tSuccessfully saved file', file_upload_json['id'], 'at',
              '%s%s' % (args.url[0].split('/courses')[0], file_upload_json['preview_url'].split('?')[0]))
    else:
        print('\tDRY RUN: skipping file upload step')

    if args.license:
        print('\tSetting file license type to', args.license, 'and publishing' if args.publish else '', end='... ')
        if args.dry_run:
            print('\n\tDRY RUN: skipping license configuration step')
            continue

        if uploaded_file_id:
            license_configuration = {
                'file_ids[]': uploaded_file_id,
                'publish': 'false' if not args.publish else args.publish,
                'usage_rights[use_justification]': args.license
            }
            license_update_response = requests.put('%s/usage_rights' % COURSE_URL, params=license_configuration,
                                                   headers=Utils.canvas_api_headers())
            if license_update_response.status_code != 200:
                print('\n\tERROR: unable to set license; skipping:', license_update_response.text)
                continue
            print('success')
