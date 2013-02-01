from urlparse import urlunsplit


def makeCandidatesDir(product, version, buildNumber, nightlyDir=None,
                      protocol=None, server=None, ftp_root='/pub/mozilla.org/'):
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

    directory = ftp_root + product + '/' + nightlyDir + '/' + \
        str(version) + '-candidates/build' + str(buildNumber) + '/'

    if protocol:
        return urlunsplit((protocol, server, directory, None, None))
    else:
        return directory


def makeReleasesDir(product, version=None, protocol=None, server=None,
                    ftp_root='/pub/mozilla.org/'):
    if protocol:
        assert server is not None, "server is required with protocol"

    directory = '%s%s/releases/' % (ftp_root, product)
    if version:
        directory += '%s/' % version

    if protocol:
        return urlunsplit((protocol, server, directory, None, None))
    else:
        return directory
