"""A basic GUI launcher for the various tools in the Canvas Helpers collection."""

__author__ = 'Simon Robinson'
__copyright__ = 'Copyright (c) 2023 Simon Robinson'
__license__ = 'Apache 2.0'
__version__ = '2023-08-03'  # ISO 8601 (YYYY-MM-DD)

import subprocess
import tkinter


def launch_tool(name):
    print('Tool selected:', name)
    subprocess.Popen(['python', '%s.py' % name])


window = tkinter.Tk()
window.title('Canvas Helpers launcher')
tkinter.Button(window, text='Attachment file/comment/mark uploader',
               command=lambda: launch_tool('feedbackuploader')).grid(row=0, column=0)
tkinter.Button(window, text='Submission downloader/renamer',
               command=lambda: launch_tool('submissiondownloader')).grid(row=0, column=1)
tkinter.Button(window, text='Student identifier',
               command=lambda: launch_tool('studentidentifier')).grid(row=1, column=0)
tkinter.Button(window, text='Conversation creator',
               command=lambda: launch_tool('conversationcreator')).grid(row=1, column=1)
tkinter.Button(window, text='WebPA manager',
               command=lambda: launch_tool('webpamanager')).grid(row=2, column=0)
tkinter.Button(window, text='Moderation manager',
               command=lambda: launch_tool('moderationmanager')).grid(row=2, column=1)
tkinter.Button(window, text='Quiz result exporter',
               command=lambda: launch_tool('quizexporter')).grid(row=3, column=0)
tkinter.Button(window, text='Course cleaner',
               command=lambda: launch_tool('coursecleaner')).grid(row=3, column=1)

window_left = (window.winfo_screenwidth() - window.winfo_reqwidth()) / 2
window_top = (window.winfo_screenheight() - window.winfo_reqheight()) / 2
window.geometry('+%d+%d' % (window_left, window_top))

# see: https://stackoverflow.com/questions/1892339/
window.lift()
window.attributes('-topmost', True)
window.after_idle(window.attributes, '-topmost', False)

window.mainloop()
