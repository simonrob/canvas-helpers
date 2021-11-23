# Canvas Helpers
A collection of Python scripts to help make common Canvas tasks more manageable

- [Quiz result exporter](quizexporter.py): When using Quizzes as assignments that need review or processing of some form (rather than just predetermined correct/incorrect responses), the "New Quizzes" feature on Canvas is far worse than the old version, and does not allow bulk response export. This script provides that missing feature, exporting to an XLSX spreadsheet. Usage: `python3 quizexporter.py [assignment URL]`

- [Attachment file/comment/mark uploader](feedbackuploader.py): When assignment marks are processed outside of Canvas itself, they can already be uploaded in bulk from a spreadsheet using the existing Canvas tools (import/export grades). But it is not possible to add comments or upload attachments in this way (except through an [unreliable hack](https://ltech.ljmu.ac.uk/wp-content/uploads/2017/04/Batch-Uploading-Student-Submissions-and-Feedback.pdf)), which means a tiresomely repetitive task of attaching these documents one-by-one. This script allows you to upload a set of feedback attachments, grades and/or generic or individual text comments in bulk. Usage: place your attachment files in the script's working directory, named according to students' login IDs/numbers, then run `python3 feedbackuploader.py [assignment URL]`. See `python3 feedbackuploader.py --help` for further options.

- [Submission downloader/renamer](submissiondownloader.py): Canvas allows you to bulk download students' submission files, but does not give any control over their naming. It can be useful to have these files named according to students' login IDs/numbers, which is what this script does. Submissions are saved in the script's current directory in a folder named as the assignment ID. Usage: `python3 submissiondownloader.py [assignment URL]`


## Additional resources
- [Canvas API reference](https://canvas.instructure.com/doc/api/index.html)
- [Canvancement (JavaScript extensions for Canvas)](https://github.com/jamesjonesmath/canvancement)


## License
[Apache 2.0](LICENSE)
