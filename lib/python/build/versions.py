import re

class BuildVersionsException(Exception):
    pass

# Versions that match this should not be bumped
DO_NOT_BUMP_REGEX = '^\d\.\d(pre)?$'

# Regex that matches all possible versions and milestones
ANY_VERSION_REGEX =\
    ('\d+\.\d[\d\.]*'    # A version number
    '([a-zA-Z]+\d+)?'    # Might be a project branch
    '((a|b)\d+)?'        # Might be an alpha or beta
    '(pre)?')            # Might be a 'pre' (nightly) version

BUMP_FILES = {
    '^.*(version.*\.txt|milestone\.txt)$': '^%(version)s$',
    '^.*(default-version\.txt|confvars\.sh)$': '^MOZ_APP_VERSION=%(version)s$'
}

def bumpFile(filename, contents, version):
    # First, find the right regex for this file
    newContents = []
    for fileRegex, versionRegex in BUMP_FILES.iteritems():
        if re.match(fileRegex, filename):
            # Second, find the line with the version in it
            for line in contents.splitlines():
                regex = versionRegex % { 'version': ANY_VERSION_REGEX }
                match = re.match(regex, line)
                # If this is the version line, and the file doesn't have
                # the correct version, change it.
                if match and match.group() != version:
                    newContents.append(re.sub(ANY_VERSION_REGEX, version, line))
                # If it's not the version line, or the version is correct,
                # don't do anything
                else:
                    newContents.append(line)
            newContents = "\n".join(newContents)
            # Be sure to preserve trailing newlines, if they exist
            if contents.endswith("\n"):
                newContents += "\n"
            break
    if len(newContents) == 0:
        raise BuildVersionsException("Don't know how to bump %s" % filename)
    return newContents

def nextVersion(version, pre=False):
    """Returns the version directly after `version', optionally with "pre"
       appended to it."""
    if re.match(DO_NOT_BUMP_REGEX, version):
        bumped = version
    else:
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
