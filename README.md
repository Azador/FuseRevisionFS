# FuseRevisionFS
A FUSE file system that adds revision support for your files

You will need fusepy https://github.com/terencehonles/fusepy and Python 3
Start Revision-FS.py to mount an existing directory as revisioned file system on another place.
The original directory may already contain files. These are just mirrored to the mount place.
(Except for files that begin with '.rev_').
If a file is changed on the mounted file system, RevisionFS will create a copy before modifying the file.
You can list the saved revisions of a file with show_revisions.py and change the revision settings with chrev.py.
The default is to store a maximum of 10 old revisions of a file up to a maximum age of 185 days, but at least one revision, even if it is older.

An automatic purge of stored revisions that are getting old is not implemented right now (will maybe follow later).
