#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
import re
import datetime

xattr_max_revisions_name = "user.revfs_max_revisions"
xattr_revisions_name     = "user.revfs_revisions"
xattr_max_revision_age   = "user.revfs_max_age"
xattr_min_revisions_age  = "user.revfs_min_revisions"

def SplitRevisionString (revisions):
    s_pattern = r"\(([^,]+,[^,]+,[^,]+)\)"
    pattern = re.compile (s_pattern)
    res = pattern.match (revisions)

    if res:
        yield res.group (1)
        
        s_pattern = ',' + s_pattern
        pattern = re.compile (s_pattern)
        
        while True:
            next_idx = res.end ()
            res = pattern.match (revisions, next_idx)
            if res:
                yield res.group (1)
            else:
                break

def IsOnRevisionFS (fname):
    xattribs = os.listxattr (fname, follow_symlinks=False)
    return xattr_max_revisions_name in xattribs

def GetMaxRevisions (fname):
    s_max_revisions = os.getxattr (fname, xattr_max_revisions_name, follow_symlinks=False)
    max_revisions = 10
    try:
        max_revisions = int (s_max_revisions)
    except ValueError:
        pass
    return max_revisions

def SetMaxRevisions (fname, max_revisions):
    os.setxattr (fname, xattr_max_revisions_name, str (max_revisions).encode ('ASCII'), follow_symlinks=False)

def GetMaxRevisionAge (fname):
    s_max_revision_age = os.getxattr (fname, xattr_max_revision_age, follow_symlinks=False)
    max_revision_age = 185
    try:
        max_revision_age = int (s_max_revision_age)
    except ValueError:
        pass
    return max_revision_age

def SetMaxRevisionAge (fname, max_age):
    os.setxattr (fname, xattr_max_revision_age, str (max_age).encode ('ASCII'), follow_symlinks=False)

def GetMinRevisionsAge (fname):
    s_min_revisions_age = os.getxattr (fname, xattr_min_revisions_age, follow_symlinks=False)
    min_revisions_age = 1
    try:
        min_revisions_age = int (s_min_revisions_age)
    except ValueError:
        pass
    return min_revisions_age

def SetMinRevisionsAge (fname, min_revisions_age):
    os.setxattr (fname, xattr_min_revisions_age, str (min_revisions_age).encode ('ASCII'), follow_symlinks=False)

class RevisionInfo:
    def __init__ (self, revision, size, date):
        self.revision = revision
        self.size = size
        self.date = date

def GetRevisionInfos (fname):
    rev_list = []

    info=os.getxattr (fname, xattr_revisions_name, follow_symlinks=False)
    
    if info == b'':
        return rev_list

    s_info = info.decode ('ASCII')
    for rev in SplitRevisionString (s_info):
        s_revision, s_date, s_size = rev.split (',')
        try:
            revision = int (s_revision)
            size = int (s_size)
            date = datetime.datetime.strptime (s_date, '%Y-%m-%d %H:%M:%S.%f')
            rev_list.append (RevisionInfo (revision, size, date))
            
        except ValueError:
            pass
        
    return rev_list



if __name__ == "__main__":
    pass

