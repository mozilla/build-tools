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
# Portions created by the Initial Developer are Copyright (C) 2006
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

import os.path
import os
from Mozilla.CompareLocales import defaultdict

class Modules(dict):
  '''
  Subclass of dict to hold information on which directories belong to a
  particular app.
  It expects to have mozilla/client.mk right there from the working dir,
  and asks that for the LOCALES_foo variables.
  This only works for toolkit applications, as it's assuming that the
  apps include toolkit.
  '''
  def __init__(self, apps):
    super(dict, self).__init__()
    lapps = apps[:]
    lapps.insert(0, 'toolkit')
    of  = os.popen('make -f mozilla/client.mk ' + \
                   ' '.join(['echo-variable-LOCALES_' + app for app in lapps]))
    
    for val in of.readlines():
      self[lapps.pop(0)] = val.strip().split()
    for k,v in self.iteritems():
      if k == 'toolkit':
        continue
      self[k] = [d for d in v if d not in self['toolkit']]

class Components(dict):
  '''
  Subclass of dict to map module dirs to applications. This reverses the
  mapping you'd get from a Modules class, and it in fact uses one to do
  its job.
  '''
  def __init__(self, apps):
    modules = Modules(apps)
    for mod, lst in modules.iteritems():
      for c in lst:
        self[c] = mod

def allLocales(apps):
  '''
  Get a locales hash for the given list of applications, mapping
  applications to the list of languages given by all-locales.
  Adds a module 'toolkit' holding all languages for all applications, too.
  '''
  locales = {}
  all = {}
  for app in apps:
    path = 'mozilla/%s/locales/all-locales' % app
    locales[app] = [l.strip() for l in open(path)]
    all.update(dict.fromkeys(locales[app]))
  locales['toolkit'] = all.keys()
  return locales

class File(object):
  def __init__(self, fullpath, file, module = None, locale = None):
    self.fullpath = fullpath
    self.file = file
    self.module = module
    self.locale = locale
    pass
  def getContents(self):
    return open(self.fullpath).read()
  def __hash__(self):
    f = self.file
    if self.module:
      f = self.module + '/' + f
    return hash(f)
  def __str__(self):
    return self.fullpath
  def __cmp__(self, other):
    if not isinstance(other, File):
      raise NotImplementedError
    rv = cmp(self.module, other.module)
    if rv != 0:
      return rv
    return cmp(self.file, other.file)

class EnumerateDir(object):
  ignore_dirs = ['CVS', '.svn', '.hg']
  def __init__(self, basepath, module = None, locale = None):
    self.basepath = basepath
    self.module = module
    self.locale = locale
    pass
  def cloneFile(self, other):
    '''
    Return a File object that this enumerator would return, if it had it.
    '''
    return File(os.path.normpath('/'.join([self.basepath, other.file])),
                                 other.file,
                                 self.module, self.locale)
  def __iter__(self):
    dirs = [os.curdir]
    while dirs:
      dir = dirs.pop(0)
      if not os.path.isdir(self.basepath + '/' + dir):
        continue
      entries = os.listdir(self.basepath + '/' + dir)
      entries.sort()
      for entry in entries:
        if os.path.isdir('/'.join([self.basepath, dir, entry])):
          if entry not in self.ignore_dirs:
            dirs.append(dir + '/' + entry)
          continue
        yield File(os.path.normpath('/'.join([self.basepath, dir, entry])), 
                   os.path.normpath(dir + '/' + entry),
                   self.module, self.locale)

class LocalesWrap(object):
  def __init__(self, base, module, locales):
    self.base = base
    self.module = module
    self.locales = locales
  def __iter__(self):
    for locale in self.locales:
      path = self.base + '/' + get_base_path(self.module, locale)
      yield (locale, EnumerateDir(path, self.module, locale))

class EnumerateApp(object):
  echo_var = 'make -f mozilla/client.mk echo-variable-LOCALES_%s'
  filterpath = 'mozilla/%s/locales/filter.py'
  reference =  'en-US'
  def __init__(self, basepath = os.curdir, l10nbase = None):
    self.modules=defaultdict(dict)
    self.basepath = os.path.abspath(basepath)
    if l10nbase is None:
      l10nbase = self.basepath
    self.l10nbase = os.path.abspath(l10nbase)
    self.filters = []
    pass
  def addApplication(self, app, locales = None):
    cwd = os.getcwd()
    os.chdir(self.basepath)
    try:
      modules = os.popen(self.echo_var % app).read().strip().split()
      if not locales:
        locales = allLocales([app])[app]
      # get filters
      self.addFilterFrom(self.filterpath % app)
    finally:
      os.chdir(cwd)
    for mod in modules:
      self.modules[mod].update(dict.fromkeys(locales))
  def addFilterFrom(self, filterpath):
    if not os.path.exists(filterpath):
      return
    l = {}
    execfile(filterpath, {}, l)
    if 'test' not in l or not callable(l['test']):
      # XXX error handling?
      return
    self.filters.append(l['test'])
  def filter(self, l10n_file, entity = None):
    for f in self.filters:
      try: 
        if not f(l10n_file.module, l10n_file.file, entity):
          return False
      except:
        # XXX error handling
        continue
    return True
  def __iter__(self):
    '''
    Iterate over all modules, return en-US directory enumerator, and an
    iterator over all locales in each iteration. Per locale, the locale
    code and an directory enumerator will be given.
    '''
    modules = self.modules.keys()
    modules.sort()
    for mod in modules:
      locales = self.modules[mod].keys()
      locales.sort()
      base = self.basepath
      yield (mod,
             EnumerateDir(base + '/' + get_base_path(mod, self.reference),
                          mod, self.reference),
             LocalesWrap(self.l10nbase, mod, locales))

def get_base_path(mod, loc):
  'statics for path patterns and conversion'
  __l10n = 'l10n/%(loc)s/%(mod)s'
  __en_US = 'mozilla/%(mod)s/locales/en-US'
  if loc == 'en-US':
    return __en_US % {'mod': mod}
  return __l10n % {'mod': mod, 'loc': loc}

def get_path(mod, loc, leaf):
  return get_base_path(mod, loc) + '/' + leaf

