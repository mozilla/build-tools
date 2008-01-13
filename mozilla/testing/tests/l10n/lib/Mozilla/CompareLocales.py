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
from difflib import SequenceMatcher
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

import Parser
import Paths

class Tree(object):
  def __init__(self, valuetype):
    self.branches = dict()
    self.valuetype = valuetype
    self.value = None
  def __getitem__(self, leaf):
    parts = []
    if isinstance(leaf, Paths.File):
      parts = [p for p in [leaf.locale, leaf.module] if p] + \
          leaf.file.split('/')
    else:
      parts = leaf.split('/')
    return self.__get(parts)
  def __get(self, parts):
    common = None
    old = None
    new = tuple(parts)
    t = self
    for k, v in self.branches.iteritems():
      for i, part in enumerate(zip(k, parts)):
        if part[0] != part[1]:
          i -= 1
          break
      if i < 0:
        continue
      i += 1
      common = tuple(k[:i])
      old = tuple(k[i:])
      new = tuple(parts[i:])
      break
    if old:
      self.branches.pop(k)
      t = Tree(self.valuetype)
      t.branches[old] = v
      self.branches[common] = t
    elif common:
      t = self.branches[common]
    if new:
      if common:
        return t.__get(new)
      t2 = t
      t = Tree(self.valuetype)
      t2.branches[new] = t
    if t.value is None:
      t.value = t.valuetype()
    return t.value
  indent = '  '
  def getContent(self, depth = 0):
    '''
    Returns iterator of (depth, flag, key_or_value) tuples.
    If flag is 'value', key_or_value is a value object, otherwise
    (flag is 'key') it's a key string.
    '''
    keys = self.branches.keys()
    keys.sort()
    if self.value is not None:
      yield (depth, 'value', self.value)
    for key in keys:
      yield (depth, 'key', key)
      for child in self.branches[key].getContent(depth + 1):
        yield child
  def toJSON(self):
    '''
    Returns this Tree as a JSON-able tree of hashes.
    Only the values need to take care that they're JSON-able.
    '''
    json = {}
    keys = self.branches.keys()
    keys.sort()
    if self.value is not None:
      json['value'] = self.value
    children = dict(('/'.join(key), self.branches[key].toJSON())
                    for key in keys)
    if children:
      json['children'] = children
    return json
  def getStrRows(self):
    def tostr(t):
      if t[1] == 'key':
        return self.indent * t[0] + '/'.join(t[2])
      return self.indent * (t[0] + 1) + str(t[2])
    return map(tostr, self.getContent())
  def __str__(self):
    return '\n'.join(self.getStrRows())

class AddRemove(SequenceMatcher):
  def __init__(self):
    SequenceMatcher.__init__(self, None, None, None)
  def set_left(self, left):
    if not isinstance(left, list):
      left = [l for l in left]
    self.set_seq1(left)
  def set_right(self, right):
    if not isinstance(right, list):
      right = [l for l in right]
    self.set_seq2(right)
  def __iter__(self):
    for tag, i1, i2, j1, j2 in self.get_opcodes():
      if tag == 'equal':
        for pair in zip(self.a[i1:i2], self.b[j1:j2]):
          yield ('equal', pair)
      elif tag == 'delete':
        for item in self.a[i1:i2]:
          yield ('delete', item)
      elif tag == 'insert':
        for item in self.b[j1:j2]:
          yield ('add', item)
      else:
        # tag == 'replace'
        for item in self.a[i1:i2]:
          yield ('delete', item)
        for item in self.b[j1:j2]:
          yield ('add', item)

class DirectoryCompare(SequenceMatcher):
  def __init__(self, reference):
    SequenceMatcher.__init__(self, None, [i for i in reference],
                             [])
    self.watcher = None
  def setWatcher(self, watcher):
    self.watcher = watcher
  def compareWith(self, other):
    if not self.watcher:
      return
    self.set_seq2([i for i in other])
    for tag, i1, i2, j1, j2 in self.get_opcodes():
      if tag == 'equal':
        for i, j in zip(xrange(i1,i2), xrange(j1,j2)):
          self.watcher.compare(self.a[i], self.b[j])
      elif tag == 'delete':
        for i in xrange(i1,i2):
          self.watcher.add(self.a[i], other.cloneFile(self.a[i]))
      elif tag == 'insert':
        for j in xrange(j1, j2):
          self.watcher.remove(self.b[j])
      else:
        for j in xrange(j1, j2):
          self.watcher.remove(self.b[j])
        for i in xrange(i1,i2):
          self.watcher.add(self.a[i], other.cloneFile(self.a[i]))

class Observer(object):
  stat_cats = ['missing', 'obsolete', 'missingInFiles',
               'changed', 'unchanged', 'keys']
  def __init__(self):
    class intdict(defaultdict):
      def __init__(self):
        defaultdict.__init__(self, int)
    self.summary = defaultdict(intdict)
    self.details = Tree(dict)
    self.filter = None
  # support pickling
  def __getstate__(self):
    return dict(summary = self.getSummary(), details = self.details)
  def __setstate__(self, state):
    class intdict(defaultdict):
      def __init__(self):
        defaultdict.__init__(self, int)
    self.summary = defaultdict(intdict)
    if 'summary' in state:
      for loc, stats in state['summary'].iteritems():
        self.summary[loc].update(stats)
    self.details = state['details']
    self.filter = None
  def getSummary(self):
    plaindict = {}
    for k, v in self.summary.iteritems():
      plaindict[k] = dict(v)
    return plaindict
  def toJSON(self):
    return dict(summary = self.getSummary(), details = self.details.toJSON())
  def notify(self, category, file, data):
    if category in self.stat_cats:
      self.summary[file.locale][category] += data
    elif category in ['missingFile', 'obsoleteFile']:
      if self.filter is None or self.filter(file):
        self.details[file][category] = True
    elif category in ['missingEntity', 'obsoleteEntity']:
      if self.filter is not None and not self.filter(file, data):
        return
      v = self.details[file]
      if 'entities' not in v:
        v['entities'] = dict()
      v['entities'][data] = ['add', 'remove'][category == 'obsoleteEntity']
    elif category == 'error':
      self.details[file][category] = data
  def serialize(self, type="text/plain"):
    def tostr(t):
      if t[1] == 'key':
        return '  ' * t[0] + '/'.join(t[2])
      o = []
      indent = '  ' * (t[0] + 1)
      if 'entities' in t[2]:
        v = t[2]['entities']
        entities = v.keys()
        entities.sort()
        for entity in entities:
          op = '+'
          if v[entity] == 'remove':
            op = '-'
          o.append(indent + op + entity)
      elif 'missingFile' in t[2]:
        o.append(indent + '// add and localize this file')
      elif 'obsoleteFile' in t[2]:
        o.append(indent + '// remove this file')
      else:
        o.append(indent + str(t[2]))
      return '\n'.join(o)
    out = []
    for locale, summary in self.summary.iteritems():
      if locale is not None:
        out.append(locale + ':')
      out += [k + ': ' + str(v) for k,v in summary.iteritems()]
      total = sum([summary[k] \
                     for k in ['changed','unchanged','missing',
                               'missingInFiles'] \
                     if k in summary])
      rate = (('changed' in summary and summary['changed'] * 100)
              or 0) / total
      out.append('%d%% of entries changed' % rate)
    return '\n'.join(map(tostr, self.details.getContent()) + out)
  def __str__(self):
    return 'observer'

class ContentComparer:
  keyRE = re.compile('[kK]ey')
  def __init__(self):
    self.reference = dict()
    self.observers = []
  def add_observer(self, obs):
    self.observers.append(obs)
  def notify(self, category, file, data):
    for obs in self.observers:
      obs.notify(category, file, data)
  def remove(self, obsolete):
    self.notify('obsoleteFile', obsolete, None)
    pass
  def compare(self, ref_file, l10n):
    try:
      p = Parser.getParser(ref_file.file)
    except UserWarning:
      # no comparison, XXX report?
      return
    if ref_file not in self.reference:
      # we didn't parse this before
      try:
        p.readContents(ref_file.getContents())
      except Exception, e:
        self.notify('error', ref_file, str(e))
        return
      self.reference[ref_file] = p.parse()
    ref = self.reference[ref_file]
    ref_list = ref[1].keys()
    ref_list.sort()
    try:
      p.readContents(l10n.getContents())
      l10n_entities, l10n_map = p.parse()
    except Exception, e:
      self.notify('error', l10n, str(e))
      return
    l10n_list = l10n_map.keys()
    l10n_list.sort()
    ar = AddRemove()
    ar.set_left(ref_list)
    ar.set_right(l10n_list)
    missing = obsolete = changed = unchanged = keys = 0
    for action, item_or_pair in ar:
      if action == 'delete':
        # missing entity
        self.notify('missingEntity', l10n, item_or_pair)
        missing += 1
      elif action == 'add':
        # obsolete entity
        self.notify('obsoleteEntity', l10n, item_or_pair)
        obsolete += 1
      else:
        entity = item_or_pair[0]
        if self.keyRE.search(entity):
          keys += 1
        else:
          refVal = ref[0][ref[1][entity]]['val']
          l10nVal = l10n_entities[l10n_map[entity]]['val']
          if refVal == l10nVal:
            unchanged += 1
          else:
            changed += 1
        pass
    if missing:
      self.notify('missing', l10n, missing)
    if obsolete:
      self.notify('obsolete', l10n, obsolete)
    if changed:
      self.notify('changed', l10n, changed)
    if unchanged:
      self.notify('unchanged', l10n, unchanged)
    if keys:
      self.notify('keys', l10n, keys)
    pass
  def add(self, orig, missing):
    self.notify('missingFile', missing, None)
    f = orig
    try:
      p = Parser.getParser(f.file)
    except UserWarning:
      return
    p.readContents(f.getContents())
    entities, map = p.parse()
    self.notify('missingInFiles', missing, len(map))

def compareApp(app):
  cc = ContentComparer()
  o  = Observer()
  cc.add_observer(o)
  o.filter = app.filter
  for module, reference, locales in app:
    dc = DirectoryCompare(reference)
    dc.setWatcher(cc)
    for locale, localization in locales:
      dc.compareWith(localization)
  return o
