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
#       Clint Talbert <ctalbert@mozilla.com>
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

import re
import codecs
import logging
from HTMLParser import HTMLParser

__constructors = []

class Parser:
  canMerge = True
  def __init__(self):
    if not hasattr(self, 'encoding'):
      self.encoding = 'utf-8';
    pass
  def readFile(self, file):
    f = codecs.open(file, 'r', self.encoding)
    try:
      self.contents = f.read()
    except UnicodeDecodeError, e:
      logging.getLogger('locales').error("Can't read file: " + file + '; ' + str(e))
      self.contents = u''
    f.close()
  def readContents(self, contents):
    (self.contents, length) = codecs.getdecoder(self.encoding)(contents)
  def parse(self):
    l = []
    m = {}
    for e in self:
      m[e['key']] = len(l)
      l.append(e)
    return (l, m)
  def postProcessValue(self, val):
    return val
  def __iter__(self):
    self.offset = 0
    self.header = ''
    self.footer = ''
    h = self.reHeader.search(self.contents)
    if h:
      self.header = h.group()
      self.offset = h.end()
    return self
  def next(self):
    m = self.reKey.search(self.contents, self.offset)
    if not m or m.start() != self.offset:
      t = self.reFooter.search(self.contents, self.offset)
      if t:
        self.footer = t.group()
        self.offset = t.end()
      raise StopIteration
    self.offset = m.end()
    return {'key': m.group(4), 'val': self.postProcessValue(m.group(5)), 'all': m.group(0), 'prespace': m.group(1), 'precomment': m.group(2), 'def': m.group(3), 'post': m.group(6)}

def getParser(path):
  for item in __constructors:
    if re.search(item[0], path):
      return item[1]
  raise UserWarning, "Cannot find Parser"


# Subgroups of the match will:
# 1: pre white space
# 2: pre comments
# 3: entity definition
# 4: entity key (name)
# 5: entity value
# 6: post comment (and white space) in the same line (dtd only)
#                                           <--[1]
# <!-- pre comments -->                     <--[2]
# <!ENTITY key "value"> <!-- comment -->
# 
# <-------[3]---------><------[6]------>


class DTDParser(Parser):
  def __init__(self):
    # http://www.w3.org/TR/2006/REC-xml11-20060816/#NT-NameStartChar
    #":" | [A-Z] | "_" | [a-z] |
    # [#xC0-#xD6] | [#xD8-#xF6] | [#xF8-#x2FF] | [#x370-#x37D] | [#x37F-#x1FFF]
    # | [#x200C-#x200D] | [#x2070-#x218F] | [#x2C00-#x2FEF] |
    # [#x3001-#xD7FF] | [#xF900-#xFDCF] | [#xFDF0-#xFFFD] |
    # [#x10000-#xEFFFF]
    NameStartChar = u':A-Z_a-z\xC0-\xD6\xD8-\xF6\xF8-\u02FF' + \
        u'\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF'+\
        u'\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD'
    # + \U00010000-\U000EFFFF seems to be unsupported in python
    
    # NameChar ::= NameStartChar | "-" | "." | [0-9] | #xB7 |
    #   [#x0300-#x036F] | [#x203F-#x2040]
    NameChar = NameStartChar + ur'\-\.0-9' + u'\xB7\u0300-\u036F\u203F-\u2040'
    Name = '[' + NameStartChar + '][' + NameChar + ']*'
    self.reKey = re.compile('(\s*)((?:<!--(?:[^-]+-)*[^-]+-->\s*)*)(<!ENTITY\s+(' + Name + ')\s+(\"[^\"]*\"|\'[^\']*\')\s*>)([ \t]*(?:<!--(?:[^\n-]+-)*[^\n-]+-->[ \t]*)*\n?)?')
    # allow parameter entity reference only in the header block
    self.reHeader = re.compile('^(\s*<!ENTITY\s+%\s+' + Name + '\s+SYSTEM\s+(\"[^\"]*\"|\'[^\']*\')\s*>\s*%[\w\.]+;)?(\s*<!--([^-]+-)*[^-]+-->)?')
    self.reFooter = re.compile('\s*(<!--([^-]+-)*[^-]+-->\s*)*$')
    Parser.__init__(self)

class PropertiesParser(Parser):
  def __init__(self):
    self.reKey = re.compile('^(\s*)((?:[#!].*\n\s*)*)(([^#!\s\r\n][^=:\r\n]*?)\s*[:=][ \t]*(.*?))([ \t]*$\n?)',re.M)
    self.reHeader = re.compile('^\s*([#!].*\s*)*')
    self.reFooter = re.compile('\s*([#!].*\s*)*$')
    self._post = re.compile('\\\\u([0-9a-fA-F]{4})')
    Parser.__init__(self)
  _arg_re = re.compile('%(?:(?P<cn>[0-9]+)\$)?(?P<width>[0-9]+)?(?:.(?P<pres>[0-9]+))?(?P<size>[hL]|(?:ll?))?(?P<type>[dciouxXefgpCSsn])')
  def postProcessValue(self, val):
    m = self._post.search(val)
    if not m:
      return val
    while m:
      uChar = unichr(int(m.group(1), 16))
      val = val.replace(m.group(), uChar)
      m = self._post.search(val)
    return val

class DefinesParser(Parser):
  def __init__(self):
    self.reKey = re.compile('^(\s*)((?:^#(?!define\s).*\s*)*)(#define[ \t]+(\w+)[ \t]+(.*?))([ \t]*$\n?)',re.M)
    self.reHeader = re.compile('^\s*(#(?!define\s).*\s*)*')
    self.reFooter = re.compile('\s*(#(?!define\s).*\s*)*$',re.M)
    Parser.__init__(self)

DECL, COMMENT, START, END, CONTENT = range(5)

class BookmarksParser(HTMLParser, Parser):
  canMerge = False

  class Token(object):
    _type = None
    content = ''
    def __str__(self):
      return self.content
  class DeclToken(Token):
    _type = DECL
    def __init__(self, decl):
      self.content = decl
      pass
    def __str__(self):
      return '<!%s>' % self.content
    pass
  class CommentToken(Token):
    _type = COMMENT
    def __init__(self, comment):
      self.content = comment
      pass
    def __str__(self):
      return '<!--%s-->' % self.content
    pass
  class StartToken(Token):
    _type = START
    def __init__(self, tag, attrs, content):
      self.tag = tag
      self.attrs = dict(attrs)
      self.content = content
      pass
    pass
  class EndToken(Token):
    _type = END
    def __init__(self, tag):
      self.tag = tag
      pass
    def __str__(self):
      return '</%s>' % self.tag.upper()
    pass
  class ContentToken(Token):
    _type = CONTENT
    def __init__(self, content):
      self.content = content
      pass
    pass
  
  def __init__(self):
    HTMLParser.__init__(self)
    Parser.__init__(self)
    self.tokens = []

  def __iter__(self):
    self.tokens = []
    self.feed(self.contents)
    self.close()
    tks = self.tokens
    i = 0
    k = []
    for i in xrange(len(tks)):
      t = tks[i]
      if t._type == START:
        k.append(t.tag)
        for attrname in sorted(t.attrs.keys()):
          yield dict(key = '.'.join(k) + '.@' + attrname,
                     val = t.attrs[attrname])
        if i + 1 < len(tks) and tks[i+1]._type == CONTENT:
          i += 1
          t = tks[i]
          v = t.content.strip()
          if v:
            yield dict(key = '.'.join(k),
                       val = v)
      elif t._type == END:
        k.pop()

  # Called when we hit an end DL tag to reset the folder selections
  def handle_decl(self, decl):
    self.tokens.append(self.DeclToken(decl))

  # Called when we hit an end DL tag to reset the folder selections
  def handle_comment(self, comment):
    self.tokens.append(self.CommentToken(comment))

  def handle_starttag(self, tag, attrs):
    self.tokens.append(self.StartToken(tag, attrs, self.get_starttag_text()))

  # Called when text data is encountered
  def handle_data(self, data):
    if self.tokens[-1]._type == CONTENT:
      self.tokens[-1].content += data
    else:
      self.tokens.append(self.ContentToken(data))

  def handle_charref(self, data):
    self.handle_data('&#%s;' % data)

  def handle_entityref(self, data):
    self.handle_data('&%s;' % data)

  # Called when we hit an end DL tag to reset the folder selections
  def handle_endtag(self, tag):
    self.tokens.append(self.EndToken(tag))

__constructors = [('\\.dtd', DTDParser()),
                  ('\\.properties', PropertiesParser()),
                  ('\\.inc', DefinesParser()),
                  ('bookmarks\\.html', BookmarksParser())]
