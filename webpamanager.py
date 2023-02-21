"""Generate one-question group peer assessment templates (intended to be uploaded as a comment to a Canvas assignment),
and then process submitted forms using an approach based on the WebPA method to calculate adjusted assignment scores.
Inspired by an offline version of the WebPA scoring system that was originally developed in R by Natalia Obukhova,
Chat Wacharamanotham and Alexander Eiselmayer."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-02-21'  # ISO 8601 (YYYY-MM-DD)

import argparse
import csv
import os
import random
import re
import sys
import tempfile

import openpyxl.styles.differential
import openpyxl.utils
import pandas
import requests

from canvashelpers import Utils

webpa_headers = ['Respondent', 'Person', 'Student №', 'Rating', 'Comments', 'Group №']

parser = argparse.ArgumentParser()
parser.add_argument('group', nargs=1,
                    help='Please pass the URL of the groups page that shows the group set you wish to use for the '
                         'WebPA exercise (e.g., https://canvas.swansea.ac.uk/courses/[course-id]/groups#tab-[set-id])')
parser.add_argument('--setup', action='store_true',
                    help='When set, the script will generate empty WebPA forms to be filled in by group members. If '
                         'not set, the script will look for group members\' responses to process (searching in '
                         '`--working-directory`)')
parser.add_argument('--setup-test', action='store_true',
                    help='When set, the script will insert random responses into the generated WebPA forms')
parser.add_argument('--setup-template', default=None,
                    help='When in `--setup` mode, a template to be used to create group members\' rating forms. Useful '
                         'if you would like to add instructions or other content to the forms each group member '
                         'completes. The template should already contain the response column headers %s as its last '
                         'row. If this parameter is not set, a new spreadsheet will be created with these column '
                         'headers.' % webpa_headers)
parser.add_argument('--setup-individual-output', action='store_true',
                    help='When in `--setup` mode, whether to generate one blank WebPA spreadsheet per group (default); '
                         'or, if set, a customised version for each student number in the group')
parser.add_argument('--marks-file', required='--setup' not in ''.join(sys.argv),
                    help='An XLSX or CSV file containing a minimum of two columns: student number (or group name) and '
                         'mark, in that order. Only applies when not in `--setup` mode')
parser.add_argument('--minimum-variance', type=float, default=0.2,
                    help='The minimum WebPA variance level at which contribution ratings will be used to adjust marks. '
                         'Only applies when not in `--setup` mode. Default: 0.2')
parser.add_argument('--maximum-mark', type=float, default=100,
                    help='The maximum possible mark for the assignment that this exercise is being applied to, used to '
                         'cap adjusted marks. Only applies when not in `--setup` mode. Default: 100')
parser.add_argument('--working-directory', default=None,
                    help='The location to use for processing and output (which will be created if it does not exist). '
                         'In normal mode this directory is assumed to contain all of the individual student responses '
                         'to the WebPA exercise, named as [student number].xlsx (missing files will be treated as non-'
                         'respondents). In `--setup` mode this directory should not exist. Default: the same directory '
                         'as this script')
args = parser.parse_args()  # exits if no group URL is provided

GROUP_ID = args.group[0].split('#tab-')[-1]
try:
    GROUP_ID = int(GROUP_ID)
except ValueError:
    print('ERROR: unable to get group set ID from given URL', args.group[0])
    exit()
print('%s WebPA forms for group set %s' % ('Creating' if args.setup else 'Processing', GROUP_ID))

TEMPLATE_FILE = args.setup_template
working_directory = os.path.dirname(
    os.path.realpath(__file__)) if args.working_directory is None else args.working_directory
WORKING_DIRECTORY = os.path.join(working_directory, str(GROUP_ID))
if args.setup and os.path.exists(WORKING_DIRECTORY):
    print('ERROR: WebPA setup output directory', WORKING_DIRECTORY, 'already exists - please remove or rename')
    exit()
os.makedirs(WORKING_DIRECTORY, exist_ok=True)

if TEMPLATE_FILE:
    response_template_workbook = openpyxl.load_workbook(TEMPLATE_FILE)
    response_template_sheet = response_template_workbook[response_template_workbook.sheetnames[0]]
else:
    response_template_workbook = openpyxl.Workbook()
    response_template_sheet = response_template_workbook.active
    response_template_sheet.title = 'WebPA response form'
    response_template_sheet.append(webpa_headers)
initial_max_rows = response_template_sheet.max_row

# load group details
group_sets = {}
csv_headers = None
group_set_response = requests.get('https://canvas.swansea.ac.uk/api/v1/group_categories/%d/export' % GROUP_ID,
                                  headers=Utils.canvas_api_headers())
if group_set_response.status_code != 200:
    print('\tERROR: unable to load group sets; aborting')
    exit()

group_cache_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
cache_file_name = group_cache_file.name
group_cache_file.write(group_set_response.text)
group_cache_file.close()
with open(cache_file_name) as group_cache_file:
    reader = csv.reader(group_cache_file)
    for row in reader:
        if not csv_headers:
            csv_headers = row
            continue

        group_entry = {
            'group_name': row[csv_headers.index('group_name')],
            'student_number': row[csv_headers.index('login_id')],
            'student_name': row[csv_headers.index('name')]
        }

        group_id = int(group_entry['group_name'].split(' ')[-1])  # note naming scheme assumption
        if group_id not in group_sets:
            group_sets[group_id] = []
        group_sets[group_id].append(group_entry)
os.remove(cache_file_name)
print('Loaded', len(group_sets), 'group sets')

# setup mode - generate empty templates, either personalised per student or general per group
if args.setup:
    thin_border = openpyxl.styles.borders.Border(
        left=openpyxl.styles.borders.Side(border_style=openpyxl.styles.borders.BORDER_THIN, color='00AAAAAA'),
        right=openpyxl.styles.borders.Side(border_style=openpyxl.styles.borders.BORDER_THIN, color='00AAAAAA'),
        top=openpyxl.styles.borders.Side(border_style=openpyxl.styles.borders.BORDER_THIN, color='00AAAAAA'),
        bottom=openpyxl.styles.borders.Side(border_style=openpyxl.styles.borders.BORDER_THIN, color='00AAAAAA')
    )
    output_count = 0
    for key in sorted(group_sets):
        for group_member in group_sets[key]:
            response_template_sheet.append(
                [None, group_member['student_name'], group_member['student_number'], None, None, key])

        if TEMPLATE_FILE:  # highlight the part of the template that needs to be completed
            for row in response_template_sheet.iter_rows(min_row=initial_max_rows,
                                                         max_row=response_template_sheet.max_row):
                for cell in row:
                    cell.fill = openpyxl.styles.PatternFill(start_color='00E7E6E6', end_color='00E7E6E6',
                                                            fill_type='solid')
                    cell.border = thin_border

        if args.setup_individual_output:
            # create a personalised form for each group member
            for group_member in group_sets[key]:
                for row in response_template_sheet.iter_rows(min_row=initial_max_rows + 1,
                                                             max_row=response_template_sheet.max_row, max_col=4):
                    row[0].value = None
                    if row[2].value == group_member['student_number']:
                        row[0].value = '✔'
                        row[0].alignment = openpyxl.styles.Alignment(horizontal='center')

                    if args.setup_test:
                        row[3].value = random.randint(1, 5)
                        print('WARNING: TEST_MODE is active; generating sample response data:', row[3].value)

                response_template_workbook.save(
                    os.path.join(WORKING_DIRECTORY, '%s.xlsx' % group_member['student_number']))
                output_count += 1

        else:
            # just a generic form for the whole group to complete
            response_template_workbook.save(os.path.join(WORKING_DIRECTORY, 'group-%d.xlsx' % key))
            output_count += 1

        # reset for next group
        response_template_sheet.delete_rows(initial_max_rows + 1,
                                            response_template_sheet.max_row - initial_max_rows)
    print('Successfully generated', output_count, 'WebPA forms to', WORKING_DIRECTORY)
    exit()

# processing mode - first load the marks to use as the baseline
marks_map = {}
if args.marks_file is not None:
    marks_file = os.path.join(WORKING_DIRECTORY, args.marks_file)
    if os.path.exists(marks_file):
        if marks_file.lower().endswith('.xlsx'):
            marks_workbook = openpyxl.load_workbook(marks_file)
            marks_sheet = marks_workbook[marks_workbook.sheetnames[0]]
            for row in marks_sheet.iter_rows():
                Utils.parse_marks_file_row(marks_map, [entry.value for entry in row])
        else:
            with open(marks_file, newline='') as marks_csv:
                reader = csv.reader(marks_csv)
                for row in reader:
                    Utils.parse_marks_file_row(marks_map, row)
        print('Loaded original marks mapping for', len(marks_map), 'submissions:', marks_map)
    else:
        print('ERROR: unable to load marks mapping from', args.marks_file, '- not found in assignment directory at',
              marks_file, '; aborting')

# next, load responses and create a master spreadsheet containing all rater responses
response_files = [f for f in os.listdir(WORKING_DIRECTORY) if re.match(r'\d+\.xlsx', f)]
response_summary_workbook = openpyxl.Workbook()
response_summary_sheet = response_summary_workbook.active
response_summary_sheet.title = 'WebPA response form summary'
response_summary_sheet.freeze_panes = 'A2'  # set the first row as a header
response_summary_sheet.append(['Rater', 'Subject', 'Rating', 'Normalised', 'Group'])

expected_submissions = [g['student_number'] for group in group_sets.values() for g in group]
skipped_files = 0
for file in response_files:
    invalid_file = False
    response_workbook = openpyxl.load_workbook(os.path.join(WORKING_DIRECTORY, file))
    response_sheet = response_workbook[response_workbook.sheetnames[0]]

    found_header_row = False
    valid_members = []
    expected_rater = file.split('.')[0]
    if expected_rater not in expected_submissions:
        print('WARNING: skipping unexpected form', file)
        skipped_files += 1
        continue

    current_group = None
    current_rater = None
    current_responses = []
    current_total = 0
    for row in response_sheet.iter_rows(min_row=1, max_row=response_sheet.max_row, max_col=6):
        if webpa_headers == [r.value for r in row]:
            found_header_row = True
            continue
        if found_header_row:
            if not current_group:
                current_group = row[5].value
                valid_members = [g['student_number'] for g in group_sets[current_group]]

            # validate the submitted data against Canvas group membership
            if row[0].value:  # note that we accept any content, not just the '✔' we ask for
                if not current_rater and row[2].value == expected_rater:
                    current_rater = row[2].value
                else:
                    print('WARNING: tampered form (incorrect or multiple raters) in', file)
                    invalid_file = True
            if row[2].value not in valid_members:
                print('WARNING: tampered form (edited member student number)', row[2].value, 'in', file)
                invalid_file = True
            if row[5].value != current_group:
                print('WARNING: tampered form (inconsistent group number)', row[5].value, 'in', file)
                invalid_file = True

            bounded_score = round(max(min(row[3].value, 5), 1))  # don't allow WebPA scores outside the 1-5 (int) range
            if bounded_score != row[3].value:
                print('WARNING: bounding given score to range 1-5:', row[3].value, '->', bounded_score, 'in', file)

            current_responses.append([None, row[2].value, bounded_score, None, current_group])
            current_total += bounded_score

    if not invalid_file:
        for response in current_responses:
            response[0] = current_rater
            response[3] = response[2] / current_total
            response_summary_sheet.append(response)
    else:
        print('WARNING: skipping tampered form', file)
        skipped_files += 1
response_summary_file = os.path.join(WORKING_DIRECTORY, 'response-summary.xlsx')
response_summary_workbook.save(response_summary_file)
print('Loaded', len(response_files) - skipped_files, 'response files, skipping', skipped_files,
      'invalid or tampered submissions; combined responses saved to', response_summary_file)

# finally, shape original marks according to the summary file of group member ratings (using pandas for ease)
data = pandas.read_excel(response_summary_file, dtype={'Rater': object, 'Subject': object})  # student num = non-numeric

# 1) count unique group members and number of submissions to calculate an adjustment factor
unique_data = data.groupby('Group').nunique()
count_group_members = unique_data['Subject']
count_webpa_submissions = unique_data['Rater']
webpa_adjustment_factor = (count_group_members / count_webpa_submissions).to_frame('Adjustment')

# 2) add a column containing the sum of the (normalised) scores, weighted by the adjustment factor
response_data = data.groupby(['Group', 'Subject']).agg(Score=('Normalised', 'sum'))  # new column: Score
response_data['Score'] *= webpa_adjustment_factor['Adjustment']  # include response rate adjustment
response_data = response_data.join(webpa_adjustment_factor)
response_data = response_data.join(count_webpa_submissions.to_frame('Raters'))
response_data = response_data.join(count_group_members.to_frame('Members'))

# 3) add a column showing whether the subject themselves responded
respondent_summary = {}
for file in response_files:
    respondent_summary[file.split('.')[0]] = 'Y'
response_present = pandas.DataFrame.from_dict(respondent_summary, orient='index')
response_present.rename(columns={response_present.columns[0]: 'Responded'}, inplace=True)
response_present.index.names = ['Subject']
response_data = response_data.join(response_present)
response_data = response_data[response_data.columns.tolist()[::-1]]  # reverse the column order for better display

# 4) add a column containing the standard deviation of the group's scores
webpa_variance = response_data.groupby('Group').agg(Variance=('Score', 'std'))  # new column: Variance
response_data['Variance'] = 1  # multiplication correctly maps group numbers; assignment does not, hence we initialise
response_data['Variance'] *= webpa_variance['Variance']

# 5) import the original marks (either individual or group)
original_marks = pandas.DataFrame.from_dict(marks_map, orient='index')
original_marks.rename(columns={original_marks.columns[0]: 'Original'}, inplace=True)
if len(original_marks[[' ' in s for s in original_marks.index]]):  # relatively simplistic detection of group-based file
    original_marks.index = original_marks.index.to_series().str.replace(r'.+?(\d+)', lambda m: m.group(1),
                                                                        regex=True).astype(int)
    original_marks.index.names = ['Group']
else:  # marks file is individual students
    original_marks.index.names = ['Subject']
response_data = response_data.join(original_marks)

# 6) if variance is above the threshold, adjust marks according to the weighting; otherwise use the original group mark
response_data['Weighted'] = response_data['Original']
response_data.loc[response_data['Variance'] > args.minimum_variance, 'Weighted'] *= response_data['Score']

# 7) ensure marks do not go above the maximum for the assignment, and round to the nearest 0.25
response_data['Mark'] = response_data['Weighted']
response_data.loc[response_data['Mark'] > args.maximum_mark, 'Mark'] = args.maximum_mark
response_data['Mark'] = (response_data['Mark'] * 4).round().astype(int) / 4

# 8) save to a calculation result file, highlighting missing data
# response_data.to_excel(output_file, sheet_name='WebPA calculation')
output_file = os.path.join(WORKING_DIRECTORY, 'response-calculation.xlsx')
writer = pandas.ExcelWriter(output_file, engine='openpyxl')
response_data.to_excel(writer, sheet_name='WebPA calculation')
for row in writer.book.active.iter_rows():
    for cell in row:
        if not cell.value:
            cell.fill = openpyxl.styles.PatternFill(start_color='00FFC7CE', end_color='00FFC7CE', fill_type='solid')
writer.close()

print('Successfully calculated WebPA scores and saved to', output_file, '- summary:')
print(response_data)
