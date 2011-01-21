import re

def nextVersion(version, pre=False):
    """Returns the version directly after `version', optionally with "pre"
       appended to it."""
    bumped = increment(version)
    if pre:
        bumped += "pre"
    return bumped

# The following function was copied from http://code.activestate.com/recipes/442460/
# Written by Chris Olds
lastNum = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')
def increment(s):
    """ look for the last sequence of number(s) in a string and increment """
    m = lastNum.search(s)
    if m:
        next = str(int(m.group(1))+1)
        start, end = m.span(1)
        s = s[:max(end-len(next), start)] + next + s[end:]
    return s
