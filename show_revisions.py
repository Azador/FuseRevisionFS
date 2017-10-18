#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
import argparse
import RevFS


def HumanReadable (v):
    if v < 1024:
        return str (v)
    
    v = v / 1024.0
    if v < 1024:
        if v < 100:
            return "{0:.1f} KB".format (v)

        return "{0:.0f} KB".format (v)
    
    v /= 1024.0
    if v < 1024:
        if v < 100:
            return "{0:.1f} MB".format (v)

        return "{0:.0f} MB".format (v)
    
    v /= 1024.0
    if v < 100:
        return "{0:.1f} GB".format (v)

    return "{0:.0f} GB".format (v)
    
def ShowRevisions ():
    parser = argparse.ArgumentParser (description='Show revisions of a file stored on RevisionFS.py.', add_help=False)
    parser.add_argument ('file_name', nargs='+',
                         help='the file name to check')
    parser.add_argument ('-h', dest='human_readable', action='store_true',
                         help='display sizes human readable')

    args = parser.parse_args()

    human_readable = args.human_readable

    for fname in args.file_name:
        if not RevFS.IsOnRevisionFS (fname):
            print ("{0} is not on a RevisionFS.py".format (os.path.basename (fname)))
            continue
        
        max_revisions = RevFS.GetMaxRevisions (fname)
        max_revision_age = RevFS.GetMaxRevisionAge (fname)
        min_revisions_age = RevFS.GetMinRevisionsAge (fname)

        revisions = RevFS.GetRevisionInfos (fname)

        if revisions == []:
            print ('{0}: max. revisions {1}, max. age {2} days, min. revisions {3}, no revisions exist' \
                   .format (os.path.basename (fname), max_revisions, max_revision_age, min_revisions_age))
        else:
            rev_nr_len = 0
            date_len = 0
            size_len = 0
            rev_list = []
            for rev in revisions:
                s_revision = str (rev.revision)
                s_size = str (rev.size)
                if human_readable:
                    s_size = HumanReadable (rev.size)
    
                s_date = rev.date.strftime ('%c')
                rev_nr_len = max (rev_nr_len, len (s_revision))
                size_len = max (size_len, len (s_size))
                date_len = max (date_len, len (s_date))
                rev_list.append ((s_revision, s_size, s_date))
            
            print ('{0}: max. revisions {1}, max. age {2} days, min. revisions {3}' \
                   .format (os.path.basename (fname), max_revisions, max_revision_age, min_revisions_age))
            for rev in rev_list:
                print ('  {0:>{align_id}}: {1:>{align_size}}  {2}'.format (rev[0], rev[1], rev[2],
                                                                          align_id=rev_nr_len, align_size=size_len))

if __name__ == "__main__":
    ShowRevisions ()

