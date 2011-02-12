import os
from twisted.web import static

def makeRootResource():
    # root corresponds to slavealloc/www
    wwwdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "www"))
    root = static.File(wwwdir)

    # serve 'index.html' at the root
    root.putChild('', static.File(os.path.join(wwwdir, 'index.html')))

    return root
