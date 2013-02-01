from os import path

from release.platforms import ftp2updatePlatforms, ftp_update_platform_map

SCHEMA_2_OPTIONAL_ATTRIBUTES_SINGLE_VALUE = (
    'showPrompt', 'showNeverForVersion', 'showSurvey', 'licenseUrl',
    'billboardURL', 'openURL', 'notificationURL', 'alertURL', 'promptWaitTime',
)
SCHEMA_2_OPTIONAL_ATTRIBUTES_MULTI_VALUE = ('actions',)
SCHEMA_2_OPTIONAL_ATTRIBUTES = SCHEMA_2_OPTIONAL_ATTRIBUTES_SINGLE_VALUE + \
    SCHEMA_2_OPTIONAL_ATTRIBUTES_MULTI_VALUE

schema1_snippet_template = """\
version=%(schema)s
type=%(type)s
url=%(url)s
hashFunction=%(hashFunction)s
hashValue=%(hash)s
size=%(size)s
build=%(buildid)s
appv=%(displayVersion)s
extv=%(appVersion)s
detailsUrl=%(detailsUrl)s
"""

schema2_snippet_template = """\
version=%(schema)s
type=%(type)s
url=%(url)s
hashFunction=%(hashFunction)s
hashValue=%(hash)s
size=%(size)s
build=%(buildid)s
displayVersion=%(displayVersion)s
appVersion=%(appVersion)s
platformVersion=%(appVersion)s
detailsUrl=%(detailsUrl)s"""


class SnippetError(ValueError):
    pass


def createSnippet(schema, type_, url, hash_, size, buildid, displayVersion, appVersion, detailsUrl, hashFunction='SHA512', **other):
    """Creates an AUS snippet based on the given information. Schema 2 snippets
       support all of the optional attributes listed in
       SCHEMA_2_OPTIONAL_ATTRIBUTES."""
    hashFunction = hashFunction.upper()
    subs = {
        'schema': schema,
        'type': type_,
        'url': url,
        'hashFunction': hashFunction,
        'hash': hash_,
        'size': size,
        'buildid': buildid,
        'displayVersion': displayVersion,
        'appVersion': appVersion,
        'detailsUrl': detailsUrl
    }
    if schema == 1:
        if other:
            raise SnippetError(
                "Optional attributes are not supported for schema version 1")
        return schema1_snippet_template % subs
    elif schema == 2:
        for k in other:
            if k not in SCHEMA_2_OPTIONAL_ATTRIBUTES:
                raise SnippetError("Invalid optional attribute: '%s'" % k)
        snippet = schema2_snippet_template % subs
        # Sorting gives us predictable ordering, making this easier to test.
        for k, v in sorted(other.items()):
            # The 'actions' attribute needs to be a space separated list
            if k == 'actions':
                v = " ".join(v)
            snippet += "\n%s=%s" % (k, v)
        return snippet + "\n"
    else:
        raise SnippetError("Unsupported schema version '%d'" % schema)


def getSnippetPaths(product, version, platform, buildid, locale, channel, type_):
    """Returns a list of all of the snippets that should be created for the
       given inputs. The platform given must be an FTP platform and will be
       translated to one or more update platforms."""
    paths = []
    if platform not in ftp_update_platform_map:
        raise SnippetError("Unknown platform '%s'" % platform)
    for updatePlatform in ftp2updatePlatforms(platform):
        paths.append(path.join(product, version, updatePlatform, str(buildid), locale, channel, '%s.txt' % type_)
                     )
    return paths
