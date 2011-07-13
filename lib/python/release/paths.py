from urlparse import urlunsplit

def makeCandidatesDir(product, version, buildNumber, nightlyDir=None,
                      protocol=None, server=None):
    if protocol:
        assert server is not None, "server is required with protocol"

    # Fennec files are uploaded to mobile/candidates instead of
    # fennec/nightly
    if product == 'fennec':
        product = 'mobile'
        if not nightlyDir:
            nightlyDir = 'candidates'

    if not nightlyDir:
        nightlyDir = 'nightly'

    dir = '/pub/mozilla.org/' + product + '/' + nightlyDir + '/' + \
          str(version) + '-candidates/build' + str(buildNumber) + '/'

    if protocol:
        return urlunsplit((protocol, server, dir, None, None))
    else:
        return dir

def makeReleasesDir(product, version, protocol=None, server=None):
    # TODO: add "devpreview" style directories
    if protocol:
        assert server is not None, "server is required with protocol"

    dir = '/pub/mozilla.org/%s/releases/%s/' % (product, version)

    if protocol:
        return urlunsplit((protocol, server, dir, None, None))
    else:
        return dir
