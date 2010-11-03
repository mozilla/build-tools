import unittest
import tempfile
import shutil
import os
import subprocess

from util.hg import clone, pull, update, hg_ver, mercurial, _make_absolute, share, make_hg_url
from util.commands import run_cmd, get_output, remove_path

def getRevisions(dest):
    retval = []
    for rev in get_output(['hg', 'log', '-R', dest, '--template', '{node|short}\n']).split('\n'):
        rev = rev.strip()
        if not rev:
            continue
        retval.append(rev)
    return retval

class TestMakeAbsolute(unittest.TestCase):
    def testAboslutePath(self):
        self.assertEquals(_make_absolute("/foo/bar"), "/foo/bar")

    def testRelativePath(self):
        self.assertEquals(_make_absolute("foo/bar"), os.path.abspath("foo/bar"))

    def testHTTPPaths(self):
        self.assertEquals(_make_absolute("http://foo/bar"), "http://foo/bar")

    def testAbsoluteFilePath(self):
        self.assertEquals(_make_absolute("file:///foo/bar"), "file:///foo/bar")

    def testRelativeFilePath(self):
        self.assertEquals(_make_absolute("file://foo/bar"), "file://%s/foo/bar" % os.getcwd())

class TestHg(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repodir = os.path.join(self.tmpdir, 'repo')
        run_cmd(['%s/init_hgrepo.sh' % os.path.dirname(__file__),
                self.repodir])

        self.revisions = getRevisions(self.repodir)
        self.wc = os.path.join(self.tmpdir, 'wc')
        self.pwd = os.getcwd()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        os.chdir(self.pwd)

    def testClone(self):
        rev = clone(self.repodir, self.wc, update_dest=False)
        self.assertEquals(rev, None)
        self.assertEquals(self.revisions, getRevisions(self.wc))
        self.assertEquals(sorted(os.listdir(self.wc)), ['.hg'])

    def testCloneIntoNonEmptyDir(self):
        os.mkdir(self.wc)
        open(os.path.join(self.wc, 'test.txt'), 'w').write('hello')
        clone(self.repodir, self.wc, update_dest=False)
        self.failUnless(not os.path.exists(os.path.join(self.wc, 'test.txt')))

    def testCloneUpdate(self):
        rev = clone(self.repodir, self.wc, update_dest=True)
        self.assertEquals(rev, self.revisions[0])

    def testCloneBranch(self):
        clone(self.repodir, self.wc, branch='branch2',
                update_dest=False)
        # On hg 1.6, we should only have a subset of the revisions
        if hg_ver() >= (1,6,0):
            self.assertEquals(self.revisions[1:],
                    getRevisions(self.wc))
        else:
            self.assertEquals(self.revisions,
                    getRevisions(self.wc))

    def testCloneUpdateBranch(self):
        rev = clone(self.repodir, os.path.join(self.tmpdir, 'wc'),
                branch="branch2", update_dest=True)
        self.assertEquals(rev, self.revisions[1], self.revisions)

    def testCloneRevision(self):
        clone(self.repodir, self.wc,
                revision=self.revisions[0], update_dest=False)
        # We'll only get a subset of the revisions
        self.assertEquals(self.revisions[:1] + self.revisions[2:],
                getRevisions(self.wc))

    def testUpdateRevision(self):
        rev = clone(self.repodir, self.wc, update_dest=False)
        self.assertEquals(rev, None)

        rev = update(self.wc, revision=self.revisions[1])
        self.assertEquals(rev, self.revisions[1])

    def testPull(self):
        # Clone just the first rev
        clone(self.repodir, self.wc, revision=self.revisions[-1], update_dest=False)
        self.assertEquals(getRevisions(self.wc), self.revisions[-1:])

        # Now pull in new changes
        rev = pull(self.repodir, self.wc, update_dest=False)
        self.assertEquals(rev, None)
        self.assertEquals(getRevisions(self.wc), self.revisions)

    def testPullRevision(self):
        # Clone just the first rev
        clone(self.repodir, self.wc, revision=self.revisions[-1], update_dest=False)
        self.assertEquals(getRevisions(self.wc), self.revisions[-1:])

        # Now pull in just the last revision
        rev = pull(self.repodir, self.wc, revision=self.revisions[0], update_dest=False)
        self.assertEquals(rev, None)

        # We'll be missing the middle revision (on another branch)
        self.assertEquals(getRevisions(self.wc), self.revisions[:1] + self.revisions[2:])

    def testPullBranch(self):
        # Clone just the first rev
        clone(self.repodir, self.wc, revision=self.revisions[-1], update_dest=False)
        self.assertEquals(getRevisions(self.wc), self.revisions[-1:])

        # Now pull in the other branch
        rev = pull(self.repodir, self.wc, branch="branch2", update_dest=False)
        self.assertEquals(rev, None)

        # On hg 1.6, we'll be missing the last revision (on another branch)
        if hg_ver() >= (1,6,0):
            self.assertEquals(getRevisions(self.wc), self.revisions[1:])
        else:
            self.assertEquals(getRevisions(self.wc), self.revisions)

    def testPullUnrelated(self):
        # Create a new repo
        repo2 = os.path.join(self.tmpdir, 'repo2')
        run_cmd(['%s/init_hgrepo.sh' % os.path.dirname(__file__), repo2])

        self.assertNotEqual(self.revisions, getRevisions(repo2))

        # Clone the original repo
        clone(self.repodir, self.wc, update_dest=False)

        # Try and pull in changes from the new repo
        self.assertRaises(subprocess.CalledProcessError, pull, repo2, self.wc, update_dest=False)

    def testMercurial(self):
        rev = mercurial(self.repodir, self.wc)
        self.assertEquals(rev, self.revisions[0])

    def testMercurialRelativeDir(self):
        os.chdir(os.path.dirname(self.repodir))

        repo = os.path.basename(self.repodir)
        wc = os.path.basename(self.wc)

        rev = mercurial(repo, wc, revision=self.revisions[-1])
        self.assertEquals(rev, self.revisions[-1])
        open(os.path.join(self.wc, 'test.txt'), 'w').write("hello!")

        rev = mercurial(repo, wc)
        self.assertEquals(rev, self.revisions[0])
        # Make sure our local file didn't go away
        self.failUnless(os.path.exists(os.path.join(self.wc, 'test.txt')))

    def testMercurialUpdateTip(self):
        rev = mercurial(self.repodir, self.wc, revision=self.revisions[-1])
        self.assertEquals(rev, self.revisions[-1])
        open(os.path.join(self.wc, 'test.txt'), 'w').write("hello!")

        rev = mercurial(self.repodir, self.wc)
        self.assertEquals(rev, self.revisions[0])
        # Make sure our local file didn't go away
        self.failUnless(os.path.exists(os.path.join(self.wc, 'test.txt')))

    def testMercurialUpdateRev(self):
        rev = mercurial(self.repodir, self.wc, revision=self.revisions[-1])
        self.assertEquals(rev, self.revisions[-1])
        open(os.path.join(self.wc, 'test.txt'), 'w').write("hello!")

        rev = mercurial(self.repodir, self.wc, revision=self.revisions[0])
        self.assertEquals(rev, self.revisions[0])
        # Make sure our local file didn't go away
        self.failUnless(os.path.exists(os.path.join(self.wc, 'test.txt')))

    def testMercurialChangeRepo(self):
        # Create a new repo
        repo2 = os.path.join(self.tmpdir, 'repo2')
        run_cmd(['%s/init_hgrepo.sh' % os.path.dirname(__file__), repo2])

        self.assertNotEqual(self.revisions, getRevisions(repo2))

        # Clone the original repo
        mercurial(self.repodir, self.wc)
        self.assertEquals(getRevisions(self.wc), self.revisions)
        open(os.path.join(self.wc, 'test.txt'), 'w').write("hello!")

        # Clone the new one
        mercurial(repo2, self.wc)
        self.assertEquals(getRevisions(self.wc), getRevisions(repo2))
        # Make sure our local file went away
        self.failUnless(not os.path.exists(os.path.join(self.wc, 'test.txt')))

    def testMakeHGUrl(self):
        #construct an hg url specific to revision, branch and filename and try to pull it down
        file_url = make_hg_url(
                "http://hg.mozilla.org",
                '//build/tools/',
                'FIREFOX_3_6_12_RELEASE',
                "/lib/python/util/hg.py"
                )
        expected_url = "http://hg.mozilla.org/build/tools/raw-file/FIREFOX_3_6_12_RELEASE/lib/python/util/hg.py"
        self.assertEquals(file_url, expected_url)

    def testShareRepo(self):
        repo3 = os.path.join(self.tmpdir, 'repo3')
        share(self.repodir, repo3)
        # make sure shared history is identical
        self.assertEquals(self.revisions, getRevisions(repo3))

    def testShareClobber(self):
        repo4 = os.path.join(self.tmpdir, 'repo4')
        os.mkdir(repo4)
        share(self.repodir, repo4)
        # make sure that share() clobbered the empty dir and created the shared repo
        self.assertEquals(self.revisions, getRevisions(repo4))

    def testMercurialShareOutgoing(self):
        # ensure that outgoing changesets in a shared clone affect the shared history
        repo5 = os.path.join(self.tmpdir, 'repo5')
        repo6 = os.path.join(self.tmpdir, 'repo6')
        mercurial(self.repodir, repo5)
        share(repo5, repo6)
        open(os.path.join(repo6, 'test.txt'), 'w').write("hello!")
        # modify the history of the new clone
        run_cmd(['hg', 'add', 'test.txt'], cwd=repo6)
        run_cmd(['hg', 'commit', '-m', 'adding changeset'], cwd=repo6)
        self.assertNotEquals(self.revisions, getRevisions(repo6))
        self.assertNotEquals(self.revisions, getRevisions(repo5))
        self.assertEquals(getRevisions(repo5), getRevisions(repo6))
