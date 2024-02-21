# Canvas Helpers
A collection of Python and JavaScript utilities to help make common [Instructure Canvas](https://www.instructure.com/canvas) tasks more manageable.

Please feel free to [open an issue](https://github.com/simonrob/canvas-helpers/issues) with feedback or suggestions, or to report any problems.


## Python tools
The following Python scripts use the Canvas API to retrieve, manipulate or configure your Canvas courses and their data.

Please note that it is possible to quickly make major (and in some cases irreversible) changes to your Canvas courses using these scripts.
As a result, you use these tools at your own risk, and take full responsibility for any actions taken.
Most scripts have a `--dry-run` option that is highly recommended to use for testing before committing to an action.
It is also well worth first running any experiments in a Sandbox course, or the Test or Beta version of your Canvas environment – see [this helpful introduction](https://community.canvaslms.com/t5/Canvas-Developers-Group/Canvas-APIs-Getting-started-the-practical-ins-and-outs-gotchas/ba-p/263685#toc-hId--974335714) for an overview here.

The hope regarding these tools, however, is that you will find that going back to what can be a tediously repetitive manual option in the web-based Canvas portal is inconceivable once you have set up a workflow that works for you.


### Getting started
Begin by cloning or downloading the contents of this repository, then installing the scripts' requirements via `python -m pip install -r requirements.txt` (see [below](https://github.com/simonrob/canvas-helpers#requirements) for further details and special cases).

Next, obtain a Canvas API key from your account's Settings page and add this in [canvashelpers.config](https://github.com/simonrob/canvas-helpers/blob/main/canvashelpers.config).

Once set up is complete, read the descriptions below to get started.
Each script also has a `--help` option that provides further detail.

If this all sounds a bit daunting to you, try installing [tooey](https://github.com/simonrob/tooey) or [gooey](https://github.com/chriskiehl/Gooey/), and the scripts will automatically provide an interface to help guide you through their usage.

Pull requests to improve these tools are very welcome.


### Scripts and capabilities
- [Attachment file/comment/mark uploader](feedbackuploader.py): When assignment marks are processed outside of Canvas, they can already be uploaded in bulk from a spreadsheet using the existing tools (import/export grades).
However, it is not possible to add comments or upload attachments in this way, which means a tiresomely repetitive task of attaching these documents one-by-one.
This script allows you to upload a set of feedback attachments, grades and/or generic or individual text comments in bulk, and is compatible with both individual assignments and group-based ones.
Usage: Place your attachment files in the script's working directory, named according to students' Login IDs (typically their institutional student numbers) or their group names, then run `python feedbackuploader.py [assignment URL]`.
See `python feedbackuploader.py --help` for additional options.

- [Submission downloader/renamer](submissiondownloader.py): Canvas allows you to bulk download students' submission files, but does not give any control over their naming.
It can be useful to have these files named according to students' numbers or group names, which is what this script does.
Downloaded submissions are saved in a folder named as the assignment ID.
If needed, the script can also download Turnitin report PDFs or a spreadsheet of links to each submission's SpeedGrader page.
Usage: `python submissiondownloader.py [assignment URL]`.
See `python submissiondownloader.py --help` for additional options.

- [Bulk file uploader](bulkfileuploader.py): Canvas already allows you to upload multiple files at once, but setting their configuration can still be time-consuming.
This script lets you upload the contents of a folder (selectively, if needed), and set licence types and publish in bulk.
The script also has an option to list direct media links, which is useful when embedding a set of files in a page.
Usage: `python bulkfileuploader.py [folder URL] --working-directory /path/to/directory`.
See `python bulkfileuploader.py --help` for additional options.

- [Student identifier](studentidentifier.py): Canvas sometimes seems to try quite hard to hide the fact that students typically have an institutional identifier (i.e., student number) that is different to their internal Canvas ID.
This script adds a new custom column in a course's Gradebook that shows these student numbers.
Note: by default, courses often have a hidden custom column called 'Notes' that is private to the course teacher.
Only one private column is allowed per course, so this column will be replaced *and any existing data lost* if it is present.
Usage: `python studentidentifier.py [course URL]`.
See `python studentidentifier.py --help` for additional options.

- [Conversation creator](conversationcreator.py): This script allows you to send personalised or generic conversation messages to individual students on a course.
Messages can also include a unique attachment file.
Usage: Place your attachment files in the script's working directory, named according to students' Login IDs (typically their institutional student numbers), then run `python conversationcreator.py [course URL]`.
See `python conversationcreator.py --help` for additional options.

- [WebPA manager](webpamanager.py): [WebPA](https://webpaproject.lboro.ac.uk/) is a useful way of incorporating team member contribution feedback when running group-based assignments.
This script helps run either a Canvas (Old) Quiz-based version of this process; or, an offline version using spreadsheets uploaded to a Canvas assignment, and handles both form/quiz generation and subsequent mark scaling.
See `python webpamanager.py --help` for further instructions.

- [Moderation manager](moderationmanager.py): The intended use of the inbuilt Canvas moderation tools is for one or more markers to initially grade submissions, and then a moderating marker to review these, either selecting one mark as the final grade or providing their own (often naturally an average of the existing marks).
Like so many of the platform's features, this works relatively well with small classes, but is totally impractical at larger course sizes.
In addition, even with smaller classes, moderation does not always work well when rubrics are used – any comments entered by markers whose score is not chosen as the final grade are simply discarded.
This script automates the process of averaging marks from multiple markers; and, when rubrics are used, combines all markers' grades and feedback into a single final rubric that is released (anonymously or with marker names attached) to the student.
Note that the underlying limitations of the Canvas moderation features still apply; in particular the rather arbitrary limit of [10 unique markers per _assignment_](https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Maximum-number-of-moderators-change-to-limit/idi-p/530239) (not per student).
See `python moderationmanager.py --help` for further instructions.

- [Quiz result exporter](quizexporter.py): When using quizzes as assignments that need review or processing of some form (rather than just predetermined correct/incorrect responses), the "New Quizzes" feature on Canvas is far worse than the old version, and–most importantly, for large class sizes–does not allow bulk response export.
After significant community resistance, Canvas developers Instructure have now [relented](https://community.canvaslms.com/t5/New-Quizzes-Resources/Transparency-into-Quizzes-Planning/ta-p/502615) and may at some point implement this missing feature.
In the meantime, this script allows you to export all quiz responses to an XLSX spreadsheet.
Usage: `python quizexporter.py [assignment URL]`.
See `python quizexporter.py --help` for additional options.

- [Course cleaner](coursecleaner.py): Canvas supports the use of course templates ("Blueprints") that are often used to fill new courses with example content.
While this can be useful, if over-used it tends to be more of an annoyance than a helpful starting point. 
This script allows you to easily delete some or all course content (e.g., pages, modules, assignments, etc.) before starting again or importing from an existing course.
See `python coursecleaner.py --help` for further instructions.


### Requirements
Python 3 is required to run all of these scripts.
Most tools have a common set of dependencies, which can be installed from the project's requirements file:
```
python -m pip install -r requirements.txt
```

The [WebPA manager](webpamanager.py) script has an extra requirement that you can install manually:
```
python -m pip install pandas
```


## JavaScript tools
The following scripts can be used in conjunction with a UserScript browser extension to make various refinements to the Canvas web interface.
If you don't already have a UserScript extension, the following options are recommended:
- Violentmonkey: for [Firefox](https://addons.mozilla.org/firefox/addon/violentmonkey/), [Chrome](https://chrome.google.com/webstore/detail/violent-monkey/jinjaccalgkegednnccohejagnlnfdag) or [Edge](https://microsoftedge.microsoft.com/addons/detail/eeagobfjdenkkddmbclomhiblgggliao)
- Userscripts: for [Safari](https://apps.apple.com/us/app/userscripts/id1463298887)

Once you have a UserScript extension, click a script's name in the list below to install it:
- [Canvas helpers](https://github.com/simonrob/canvas-helpers/raw/main/canvashelpers.user.js): Currently, the script does the following:
   - Reduce the size of the homepage cards to allow more courses to be displayed at once
   - Sort groups by name/number in the assignment selection box
   - Reduce extra spacing around list items in various places within courses

- [Sort the roster](https://github.com/simonrob/canvancement/raw/sort-roster/roster/sort-roster/sort-roster.user.js): A slightly enhanced version of an [original script](https://github.com/jamesjonesmath/canvancement/tree/master/roster/sort-roster) by James Jones that allows the Canvas People pages to be sorted, and automatically loads all members of a course.
James' [Canvancement project](https://github.com/jamesjonesmath/canvancement) is well worth exploring for a wide range of other useful scripts.

- [All courses sort](https://github.com/simonrob/canvancement/raw/combine-course-tables/courses/all-courses/all-courses-sort.user.js): A slightly enhanced version of another [James Jones script](https://github.com/jamesjonesmath/canvancement/tree/master/courses/all-courses) that combines the tables on the course list page, and allows them to be sorted and filtered.


## Additional resources
- [Canvas API reference](https://canvas.instructure.com/doc/api/index.html)
- [CanvasAPI](https://canvasapi.readthedocs.io/en/stable/index.html): A Python module for working with the Canvas API (not currently used by this project)
- [Canvancement](https://github.com/jamesjonesmath/canvancement): JavaScript extensions for Canvas
- [Pages Data Merge](https://iworkautomation.com/pages/script-tags-data-merge.html): Create Pages/PDF documents automatically from a Numbers spreadsheet


## License
[Apache 2.0](LICENSE)
