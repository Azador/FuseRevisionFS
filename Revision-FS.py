#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import stat
import sys
import os
import stat
import fuse
import errno
import shutil
import logging
import argparse
import datetime
import re
#from numpy import s_
import RevFS

revision_prefix = '.rev_'
revision_escape_prefix = revision_prefix + 'e_'
revision_info_prefix = revision_prefix + 'i_'
max_revisions = 10
max_revision_age = 185
min_revisions_age = 1

xattr_max_revisions_name = RevFS.xattr_max_revisions_name
xattr_revisions_name     = RevFS.xattr_revisions_name
xattr_max_revision_age   = RevFS.xattr_max_revision_age
xattr_min_revisions_age  = RevFS.xattr_min_revisions_age

log_file = None
if "HOME" in os.environ:
    log_file = os.environ["HOME"]
else:
    log_file = os.getcwd ()

log_file = os.path.join (log_file, ".revision_fs.log")

class FileInfo:
    def __init__ (self):
        self.copy_on_write = True
        self.revisions = max_revisions
        self.max_age = max_revision_age
        self.min_revisions = min_revisions_age
        
    def setMaxRevisions (self, revisions):
        self.revisions = revisions
        if self.min_revisions > revisions:
            self.min_revisions = revisions
        
    def setMinRevisionsAge (self, min_revisions):
        self.min_revisions = min_revisions
        if self.revisions < min_revisions:
            self.revisions < min_revisions

    def setMaxRevisionAge (self, max_age):
        self.max_age = max_age
        
    def loadFileInfo (self, src_path):
        (head, tail) = os.path.split (src_path)
        
        info_file_name = os.path.join (head, revision_info_prefix + tail)
        if not os.path.exists (info_file_name):
            return
        
        f = open (info_file_name, 'r')
        for line in f:
            (keyword, value) = line.strip ().split ('=', maxsplit=1)
            keyword = keyword.strip ()
            value = value.strip ()
            
            if keyword == 'revisions':
                try:
                    revisions = int (value)
                    self.revisions = revisions
                except ValueError:
                    pass
                
            elif keyword == 'max_age':
                try:
                    max_age = int (value)
                    self.max_age = max_age
                except ValueError:
                    pass
                
            elif keyword == 'min_revisions':
                try:
                    min_revisions = int (value)
                    self.min_revisions = min_revisions
                except ValueError:
                    pass
                
        if self.min_revisions >= self.revisions:
            self.revisions = self.min_revisions

        f.close ()
    
    def saveFileInfo (self, src_path):
        (head, tail) = os.path.split (src_path)
        
        info_file_name = os.path.join (head, revision_info_prefix + tail)
        f = open (info_file_name, 'w')
        #logging.debug ("saveFileInfo: revisions: %s", repr (self.revisions))
        f.write ("{0}={1}\n".format ('revisions', self.revisions))
        f.write ("{0}={1}\n".format ('max_age', self.max_age))
        f.write ("{0}={1}\n".format ('min_revisions', self.min_revisions))

        f.close ()
    

class File:
    def __init__ (self, src_path, is_dir, open_flags = None):
        self.src_path = src_path
        self.is_dir = is_dir
        self.file = None
        self.open_flags = open_flags
        
    def getRevisionName (self, revision):
        (src_dir, src_name) = os.path.split (self.src_path)
        return os.path.join (src_dir, revision_prefix + str (revision) + '_' + src_name) 

    def getAvailableRevisions (self):
        (src_dir, src_name) = os.path.split (self.src_path)
        dirlist = os.listdir (src_dir)
        revisions = []
        for dir in dirlist:
            #print ("check ", repr (dir))
            if dir.startswith (revision_prefix) and not dir.startswith (revision_escape_prefix):
                snum = ''
                i = len (revision_prefix)
                
                while i < len (dir) and dir[i] != '_':
                    snum += dir[i]
                    i += 1
                
                #print ("  found revision: ", repr (dir[i:]))
                if dir[i+1:] == src_name:
                    try:
                        num = int (snum)
                        if num >= 1:
                            #print ("found revision ", num, " of file ", self.src_path)
                            revisions.append (num)
                    except ValueError:
                        pass

        return revisions
    
    def removeRecursiv (self, path):
        if not os.path.islink (path) and os.path.isdir (path):
            for (dirpath, dirnames, filenames) in os.walk (path, topdown=False):
                for name in filenames:
                    os.unlink (os.path.join (dirpath, name))
                for name in dirnames:
                    os.rmdir (os.path.join (dirpath, name))
            os.rmdir (path)
        else:
            os.unlink (path)
        
    def limitRevisions (self, file_info):
        if os.path.lexists (self.src_path):
            existing_revisions = self.getAvailableRevisions ()

            del_date = datetime.datetime.now () - datetime.timedelta (days=file_info.max_age)

            for rev in existing_revisions:
                if rev > file_info.min_revisions:
                    if rev <= file_info.revisions:
                        mtime = datetime.datetime.fromtimestamp (os.stat (self.getRevisionName (rev), follow_symlinks=False).st_mtime)
                    
                        if mtime >= del_date:
                            continue

                    logging.info ("delete revision %d (%s)", rev, self.getRevisionName (rev))
                    self.removeRecursiv (self.getRevisionName (rev))
        
    def createRevisionCopy (self, file_info, use_rename = False):
        if os.path.lexists (self.src_path):
            existing_revisions = self.getAvailableRevisions ()
            
            logging.info ("Creating new revision for %s, now having %d of %d revisions",
                          self.src_path, min (len (existing_revisions)+1, file_info.revisions), file_info.revisions)
            
            del_date = datetime.datetime.now () - datetime.timedelta (days=file_info.max_age)
            
            if file_info.revisions in existing_revisions:
                self.removeRecursiv (self.getRevisionName (file_info.revisions))
        
            for i in range (file_info.revisions-1, 0, -1):
                if i in existing_revisions:

                    if i > file_info.min_revisions:
                        mtime = datetime.datetime.fromtimestamp (os.stat (self.getRevisionName (i), follow_symlinks=False).st_mtime)
                    
                        if mtime < del_date:
                            logging.info ("delete revision %d (%s)", i, self.getRevisionName (i))
                            self.removeRecursiv (self.getRevisionName (i))
                            continue
                        
                    os.rename (self.getRevisionName (i), self.getRevisionName (i+1))

            if file_info.revisions == 0:
                logging.info ("should not copy/rename original file (%s)", self.src_path)
                
            if use_rename:
                os.rename (self.src_path, self.getRevisionName (1))
            elif os.path.islink (self.src_path):
                logging.error ("Copy of symbolic link not implemented")
                raise fuse.FuseOSError (errno.ENOSYS)
            elif os.path.isdir (self.src_path):
                logging.error ("Copy of directory not implemented")
                raise fuse.FuseOSError (errno.ENOSYS)
            elif os.path.isfile (self.src_path):
                shutil.copy2 (self.src_path, self.getRevisionName (1))
            else:
                logging.error ("Copy of not regular file not implemented")
                raise fuse.FuseOSError (errno.ENOSYS)

    def open (self, mode = None):
        if self.file != None:
            raise fuse.FuseOSError (errno.EIO)

        open_mode = ''
        
        m = self.open_flags & os.O_ACCMODE
        trunc = (self.open_flags & os.O_TRUNC) == os.O_TRUNC
        create = (self.open_flags & os.O_CREAT) == os.O_CREAT
        append = (self.open_flags & os.O_APPEND) == os.O_APPEND
        exclusive = (self.open_flags & os.O_EXCL) == os.O_EXCL
        opener = os.open
        if mode != None:
            opener = lambda path, flags, dir_fd=None: os.open (path, flags, mode, dir_fd = dir_fd)
        
        if os.path.exists (self.src_path):
            if create and exclusive:
                raise fuse.FuseOSError (errno.EEXIST)
        else:
            if not create:
                raise fuse.FuseOSError (errno.ENOENT)
            
            self.need_copy_on_write = False
            
        if m == os.O_RDWR:
            if trunc or create:
                open_mode = 'w+b'
            elif append:
                open_mode = 'a+b'
            else:
                open_mode = 'r+b'
        elif m == os.O_RDONLY:
            open_mode = 'rb'
        elif m == os.O_WRONLY:
            if append:
                open_mode = 'ab'
            else:
                open_mode = 'wb'

        try:
            self.file = open (self.src_path, open_mode, opener = opener)
        except OSError as e:
            print (repr (e))
            self.file = None
            raise fuse.FuseOSError (e.errno)
        
    def close (self):
        if self.is_dir:
            return
        
        if self.file == None:
            raise fuse.FuseOSError (errno.EIO)
        
        self.file.close ()
        self.file = None
        
    def readdir (self):
        if not self.is_dir:
            raise fuse.FuseOSError(errno.EIO)
        
        dirs = ['.', '..']
        dirlist = os.listdir (self.src_path)
        for dir in dirlist:
            try:
                encoded_dir = dir.encode ("utf-8")
            except Exception as e:
                logging.error ("Cannot encode %s: File name is no valid UTF-8. Ignoring file.",
                               repr (os.path.join (self.src_path, dir)))
                continue
                
            if dir.startswith (revision_prefix):
                if dir.startswith (revision_escape_prefix):
                    dirs.append (revision_escape_prefix + dir[len(revision_escape_prefix):])
            else:
                dirs.append (dir)
        #print ("  result: ", repr (dirs))
        return dirs

    def read (self, size, offset):
        if self.is_dir:
            raise fuse.FuseOSError(errno.EIO)

        f = self.file
        f.seek (offset)
        return f.read (size)

    def write (self, data, offset):
        if self.is_dir:
            raise fuse.FuseOSError(errno.EIO)

        f = self.file
        f.seek (offset)
        return f.write (data)

class RevisionFS (fuse.Operations):
    def __init__ (self, src_dir):
        self.src_dir = src_dir
        self.file_handles = {}
        self.files = {}
        
    def getSource (self, path):
        parts = []
        dir = path.lstrip ('/')
        while path != '':
            (head, tail) = os.path.split (dir)
            if tail == None or tail == '':
                break
            if tail.startswith (revision_prefix):
                tail = revision_escape_prefix + tail[len (revision_prefix):]
            parts = [tail] + parts
            dir = head

        src_path = self.src_dir
        for part in parts:
            src_path = os.path.join (src_path, part)
        return src_path

    def copyOnWrite (self, file, use_rename=False):
        file_info = FileInfo ()
        if file.src_path in self.files:
            file_info = self.files[file.src_path]
            if not file_info.copy_on_write:
                return
            
            file_info.copy_on_write = False
        else:
            file_info.loadFileInfo (file.src_path)
            
        file.createRevisionCopy (file_info, use_rename)
        
    def createFileHandle (self, file):
        if file.src_path not in self.files:
            #logging.debug ("add file %s to copy on write list", file.src_path)
            self.files[file.src_path] = FileInfo ()
            self.files[file.src_path].loadFileInfo (file.src_path)
            
        free_fh = 0
        while free_fh in self.file_handles:
            free_fh += 1
            
        self.file_handles[free_fh] = file
        return (free_fh, file)
    
    def access(self, path, amode):
        logging.debug ("access: %s", repr ((path, amode)))
        src_path = self.getSource (path)
        
        if not os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.ENOENT)
        
        if os.access (src_path, amode, follow_symlinks=False):
            return 0

        raise fuse.FuseOSError (errno.EACCES)

    bmap = None

    def chmod(self, path, mode):
        logging.debug ("chmod: %s", repr ((path, mode)))
        src_path = self.getSource (path)
        
        if not os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.ENOENT)
        
        os.chmod (src_path, mode)

    def chown(self, path, uid, gid):
        logging.debug ("chown: %s", repr ((path, uid, gid)))
        src_path = self.getSource (path)
        
        if not os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.ENOENT)
        
        os.chown (src_path, uid, gid)

    def create(self, path, mode, fi=None):
        '''
        When raw_fi is False (default case), fi is None and create should
        return a numerical file handle.

        When raw_fi is True the file handle should be set directly by create
        and return 0.
        '''

        (fh, file) = self.createFileHandle (File (self.getSource (path), False, os.O_CREAT | os.O_WRONLY | os.O_TRUNC))
        self.copyOnWrite (file)
        file.open (mode)
        return fh

    def destroy(self, path):
        'Called on filesystem destruction. Path is always /'

        #logging.debug ("destroy: %s", repr (path))
        logging.info ("Unmount %s", repr (self.src_dir))

    def flush(self, path, fh):
        logging.debug ("flush: %s", repr ((path, fh)))
        
        if fh not in self.file_handles:
            raise fuse.FuseOSError (errno.ENOENT)
        
        f = self.file_handles[fh]
        
        if f.file == None:
            raise fuse.FuseOSError (errno.ENOENT)

        f.file.flush ()
        return 0

    def fsync(self, path, datasync, fh):
        logging.warning ("fsync: %s - not implemented", repr ((path, datasync, fh)))
        return 0

    def fsyncdir(self, path, datasync, fh):
        logging.warning ("fsyncdir: %s - not implemented", repr ((path, datasync, fh)))
        return 0

    def getattr(self, path, fh=None):
        '''
        Returns a dictionary with keys identical to the stat C structure of
        stat(2).

        st_atime, st_mtime and st_ctime should be floats.

        NOTE: There is an incombatibility between Linux and Mac OS X
        concerning st_nlink of directories. Mac OS X counts all files inside
        the directory, while Linux counts only the subdirectories.
        '''
        logging.debug ("getattr: %s", repr ((path, fh)))
        
        src_path = self.getSource (path)
        #logging.debug ("  src_path: %s", repr (src_path))

        if not os.path.lexists (src_path):
            #logging.debug ("  path %s missing", src_path)
            f = File (src_path, False)
            revs = f.getAvailableRevisions ()
            if len (revs) > 0:
                # File not existing but old revisions exist
                res = dict (st_mode=0o100000, st_nlink=1, st_ino=0, st_uid=0, st_gid=0,
                            st_size=0, st_atime=0, st_mtime=0, st_ctime=0)
                return res
            
            raise fuse.FuseOSError (errno.ENOENT)
        
        #r = os.stat (src_path, follow_symlinks=False)
        try:
            r = os.lstat (src_path)
        except IOError as e:
            #logging.debug ("  exception: %s", repr (e))
            raise e
        
        #logging.debug ("  result: %s", repr (r))
        res = dict (st_mode=r.st_mode, st_nlink=r.st_nlink, st_ino=r.st_ino, st_dev=r.st_dev, st_uid=r.st_uid, st_gid=r.st_gid,
                    st_size=r.st_size, st_atime=r.st_atime, st_mtime=r.st_mtime, st_ctime=r.st_ctime)
        try:
            res["st_blocks"] = r.st_blocks
        except:
            res["st_blocks"] = (r.st_size + 511) / 512

        try:
            res["st_blksize"] = r.st_blksize
        except:
            res["st_blksize"] = 512
            
        #logging.debug ("  result: %s", repr (res))
        
        return res

    def getxattr(self, path, name, position=0):
        logging.debug ("getxattr: %s", repr ((path, name, position)))
        src_path = self.getSource (path)

        if name == xattr_revisions_name:
            f = File (src_path, is_dir=False)
            revisions = f.getAvailableRevisions ()
            res = []
            revisions.sort ()
            for rev in revisions:
                fn = f.getRevisionName (rev)
                sr = os.stat (fn, follow_symlinks=False)
                res.append ("({0},{1},{2})".format (rev, str (datetime.datetime.fromtimestamp (sr.st_mtime)), sr.st_size).encode ('ASCII'))

            return b",".join (res)

        file_info = FileInfo ()
        if src_path in self.files:
            file_info = self.files
        else:
            file_info.loadFileInfo (src_path)
                
        if name == xattr_max_revisions_name:
            #logging.debug ("  result: %s", repr (bytes (str (file_info.revisions), "ASCII")))
            return bytes (str (file_info.revisions), "ASCII")
        
        if name == xattr_max_revision_age:
            return bytes (str (file_info.max_age), "ASCII")

        if name == xattr_min_revisions_age:
            return bytes (str (file_info.min_revisions), "ASCII")
        
        res = os.getxattr (src_path, name, follow_symlinks=False)
        #logging.debug ("  result: %s", repr (res))
        return res

    def init(self, path):
        '''
        Called on filesystem initialization. (Path is always /)

        Use it instead of __init__ if you start threads on initialization.
        '''

        logging.debug ("init: %s", repr (path))
        pass

    def link(self, target, source):
        'creates a hard link `target -> source` (e.g. ln source target)'

        logging.debug ("link: %s", repr ((target, source)))
        os.link (self.getSource (source), self.getSource (target))

    def listxattr(self, path):
        logging.debug ("listxattr: %s", repr (path))
        src_path = self.getSource (path)
        
        res = []
        if not os.path.lexists (src_path):
            f = File (src_path, False)
            revs = f.getAvailableRevisions ()
            if len (revs) == 0:
                raise fuse.FuseOSError (errno.EEXIST)

            # File not existing but old revisions exist
        else:
            res = os.listxattr (src_path, follow_symlinks=False)
            
        res.append (xattr_revisions_name)
        res.append (xattr_max_revisions_name)
        #logging.debug ("  result: %s", repr (res))
        return res

    lock = None

    def mkdir(self, path, mode):
        logging.debug ("mkdir: %s", repr ((path, mode)))
        src_path = self.getSource (path)
        if os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.EEXIST)

        os.mkdir (src_path, mode)

    def mknod(self, path, mode, dev):
        logging.warning ("mknod: %s - not implemented", repr ((path, mode, dev)))
        raise fuse.FuseOSError(errno.ENOSYS)

    def open(self, path, flags):
        '''
        When raw_fi is False (default case), open should return a numerical
        file handle.

        When raw_fi is True the signature of open becomes:
            open(self, path, fi)

        and the file handle should be set directly.
        '''

        logging.debug ("open: %s", repr ((path, flags)))
        
        (fh, file) = self.createFileHandle (File (self.getSource (path), False, flags))
        if (flags & os.O_TRUNC) == os.O_TRUNC:
            self.copyOnWrite (file)
        file.open ()
        return fh

    def opendir(self, path):
        'Returns a numerical file handle.'

        logging.debug ("opendir: %s", repr (path))
        (fh, file) = self.createFileHandle (File (self.getSource (path), True))
        return fh

    def read(self, path, size, offset, fh):
        'Returns a string containing the data requested.'

        logging.debug ("read: %s", repr ((path, size, offset, fh)))

        if fh not in self.file_handles:
            raise fuse.FuseOSError(errno.EIO)

        return self.file_handles[fh].read (size, offset)

    def readdir(self, path, fh):
        '''
        Can return either a list of names, or a list of (name, attrs, offset)
        tuples. attrs is a dict as in getattr.
        '''

        logging.debug ("readdir: %s", repr ((path, fh)))

        if fh not in self.file_handles:
            raise fuse.FuseOSError(errno.EIO)
        
        return self.file_handles[fh].readdir ()
        
    def readlink(self, path):
        logging.debug ("readlink: %s", repr (path))
        return os.readlink (self.getSource (path))

    def release(self, path, fh):
        logging.debug ("release: %s", repr ((path, fh)))
        if fh in self.file_handles:
            file = self.file_handles[fh]
            found_other = False
            for f2 in self.file_handles:
                if f2 != fh and self.file_handles[f2].src_path == file.src_path:
                    found_other = True
                    break
                
            if not found_other:
                #logging.debug ("remove file %s from copy on write list", file.src_path)
                del self.files[file.src_path]

            file.close ()
            del self.file_handles[fh]

        return 0

    def releasedir(self, path, fh):
        logging.debug ("releasedir: %s", repr ((path, fh)))
        if fh in self.file_handles:
            file = self.file_handles[fh]
            found_other = False
            for f2 in self.file_handles:
                if f2 != fh and self.file_handles[f2].src_path == file.src_path:
                    found_other = True
                    break
                
            if not found_other:
                del self.files[file.src_path]

            file.close ()
            del self.file_handles[fh]

        return 0

    def removexattr(self, path, name):
        logging.debug ("removexattr: %s", repr ((path, name)))
        src_path = self.getSource (path)
        
        if name == xattr_revisions_name:
            raise (fuse.FuseOSError (errno.EACCES))

        file_info = FileInfo ()
        if src_path in self.files:
            file_info = self.files
        else:
            file_info.loadFileInfo (src_path)
            
        if name == xattr_max_revisions_name:
            if file_info.revisions != max_revisions:
                if max_revisions < file_info.revisions:
                    file_info.setMaxRevisions (revisions)
                    f = File (src_path, os.path.isdir (src_path, follow_symlinks=False))
                    f.limitRevisions (file_info)
                else:
                    file_info.setMaxRevisions (revisions)
                        
                file_info.saveFileInfo (src_path)
            return

        if name == xattr_max_revision_age:
            if file_info.max_age != max_revision_age:
                if max_revision_age < file_info.max_age:
                    file_info.setMaxRevisionAge (max_revision_age)
                    f = File (src_path, os.path.isdir (src_path, follow_symlinks=False))
                    f.limitRevisions (file_info)
                else:
                    file_info.setMaxRevisionAge (max_revision_age)

                file_info.saveFileInfo (src_path)
            return

        if name == xattr_min_revisions_age:
            if file_info.min_revisions != min_revisions_age:
                if min_revisions_age < file_info.min_revisions:
                    file_info.setMinRevisionsAge (min_revisions_age)
                    f = File (src_path, os.path.isdir (src_path, follow_symlinks=False))
                    f.limitRevisions (file_info)
                else:
                    file_info.setMinRevisionsAge (min_revisions_age)
                    
                file_info.saveFileInfo (src_path)
            return

        os.removexattr (src_path, name, follow_symlinks=False)

    def rename(self, old, new):
        logging.debug ("rename: %s", repr ((old, new)))
        src_new = self.getSource (new)
        if os.path.lexists (src_new):
            self.copyOnWrite (File (src_new, is_dir=not os.path.islink (src_new) and os.path.isdir (src_new)), use_rename = True)
            
        os.rename (self.getSource (old), src_new)

    def rmdir(self, path):
        logging.debug ("rmdir: %s", repr (path))

        src_path = self.getSource (path)
        
        if not os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.ENOENT)
        
        if os.path.islink (src_path) or not os.path.isdir (src_path):
            raise fuse.FuseOSError (errno.ENOTDIR)

        dirlist = os.listdir (src_path)
        for f in dirlist:
            #print ("check ", repr (f))
            if not f.startswith (revision_prefix) or f.startswith (revision_escape_prefix):
                raise fuse.FuseOSError (errno.ENOTEMPTY)
        
        f = File (src_path, True)
        self.copyOnWrite (f, use_rename=True)
        #os.rmdir (src_path)

    def setxattr(self, path, name, value, options, position=0):
        logging.debug ("setxattr: %s", repr ((path, name, value, options, position)))
        src_path = self.getSource (path)
        
        if name == xattr_revisions_name:
            raise fuse.FuseOSError (errno.EACCES)

        v = 0
        try:
            v = int (value)
        except ValueError:
            raise fuse.FuseOSError (errno.EINVAL)
        
        file_info = FileInfo ()
        if src_path in self.files:
            file_info = self.files
        else:
            file_info.loadFileInfo (src_path)
        
        src_is_dir = not os.path.islink (src_path) and os.path.isdir (src_path)
        if name == xattr_max_revisions_name:
            if file_info.revisions != v:
                logging.debug ("  changing number of revisions for %s from %d to %d", repr (path), file_info.revisions, v)                    

                if v < file_info.revisions:
                    file_info.setMaxRevisions (v)
                    f = File (src_path, src_is_dir)
                    f.limitRevisions (file_info)
                else:
                    file_info.setMaxRevisions (v)

                file_info.saveFileInfo (src_path)
                
            return

        if name == xattr_max_revision_age:
            if file_info.max_age != v:
                logging.debug ("  changing maximal revision age for %s from %d to %d days", repr (path), file_info.max_age, v)                    

                if v < file_info.max_age:
                    file_info.setMaxRevisionAge (v)
                    f = File (src_path, src_is_dir)
                    f.limitRevisions (file_info)
                else:
                    file_info.setMaxRevisionAge (v)
                    
                file_info.saveFileInfo (src_path)
                
            return

        if name == xattr_min_revisions_age:
            if file_info.min_revisions != v:
                logging.debug ("  changing minimal number of revisions for %s from %d to %d", repr (path), file_info.min_revisions, v)                    

                if v < file_info.min_revisions:
                    file_info.setMinRevisionsAge (v)
                    f = File (src_path, src_is_dir)
                    f.limitRevisions (file_info)
                else:
                    file_info.setMinRevisionsAge (v)

                file_info.saveFileInfo (src_path)
                
            return

        os.setxattr (src_path, name, value, options, follow_symlinks=False)

    def statfs(self, path):
        '''
        Returns a dictionary with keys identical to the statvfs C structure of
        statvfs(3).

        On Mac OS X f_bsize and f_frsize must be a power of 2
        (minimum 512).
        '''

        logging.debug ("statfs: %s", repr (path))
        r = os.statvfs (self.getSource (path))
        #logging.debug ("  result: %s", repr (r))
        return {"f_bsize"  : r.f_bsize,    # Filesystem block size
                "f_frsize" : r.f_frsize,   # Fragment size
                "f_blocks" : r.f_blocks,   # Size of fs in f_frsize units
                "f_bfree"  : r.f_bfree,    # Number of free blocks
                "f_bavail" : r.f_bavail,   # Number of free blocks for unprivileged users
                "f_files"  : r.f_files,    # Number of inodes
                "f_ffree"  : r.f_ffree,    # Number of free inodes
                "f_favail" : r.f_favail,   # Number of free inodes for unprivileged users
                "f_flag"   : r.f_flag,     # Mount flags
                "f_namemax": r.f_namemax } # Maximum filename length

    def symlink(self, target, source):
        'creates a symlink `target -> source` (e.g. ln -s source target)'

        logging.debug ("symlink: %s", repr ((target, source)))
        os.symlink (source, self.getSource (target))

    def truncate(self, path, length, fh=None):
        logging.debug ("truncate: %s", repr ((path, length, fh)))
        
        f = None
        
        if fh == None:
            #print ("  closed file")
            src_path = self.getSource (path)
        
            if not os.path.exists (src_path):
                raise fuse.FuseOSError (errno.ENOENT)

            if os.path.isdir (src_path):
                raise fuse.FuseOSError (errno.EISDIR)
        
            f = File (src_path, False)
        else:
            #print ("  file handle ", fh)
            if fh not in self.file_handles:
                raise fuse.FuseOSError (errno.ENOENT)
            
            f = self.file[fh]
            if f.is_dir:
                raise fuse.FuseOSError (errno.EISDIR)
        
        self.copyOnWrite (f)
        #print ("truncate file ", repr (f.src_path))
        os.truncate (f.src_path, length)

    def unlink(self, path):
        logging.debug ("unlink: %s", repr (path))
        src_path = self.getSource (path)
        
        if not os.path.lexists (src_path):
            raise fuse.FuseOSError (errno.ENOENT)

        if not os.path.islink (src_path) and os.path.isdir (src_path):
            raise fuse.FuseOSError (errno.EISDIR)
        
        f = File (src_path, False)
        self.copyOnWrite (f, use_rename=True)
        #os.unlink (src_path, follow_symlinks=False)
        
    def utimens(self, path, times=None):
        'Times is a (atime, mtime) tuple. If None use current time.'

        logging.debug ("utimens: %s", repr ((path, times)))
        if times == None: 
            os.utime (self.getSource (path))
        else:
            (atime, mtime) = times
            os.utime (self.getSource (path), (atime, mtime), follow_symlinks=False)
        return 0

    def write(self, path, data, offset, fh):
        logging.debug ("write: %s", repr ((path, data, offset, fh)))

        if fh not in self.file_handles:
            raise fuse.FuseOSError(errno.EIO)

        f = self.file_handles[fh]
        
        self.copyOnWrite (f)

        return f.write (data, offset)

def StartFuseFS ():
    parser = argparse.ArgumentParser ( #prog='FuseMirrorFS.py',
                                      description='A revisioned filesystem which stores all content and revisions in another directory.')
    parser.add_argument ('source_dir', metavar='source',
                         help='the source directory where the files and revisions will be stored')
    parser.add_argument ('mount_dir', metavar='target',
                         help='the directory where to mount the source directory to')
    parser.add_argument ('-f', dest='foreground', action='store_true',
                         help='run in foreground (default: run in background)')
    parser.add_argument ('-v', dest='verbose', action='count',
                         help='show more information, can be used several times to get even more information')
    parser.add_argument ('-l', dest='log_file',
                         help='log file. Default: {0} or stderr when -f is given'.format (log_file))

    args = parser.parse_args()
    
    #print (repr (args))
    
    if args.verbose == None:
        log_level = logging.ERROR
    elif args.verbose == 1:
        log_level = logging.WARNING
    elif args.verbose == 2:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
        
    logger = logging.getLogger ()
    logger.setLevel (log_level)
    
    ch = logging.StreamHandler ()
    if args.log_file != None:
        ch = logging.FileHandler (args.log_file)
    elif not args.foreground:
        ch = logging.FileHandler (log_file)
        
    ch.setLevel (log_level)
    logger.addHandler (ch)
    
    if args.foreground:
        logger.info ("Running in foreground...")

    logger.info ("Mounting %s on %s", args.source_dir, args.mount_dir)

    rev_fs = RevisionFS (args.source_dir)
    fuse.FUSE (rev_fs, args.mount_dir, foreground=args.foreground)

if __name__ == "__main__":
    StartFuseFS ()

