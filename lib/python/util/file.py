"""Helper functions to handle file operations"""
import logging, os
log = logging.getLogger(__name__)

def compare(file1, file2):
    """compares the contents of two files, passed in either as
       open file handles or accessible file paths. Does a simple
       naive string comparison, so do not use on larger files"""
    if isinstance(file1, basestring):
        file1 = open(file1, 'r', True)
    if isinstance(file2, basestring):
        file2 = open(file2, 'r', True)
    file1_contents = file1.read()
    file2_contents = file2.read()
    return file1_contents == file2_contents

def directoryContains(directory, suffix):
    """ Return true if the given directory contains the provided wildcard
    suffix, similar to `ls foo/*bar` """
    hit = any([f.endswith(suffix) for f in os.listdir(directory)])
    if not hit:
        log.error("Could not find *%s in %s" % (suffix, directory))
    return hit
