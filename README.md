# Canvas Helpers
A collection of Python scripts to help make common [Canvas](https://www.instructure.com/canvas) tasks more manageable.

Begin by adding your Canvas API key in [canvashelpers.config](https://github.com/simonrob/canvas-helpers/blob/main/canvashelpers.config), then read the guides below to get started.
Each script also has a `--help` option that provides further detail.


## Scripts and functions
- [Attachment file/comment/mark uploader](feedbackuploader.py): When assignment marks are processed outside of Canvas, they can already be uploaded in bulk from a spreadsheet using the existing tools (import/export grades).
However, it is not possible to add comments or upload attachments in this way, which means a tiresomely repetitive task of attaching these documents one-by-one.
This script allows you to upload a set of feedback attachments, grades and/or generic or individual text comments in bulk, and is compatible with both individual assignments and group-based ones.
Usage: Place your attachment files in the script's working directory, named according to students' Login IDs (typically their institutional student numbers) or their group names, then run `python feedbackuploader.py [assignment URL]`.
See `python feedbackuploader.py --help` for additional options.

- [Submission downloader/renamer](submissiondownloader.py): Canvas allows you to bulk download students' submission files, but does not give any control over their naming.
It can be useful to have these files named according to students' numbers or group names, which is what this script does.
Downloaded submissions are saved in a folder named as the assignment ID.
Usage: `python submissiondownloader.py [assignment URL]`.
See `python submissiondownloader.py --help` for additional options.

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
This script helps run an offline version of this process using spreadsheets uploaded to a Canvas assignment, and handles both form generation and mark scaling.
See `python webpamanager.py --help` for further instructions.

- [Moderation manager](moderationmanager.py): The intended use of the inbuilt Canvas moderation tools is for one or more markers to initially grade submissions, and then a moderating marker to review these, either selecting one mark as the final grade or providing their own (often naturally an average of the existing marks).
Like so many of the platform's features, this works relatively well with small classes, but is totally impractical at larger course sizes.
In addition, even with smaller classes, moderation does not always work well when rubrics are used - any comments entered by markers whose score is not chosen as the final grade are simply discarded.
This script automates the process of averaging marks from multiple markers; and, when rubrics are used, combines all markers' grades and feedback into a single final rubric that is released (anonymously or with marker names attached) to the student.
Note that the underlying limitations of the Canvas moderation features still apply; in particular the rather arbitrary limit of 10 unique markers per _assignment_ (not per student).
See `python moderationmanager.py --help` for further instructions.

- [Quiz result exporter](quizexporter.py): When using quizzes as assignments that need review or processing of some form (rather than just predetermined correct/incorrect responses), the "New Quizzes" feature on Canvas is far worse than the old version, and–most importantly, for large class sizes–does not allow bulk response export.
After significant community resistance, Canvas developers Instructure have now [relented](https://community.canvaslms.com/t5/New-Quizzes-Resources/Transparency-into-Quizzes-Planning/ta-p/502615) and may at some point implement this missing feature.
In the meantime, this script allows you to export all quiz responses to an XLSX spreadsheet.
Usage: `python quizexporter.py [assignment URL]`.
See `python quizexporter.py --help` for additional options.

- [Course cleaner](coursecleaner.py): Canvas supports the use of course templates that are often used to fill new courses with example content.
While this can be useful, if over-used it tends to be more of an annoyance than a helpful starting point. 
This script allows you to easily delete some or all course content (e.g., pages, modules, assignments, etc.) before starting again or importing from an existing course.
See `python coursecleaner.py --help` for further instructions.


## Requirements
Python 3 is required to run all of these scripts.
Most tools have a common set of dependencies, which can be installed from the project's requirements file:
```
python -m pip install -r requirements.txt
```

The [WebPA manager](webpamanager.py) script has an extra requirement:
```
python -m pip install pandas
```


## Additional resources
- [Canvas API reference](https://canvas.instructure.com/doc/api/index.html)
- [CanvasAPI](https://canvasapi.readthedocs.io/en/stable/index.html): A Python module for working with the Canvas API (not currently used by this project)
- [Canvancement](https://github.com/jamesjonesmath/canvancement): JavaScript extensions for Canvas
- [Pages Data Merge](https://iworkautomation.com/pages/script-tags-data-merge.html): Create Pages/PDF documents automatically from a Numbers spreadsheet


## License
[Apache 2.0](LICENSE)
