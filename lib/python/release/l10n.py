import sys
from urllib2 import urlopen
from urlparse import urljoin

def getShippedLocales(product, appName, version, buildNumber, sourceRepo,
                      hg='http://hg.mozilla.org', verbose=False):
    tag = '%s_%s_BUILD%s' % (product.upper(), version.replace('.', '_'),
                             str(buildNumber))
    file = '%s/raw-file/%s/%s/locales/shipped-locales' % \
      (sourceRepo, tag, appName)
    url = urljoin(hg, file)
    try:
        sl = urlopen(url).read()
    except:
        if verbose:
            print >>sys.stderr, "Failed to retrieve %s" % url
        raise
    return sl

def getCommonLocales(a, b):
    return [locale for locale in a if locale in b]

def getL10nRepositories(file, l10nRepoPath, relbranch):
    """Reads in a list of locale names and revisions for their associated
       repository from 'file'.
    """
    # urljoin() will strip the last part of l10nRepoPath it doesn't end with "/"
    if not l10nRepoPath.endswith('/'):
        l10nRepoPath = l10nRepoPath + '/'
    repositories = {}
    for localeLine in open(file).readlines():
        locale, revision = localeLine.rstrip().split()
        if revision == 'FIXME':
            raise Exception('Found FIXME in %s for locale "%s"' % \
                           (file, locale))
        locale = urljoin(l10nRepoPath, locale)
        repositories[locale] = {
            'revision': revision,
            'relbranchOverride': relbranch,
            'bumpFiles': []
        }

    return repositories

