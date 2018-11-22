from urlparse import urlunsplit


def makeReleasesDir(product, version=None, protocol=None, server=None,
                    ftp_root='/pub/'):
    if protocol:
        assert server is not None, "server is required with protocol"

    directory = '%s%s/releases/' % (ftp_root, product)
    if version:
        directory += '%s/' % version

    if protocol:
        return urlunsplit((protocol, server, directory, None, None))
    else:
        return directory
