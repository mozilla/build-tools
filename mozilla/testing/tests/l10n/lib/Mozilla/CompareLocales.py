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

'Mozilla l10n compare locales tool'

import os
import os.path
import re
import logging
import Parser
import Paths
try:
  from collections import defaultdict
except ImportError:
  class defaultdict(dict):
    def __init__(self, defaultclass):
      dict.__init__(self)
      self.__defaultclass = defaultclass
    def __getitem__(self, k):
      if not dict.__contains__(self, k):
        self[k] = self.__defaultclass()
      return dict.__getitem__(self, k)
    

class FileCollector:
  def __init__(self):
    pass
  def getFiles(self, mod, locale):
    fls = {}
    for leaf, path in self.iterateFiles(mod,locale):
      fls[leaf] = path
    return fls
  def iterateFiles(self, mod, locale):
    base = Paths.get_base_path(mod, locale)
    cutoff  = len(base) + 1
    for dirpath, dirnames, filenames in os.walk(base):
      try:
        # ignore CVS dirs
        dirnames.remove('CVS')
      except ValueError:
        pass
      dirnames.sort()
      filenames.sort()
      for f in filenames:
        leaf = dirpath + '/' + f
        yield (leaf[cutoff:], leaf)

def collectFiles(aComparer, apps = None, locales = None):
  '''
  returns new files, files to compare, files to remove
  apps or locales need to be given, apps is a list, locales is a
  hash mapping applications to languages.
  If apps is given, it will look up all-locales for all apps for the
  languages to test.
  'toolkit' is added to the list of modules, too.
  '''
  if not apps and not locales:
    raise RuntimeError, "collectFiles needs either apps or locales"
  if apps and locales:
    raise RuntimeError, "You don't want to give both apps or locales"
  if locales:
    apps = locales.keys()
    # add toolkit, with all of the languages of all apps
    all = {}
    for locs in locales.values():
      all.update(dict.fromkeys(locs))
    locales['toolkit'] = all.keys()
  else:
    locales = Paths.allLocales(apps)
  modules = Paths.Modules(apps)
  en = FileCollector()
  l10n = FileCollector()
  # load filter functions for each app
  fltrs = []
  for app in apps:
    filterpath = 'mozilla/%s/locales/filter.py' % app
    if not os.path.exists(filterpath):
      continue
    l = {}
    execfile(filterpath, {}, l)
    if 'test' not in l or not callable(l['test']):
      logging.debug('%s does not define function "test"' % filterpath)
      continue
    fltrs.append(l['test'])
  
  # define fltr function to be used, calling into the app specific ones
  # if one of our apps wants us to know about a triple, make it so
  def fltr(mod, lpath, entity = None):
    for f in fltrs:
      keep  = True
      try:
        keep = f(mod, lpath, entity)
      except Exception, e:
        logging.error(str(e))
      if not keep:
        return False
    return True
  
  for cat in modules.keys():
    logging.debug(" testing " + cat+ " on " + str(modules))
    aComparer.notifyLocales(cat, locales[cat])
    for mod in modules[cat]:
      en_fls = en.getFiles(mod, 'en-US')
      for loc in locales[cat]:
        fls = dict(en_fls) # create copy for modification
        for l_fl, l_path in l10n.iterateFiles(mod, loc):
          if l_fl in fls:
            # file in both en-US and locale, compare
            aComparer.compareFile(mod, loc, l_fl)
            del fls[l_fl]
          else:
            if fltr(mod, l_fl):
              # file in locale, but not in en-US, remove
              aComparer.removeFile(mod, loc, l_fl)
            else:
              logging.debug(" ignoring %s from %s in %s" %
                            (l_fl, loc, mod))
        # all locale files dealt with, remaining fls need to be added?
        for lf in fls.keys():
          if fltr(mod, lf):
            aComparer.addFile(mod,loc,lf)
          else:
            logging.debug(" ignoring %s from %s in %s" %
                          (lf, loc, mod))

  return fltr

class listdict(defaultdict):
  def __init__(self):
    defaultdict.__init__(self, list)

class CompareCollector(object):
  'collects files to be compared, added, removed'
  def __init__(self):
    self.cl = listdict()
    self.files = defaultdict(listdict)
    self.modules = listdict()
  def notifyLocales(self, aModule, aLocaleList):
    for loc in aLocaleList:
      self.modules[loc].append(aModule)
  def addFile(self, aModule, aLocale, aLeaf):
    logging.debug(" add %s for %s in %s" % (aLeaf, aLocale, aModule))
    self.files[aLocale]['missingFiles'].append((aModule, aLeaf))
    pass
  def compareFile(self, aModule, aLocale, aLeaf):
    self.cl[(aModule, aLeaf)].append(aLocale)
    pass
  def removeFile(self, aModule, aLocale, aLeaf):
    logging.debug(" remove %s from %s in %s" % (aLeaf, aLocale, aModule))
    self.files[aLocale]['obsoleteFiles'].append((aModule, aLeaf))
    pass

class resultdict(dict):
  def __init__(self):
    dict.__init__(self, {'missing':[],'obsolete':[],
                         'changed':0,'unchanged':0,'keys':0})

def compare(apps=None, testLocales=None):
  result = defaultdict(resultdict)
  c = CompareCollector()
  fltr = collectFiles(c, apps=apps, locales=testLocales)
  
  key = re.compile('[kK]ey')
  for fl, locales in c.cl.iteritems():
    (mod,path) = fl
    try:
      parser = Parser.getParser(path)
    except UserWarning:
      logging.warning(" Can't compare " + path + " in " + mod)
      continue
    parser.readFile(Paths.get_path(mod, 'en-US', path))
    logging.debug(" Parsing en-US " + path + " in " + mod)
    (enList, enMap) = parser.parse()
    for loc in locales:
      enTmp = dict(enMap)
      parser.readFile(Paths.get_path(mod, loc, path))
      logging.debug(" Parsing " + loc + " " + path + " in " + mod)
      (l10nList, l10nMap) = parser.parse()
      l10nTmp = dict(l10nMap)
      logging.debug(" Checking existing entities of " + path + " in " + mod)
      for k,i in l10nMap.items():
        if not fltr(mod, path, k):
          if k in enTmp:
            del enTmp[k]
            del l10nTmp[k]
          continue
        if k not in enTmp:
          result[loc]['obsolete'].append((mod,path,k))
          continue
        enVal = enList[enTmp[k]]['val']
        del enTmp[k]
        del l10nTmp[k]
        if key.search(k):
          result[loc]['keys'] += 1
        else:
          if enVal == l10nList[i]['val']:
            result[loc]['unchanged'] +=1
            logging.info('%s in %s unchanged' %
                         (k, Paths.get_path(mod, loc, path)))
          else:
            result[loc]['changed'] +=1
      result[loc]['missing'].extend(filter(lambda t: fltr(*t),
                                           [(mod,path,k) for k in enTmp.keys()]))
  for loc, file_results in c.files.iteritems():
    result[loc].update(file_results)
  for loc, mods in c.modules.iteritems():
    result[loc]['tested'] = mods
  return result

# helper class to merge all the lists into more consice
# dicts
class Separator:
  def __init__(self, apps):
    self.components = Paths.Components(apps)
    pass
  def getDetails(self, res, locale):
    dic = {}
    res[locale]['tested'].sort()
    self.collectList('missing', res[locale], dic)
    self.collectList('obsolete', res[locale], dic)
    return dic
  def collectList(self, name, res, dic):
    dic[name] = {}
    if name not in res:
      res[name] = []
    counts = dict([(mod,0) for mod in res['tested']])
    counts['total'] = len(res[name])
    for mod, path, key in res[name]:
      counts[self.components[mod]] +=1
      if mod not in  dic[name]:
        dic[name][mod] = {path:[key]}
        continue
      if path not in dic[name][mod]:
        dic[name][mod][path] = [key]
      else:
        dic[name][mod][path].append(key)
    res[name] = counts
    name += 'Files'
    dic[name] = {}
    if name not in res:
      res[name] = []
    counts = dict([(mod,0) for mod in res['tested']])
    counts['total'] = len(res[name])
    for mod, path in res[name]:
      counts[self.components[mod]] +=1
      if mod not in dic[name]:
        dic[name][mod] = [path]
      else:
        dic[name][mod].append(path)
    res[name] = counts
