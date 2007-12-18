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
#	Toshihiro Kura
#	Tomoya Asai (dynamis)
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

'Mozilla l10n merge tool'

import os
import re
import codecs
import logging
import time
import shutil
import Parser
import Paths
from CompareLocales import FileCollector, CompareCollector, collectFiles

options = {}

class MergeCollector(CompareCollector):
  def addFile(self, aModule, aLocale, aLeaf):
    super(MergeCollector, self).addFile(aModule, aLocale, aLeaf)
    l_fl = Paths.get_path(aModule, aLocale, aLeaf)
    if not os.path.isdir(os.path.dirname(l_fl)):
      os.makedirs(os.path.dirname(l_fl))
    shutil.copy2(Paths.get_path(aModule, 'en-US', aLeaf), l_fl)
    pass
  def removeFile(self, aModule, aLocale, aLeaf):
    super(MergeCollector, self).removeFile(aModule, aLocale, aLeaf)
    if options['backup']:
      os.rename(Paths.get_path(aModule, aLocale, aLeaf), Paths.get_path(aModule, aLocale, aLeaf + '~'))
    else:
      os.remove(Paths.get_path(aModule, aLocale, aLeaf))
    pass

def merge(apps=None, testLocales=[]):
  result = {}
  c = MergeCollector()
  fltr = collectFiles(c, apps=apps, locales=testLocales)
  
  key = re.compile('[kK]ey')
  for fl, locales in c.cl.iteritems():
    (mod,path) = fl
    logging.info(" Handling " + path + " in " + mod)
    try:
      parser = Parser.getParser(path)
    except UserWarning:
      logging.warning(" Can't merge " + path + " in " + mod)
      continue
    parser.readFile(Paths.get_path(mod, 'en-US', path))
    logging.debug(" Parsing en-US " + path + " in " + mod)
    (enList, enMap) = parser.parse()
    for loc in locales:
      if not result.has_key(loc):
        result[loc] = {'missing':[],'obsolete':[],
                       'changed':0,'unchanged':0,'keys':0}
      enTmp = dict(enMap)
      parser.readFile(Paths.get_path(mod, loc, path))
      logging.debug(" Parsing " + loc + " " + path + " in " + mod)
      (l10nList, l10nMap) = parser.parse()
      l10nTmp = dict(l10nMap)
      logging.debug(" Checking existing entities of " + path + " in " + mod)
      for k,i in l10nMap.items():
        if not fltr(mod, path, k):
          if enTmp.has_key(k):
            del enTmp[k]
            del l10nTmp[k]
          continue
        if not enTmp.has_key(k):
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
      filename = Paths.get_path(mod, loc, path)
      if not parser.canMerge:
        if l10nTmp or enTmp:
          logging.error('not merging ' + path)
        continue
      # comment out obsolete entities
      if l10nTmp != {}:
        logging.info(" Commenting out obsolete entities...")
        f = codecs.open(filename, 'w', parser.encoding)
        daytime = time.asctime()
        try:
          f.write(parser.header)
          if re.search('\\.dtd', filename):
            for entity in l10nList:
              if l10nTmp.has_key(entity['key']):
                if not options['cleanobsolete']:
                  f.write(entity['prespace'] + '<!-- XXX l10n merge: obsolete entity (' + daytime + ') -->\n' + entity['precomment'] + '<!-- ' + entity['def'] + ' -->' + entity['post'])
              else:
                f.write(entity['all'])
          elif re.search('\\.(properties|inc)', filename):
            for entity in l10nList:
              if l10nTmp.has_key(entity['key']):
                if not options['cleanobsolete']:
                  f.write(entity['prespace'] + '# XXX l10n merge: obsolete entity (' + daytime + ')\n' + entity['precomment'] + '#' + entity['def'] + entity['post'])
              else:
                f.write(entity['all'])
          f.write(parser.footer)
        except UnicodeDecodeError, e:
          logging.getLogger('locales').error("Can't write file: " + file + ';' + str(e))
        f.close()
      # add new entities
      if enTmp != {}:
        logging.info(" Adding new entities...")
        f = codecs.open(filename, 'a', parser.encoding)
        daytime = time.asctime()
        try:
          if re.search('\\.dtd', filename):
            f.write('\n<!-- XXX l10n merge: new entities (' + daytime + ') -->\n')
            v = enTmp.values()
            v.sort()
            for i in v:
              f.write(enList[i]['all'])
          elif re.search('\\.(properties|inc)', filename):
            f.write('\n# XXX l10n merge: new entities (' + daytime + ')\n')
            v = enTmp.values()
            v.sort()
            for i in v:
              f.write(enList[i]['all'])
        except UnicodeDecodeError, e:
          logging.getLogger('locales').error("Can't write file: " + file + ';' + str(e))
        f.close()
  for loc,dics in c.files.iteritems():
    if not result.has_key(loc):
      result[loc] = dics
    else:
      for key, list in dics.iteritems():
        result[loc][key] = list
  for loc, mods in c.modules.iteritems():
    result[loc]['tested'] = mods
  return result
