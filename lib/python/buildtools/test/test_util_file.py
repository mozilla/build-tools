import unittest, tempfile, os
from util.file import compare

class TestFileOps(unittest.TestCase):
    def testCompareEqFiles(self):
        tmpdir = tempfile.mkdtemp()
        file1 = os.path.join(tmpdir, "foo")
        file2 = os.path.join(tmpdir, "bar")
        open(file1, "w").write("hello")
        open(file2, "w").write("hello")
        self.failUnless(compare(file1, file2))

    def testCompareDiffFiles(self):
        tmpdir = tempfile.mkdtemp()
        file1 = os.path.join(tmpdir, "foo")
        file2 = os.path.join(tmpdir, "bar")
        open(file1, "w").write("hello")
        open(file2, "w").write("goodbye")
        self.failUnless(not compare(file1, file2))
