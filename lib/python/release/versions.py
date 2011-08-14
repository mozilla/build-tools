import re

from build.versions import ANY_VERSION_REGEX

def getPrettyVersion(version):
    version = re.sub(r'a([0-9]+)$', r' Alpha \1', version)
    version = re.sub(r'b([0-9]+)$', r' Beta \1', version)
    version = re.sub(r'rc([0-9]+)$', r' RC \1', version)
    return version

def getL10nDashboardVersion(version, product):
    if product == 'firefox':
        ret = 'fx'
    elif product == 'fennec':
        ret = 'fennec'
    elif product == 'thunderbird':
        ret = 'tb'
    elif product == 'seamonkey':
        ret = 'sea'

    parsed = re.match(ANY_VERSION_REGEX, version)
    if parsed.group(1) and parsed.group(1).startswith('b'):
        ret = '%s%s_beta_%s' % (ret, version[0], parsed.group(1))
    else:
        ret += version
    return ret
