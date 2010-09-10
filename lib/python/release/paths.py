def makeCandidatesDir(product, version, buildNumber, nightlyDir='nightly',
                      protocol=None, server=None):
    if protocol:
        assert server is not None, "server is required with protocol"

    dir = '/pub/mozilla.org/' + product + '/' + nightlyDir + '/' + \
          str(version) + '-candidates/build' + str(buildNumber) + '/'

    if protocol:
        return protocol + '://' + server + '' + dir
    else:
        return dir
