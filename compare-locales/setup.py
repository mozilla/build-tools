"""Python library and scripts to assist in localizing Mozilla applications

Localization of XUL applications in general and Mozilla applications in
particular are done by a number of different file formats. Independent
of the format, the Mozilla architecture does not provide fallback strings
at runtime. This library and the calling scripts provide a way to check
a given localization for completeness. For more information see
http://developer.mozilla.org/en/docs/Compare-locales
"""

docstrings = __doc__.split("\n")

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages
import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from Mozilla import version

classifiers = """\
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: GNU General Public License (GPL)
License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)
License :: OSI Approved :: Mozilla Public License 1.1 (MPL 1.1)
Operating System :: OS Independent
Programming Language :: Python
Topic :: Software Development :: Libraries :: Python Modules
Topic :: Software Development :: Localization
Topic :: Software Development :: Testing
"""

from setuptools import Command
import glob

class web(Command):
  description = 'install web files'
  user_options = [('target=','d','base directory for installation')]
  
  def initialize_options(self):
    self.target = None
    pass
  def finalize_options(self):
    pass
  def run(self):
    self.ensure_dirname('target')
    for f in glob.glob('web/*.*'):
      if f.find('/CVS') >=0 or f.find('~') >= 0:
        continue
      self.copy_file(f, self.target)

setup(name="compare-locales",
      version=version,
      author="Axel Hecht",
      author_email="axel@mozilla.com",
      description=docstrings[0],
      long_description="\n".join(docstrings[2:]),
      license="MPL 1.1/GPL 2.0/LGPL 2.1",
      url="http://developer.mozilla.org/en/docs/Compare-locales",
      classifiers=filter(None, classifiers.split("\n")),
      platforms=["any"],
      scripts=['scripts/compare-locales',
               'scripts/compare-dirs',
               'scripts/test-locales',
               'scripts/verify-rss-redirects'],
      package_dir={'': 'lib'},
      packages=['Mozilla'],
      cmdclass={'web': web}
      )
