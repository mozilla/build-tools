# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is l10n test automation.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation
# Portions created by the Initial Developer are Copyright (C) 2007
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#	Axel Hecht <l10n@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

from zipfile import ZipFile
from difflib import SequenceMatcher
import os.path
import re

from Paths import File
import CompareLocales

class JarEntry(File):
  def __init__(self, zf, file, fakefile):
    File.__init__(self, None, fakefile)
    self.realfile = file
    self.zipfile = zf
  def __str__(self):
    return self.zipfile.filename + '!' + self.realfile
  def getContents(self):
    return self.zipfile.read(self.realfile)

class EnumerateJar(object):
  def __init__(self, basepath):
    basepath = os.path.abspath(basepath)
    if not basepath.endswith('.jar'):
      raise RuntimeError("Only jar files supported")
    self.basepath = basepath
    # best guess we have on locale code
    self.locale = os.path.split(basepath)[1].replace('.jar','')
    self.zf = ZipFile(basepath, 'r')
  def cloneFile(self, other):
    return JarEntry(self.zf, other.realfile, other.file)
  def __iter__(self):
    # get all entries, drop those ending with '/', those are dirs.
    files = [f for f in self.zf.namelist() if not f.endswith('/')]
    files.sort()
    # unfortunately, we have to fake file paths of the form
    # locale/AB-CD/
    # for comparison.
    # For real, the corresponding manifest would tell us. Whichever.
    localesub = re.compile('^locale/' + self.locale)
    for f in files:
      yield JarEntry(self.zf, f, localesub.sub('locale/@AB_CD@', f))

def compareJars(ref, l10n):
  cc = CompareLocales.ContentComparer()
  o  = CompareLocales.Observer()
  cc.add_observer(o)
  dc = CompareLocales.DirectoryCompare(EnumerateJar(ref))
  dc.setWatcher(cc)
  dc.compareWith(EnumerateJar(l10n))
  return o
