import unittest

from Mozilla.Parser import getParser

class TestLineWraps(unittest.TestCase):

  def setUp(self):
    self.p = getParser('foo.properties')

  def tearDown(self):
    self.p = None

  def testBackslashes(self):
    self.p.readContents(r'''one_line = This is one line
two_line = This is the first \
of two lines
one_line_trailing = This line ends in \\
and has junk
two_lines_triple = This line is one of two and ends in \\\
and still has another line coming
''')
    for e in self.p:
      print '"%s" => %s \n\n' % (e.key, e.val)

if __name__ == '__main__':
  unittest.main()
