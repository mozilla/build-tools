def getLatestDir(product, branch, platform, nightlyDir="nightly",
                 protocol=None, server=None):
    if protocol:
        assert server is not None, "server is required with protocol"

    dirpath = "/pub/mozilla.org/" + product + "/" + nightlyDir + "/" + \
              "latest-" + branch + "-" + platform

    if protocol:
        return protocol + "://" + server + dirpath
    else:
        return dirpath


def getSnippetDir(brandName, version, buildNumber):
    return '%s-%s-build%s' % (brandName, version, buildNumber)


def getMUSnippetDir(brandName, oldVersion, oldBuildNumber, version,
                    buildNumber):
    return '%s-%s-build%s-%s-build%s-MU' % (brandName, oldVersion,
                                            oldBuildNumber, version,
                                            buildNumber)
