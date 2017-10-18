#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
import argparse
import RevFS


def ShowRevisions ():
    parser = argparse.ArgumentParser (description='Change the revision parameters of a file stored on RevisionFS.py.')
    parser.add_argument ('file_name', nargs='+',
                         help='the files to change')
    parser.add_argument ('-m', dest='max_revisions', type=int,
                         help='maximum revisions stored for this file')
    parser.add_argument ('-a', dest='max_age', type=int,
                         help='maximum age of stored revisions for this file in days')
    parser.add_argument ('-n', dest='min_revisions', type=int,
                         help='minimum number of revisions stored for this file even if oder than max_age')

    args = parser.parse_args()

    for fname in args.file_name:
        if not RevFS.IsOnRevisionFS (fname):
            print ("{0} is not on a RevisionFS.py".format (fname))
            continue
        
        max_rev = RevFS.GetMaxRevisions (fname)
        if args.max_revisions != None:
            RevFS.SetMaxRevisions (fname, args.max_revisions)
            print ('{0}: changing max. revisions from {1} to {2}'.format (os.path.basename (fname), max_rev, args.max_revisions))
        else:
            print ('{0}: max. revisions {1}'.format (os.path.basename (fname), max_rev))
        
        min_rev = RevFS.GetMinRevisionsAge (fname)
        if args.min_revisions != None:
            RevFS.SetMinRevisionsAge (fname, args.min_revisions)
            print ('{0}: changing max. revisions from {1} to {2}'.format (os.path.basename (fname), min_rev, args.min_revisions))
        else:
            print ('{0}: max. revisions {1}'.format (os.path.basename (fname), min_rev))
        
        max_age = RevFS.GetMaxRevisionAge (fname)
        if args.max_age != None:
            RevFS.SetMaxRevisionAge (fname, args.max_age)
            print ('{0}: changing max. age from {1} to {2} days'.format (os.path.basename (fname), max_age, args.max_age))
        else:
            print ('{0}: max. age {1} days'.format (os.path.basename (fname), max_age))

if __name__ == "__main__":
    ShowRevisions ()

