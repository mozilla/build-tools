import re

from build.versions import ANY_VERSION_REGEX


def getAppVersion(version):
    return re.match(ANY_VERSION_REGEX, version).group(1)
