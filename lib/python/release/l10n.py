import sys
from urllib2 import urlopen
from urlparse import urljoin

def getShippedLocales(product, version, buildNumber, sourceRepo,
                      hg='http://hg.mozilla.org', verbose=False):
    tag = '%s_%s_BUILD%s' % (product.upper(), version.replace('.', '_'),
                             str(buildNumber))
    file = '%s/raw-file/%s/browser/locales/shipped-locales' % \
      (sourceRepo, tag)
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
