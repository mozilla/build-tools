import unittest
import tempfile
import shutil
import os
import subprocess

from util.hg import clone, pull, update, hg_ver, mercurial, _make_absolute, \
  share, push, apply_and_push, HgUtilError, make_hg_url, get_branch, \
  get_branches
from util.commands import run_cmd, get_output

def getRevisions(dest):
    retval = []
    for rev in get_output(['hg', 'log', '-R', dest, '--template', '{node|short}\n']).split('\n'):
        rev = rev.strip()
        if not rev:
            continue
        retval.append(rev)
    return retval

class TestMakeAbsolute(unittest.TestCase):
    def testAbsolutePath(self):
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

    def testGetBranch(self):
        clone(self.repodir, self.wc)
        b = get_branch(self.wc)
        self.assertEquals(b, 'default')

    def testGetBranches(self):
        clone(self.repodir, self.wc)
        branches = get_branches(self.wc)
        self.assertEquals(sorted(branches), sorted(["branch2", "default"]))

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

    def testShareUnrelated(self):
        # Create a new repo
        repo2 = os.path.join(self.tmpdir, 'repo2')
        run_cmd(['%s/init_hgrepo.sh' % os.path.dirname(__file__), repo2])

        self.assertNotEqual(self.revisions, getRevisions(repo2))

        shareBase = os.path.join(self.tmpdir, 'share')

        # Clone the original repo
        mercurial(self.repodir, self.wc, shareBase=shareBase)

        # Clone the new repo
        mercurial(repo2, self.wc, shareBase=shareBase)

        self.assertEquals(getRevisions(self.wc), getRevisions(repo2))

    def testShareReset(self):
        shareBase = os.path.join(self.tmpdir, 'share')

        # Clone the original repo
        mercurial(self.repodir, self.wc, shareBase=shareBase)

        old_revs = self.revisions[:]

        # Reset the repo
        run_cmd(['%s/init_hgrepo.sh' % os.path.dirname(__file__), self.repodir])

        self.assertNotEqual(old_revs, getRevisions(self.repodir))

        # Try and update our working copy
        mercurial(self.repodir, self.wc, shareBase=shareBase)

        self.assertEquals(getRevisions(self.repodir), getRevisions(self.wc))
        self.assertNotEqual(old_revs, getRevisions(self.wc))

    def testPush(self):
        clone(self.repodir, self.wc, revision=self.revisions[-2])
        push(src=self.repodir, remote=self.wc)
        self.assertEquals(getRevisions(self.wc), self.revisions)

    def testPushWithBranch(self):
        clone(self.repodir, self.wc, revision=self.revisions[-1])
        push(src=self.repodir, remote=self.wc, branch='branch2')
        push(src=self.repodir, remote=self.wc, branch='default')
        self.assertEquals(getRevisions(self.wc), self.revisions)

    def testPushWithRevision(self):
        clone(self.repodir, self.wc, revision=self.revisions[-2])
        push(src=self.repodir, remote=self.wc, revision=self.revisions[-1])
        self.assertEquals(getRevisions(self.wc), self.revisions[-2:])

    def testMercurial(self):
        rev = mercurial(self.repodir, self.wc)
        self.assertEquals(rev, self.revisions[0])

    def testPushNewBranchesNotAllowed(self):
        clone(self.repodir, self.wc, revision=self.revisions[0])
        self.assertRaises(Exception, push, self.repodir, self.wc,
                          push_new_branches=False)

    def testMercurialWithNewShare(self):
        shareBase = os.path.join(self.tmpdir, 'share')
        sharerepo = os.path.join(shareBase, self.repodir.lstrip("/"))
        os.mkdir(shareBase)
        mercurial(self.repodir, self.wc, shareBase=shareBase)
        self.assertEquals(getRevisions(self.repodir), getRevisions(self.wc))
        self.assertEquals(getRevisions(self.repodir), getRevisions(sharerepo))

    def testMercurialWithShareBaseInEnv(self):
        shareBase = os.path.join(self.tmpdir, 'share')
        sharerepo = os.path.join(shareBase, self.repodir.lstrip("/"))
        os.mkdir(shareBase)
        try:
            os.environ['HG_SHARE_BASE_DIR'] = shareBase
            mercurial(self.repodir, self.wc)
            self.assertEquals(getRevisions(self.repodir), getRevisions(self.wc))
            self.assertEquals(getRevisions(self.repodir), getRevisions(sharerepo))
        finally:
            del os.environ['HG_SHARE_BASE_DIR']

    def testMercurialWithExistingShare(self):
        shareBase = os.path.join(self.tmpdir, 'share')
        sharerepo = os.path.join(shareBase, self.repodir.lstrip("/"))
        os.mkdir(shareBase)
        mercurial(self.repodir, sharerepo)
        open(os.path.join(self.repodir, 'test.txt'), 'w').write('hello!')
        run_cmd(['hg', 'add', 'test.txt'], cwd=self.repodir)
        run_cmd(['hg', 'commit', '-m', 'adding changeset'], cwd=self.repodir)
        mercurial(self.repodir, self.wc, shareBase=shareBase)
        self.assertEquals(getRevisions(self.repodir), getRevisions(self.wc))
        self.assertEquals(getRevisions(self.repodir), getRevisions(sharerepo))


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

    # TODO: this test doesn't seem to be compatible with mercurial()'s
    # share() usage, and fails when HG_SHARE_BASE_DIR is set
    def testMercurialChangeRepo(self):
        # Create a new repo
        old_env = os.environ.copy()
        if 'HG_SHARE_BASE_DIR' in os.environ:
            del os.environ['HG_SHARE_BASE_DIR']

        try:
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
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def testMakeHGUrl(self):
        #construct an hg url specific to revision, branch and filename and try to pull it down
        file_url = make_hg_url(
                "hg.mozilla.org",
                '//build/tools/',
                revision='FIREFOX_3_6_12_RELEASE',
                filename="/lib/python/util/hg.py"
                )
        expected_url = "http://hg.mozilla.org/build/tools/raw-file/FIREFOX_3_6_12_RELEASE/lib/python/util/hg.py"
        self.assertEquals(file_url, expected_url)

    def testMakeHGUrlNoFilename(self):
        file_url = make_hg_url(
                "hg.mozilla.org",
                "/build/tools",
                revision="default"
        )
        expected_url = "http://hg.mozilla.org/build/tools/rev/default"
        self.assertEquals(file_url, expected_url)

    def testMakeHGUrlNoRevisionNoFilename(self):
        repo_url = make_hg_url(
                "hg.mozilla.org",
                "/build/tools"
        )
        expected_url = "http://hg.mozilla.org/build/tools"
        self.assertEquals(repo_url, expected_url)

    def testMakeHGUrlDifferentProtocol(self):
        repo_url = make_hg_url(
                "hg.mozilla.org",
                "/build/tools",
                protocol='ssh'
        )
        expected_url = "ssh://hg.mozilla.org/build/tools"
        self.assertEquals(repo_url, expected_url)

    def testShareRepo(self):
        repo3 = os.path.join(self.tmpdir, 'repo3')
        share(self.repodir, repo3)
        # make sure shared history is identical
        self.assertEquals(self.revisions, getRevisions(repo3))

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

    def testApplyAndPush(self):
        clone(self.repodir, self.wc)
        def c(repo, attempt):
            run_cmd(['hg', 'tag', '-f', 'TEST'], cwd=repo)
        apply_and_push(self.wc, self.repodir, c)
        self.assertEquals(getRevisions(self.wc), getRevisions(self.repodir))

    def testApplyAndPushFail(self):
        clone(self.repodir, self.wc)
        def c(repo, attempt, remote):
            run_cmd(['hg', 'tag', '-f', 'TEST'], cwd=repo)
            run_cmd(['hg', 'tag', '-f', 'CONFLICTING_TAG'], cwd=remote)
        self.assertRaises(HgUtilError, apply_and_push, self.wc, self.repodir,
                          lambda r, a: c(r, a, self.repodir), max_attempts=2)

    def testApplyAndPushWithRebase(self):
        clone(self.repodir, self.wc)
        def c(repo, attempt, remote):
            run_cmd(['hg', 'tag', '-f', 'TEST'], cwd=repo)
            if attempt == 1:
                run_cmd(['hg', 'rm', 'hello.txt'], cwd=remote)
                run_cmd(['hg', 'commit', '-m', 'test'], cwd=remote)
        apply_and_push(self.wc, self.repodir,
                       lambda r, a: c(r, a, self.repodir), max_attempts=2)
        self.assertEquals(getRevisions(self.wc), getRevisions(self.repodir))

    def testApplyAndPushRebaseFails(self):
        clone(self.repodir, self.wc)
        def c(repo, attempt, remote):
            run_cmd(['hg', 'tag', '-f', 'TEST'], cwd=repo)
            if attempt in (1,2):
                run_cmd(['hg', 'tag', '-f', 'CONFLICTING_TAG'], cwd=remote)
        apply_and_push(self.wc, self.repodir,
                       lambda r, a: c(r, a, self.repodir), max_attempts=3)
        self.assertEquals(getRevisions(self.wc), getRevisions(self.repodir))

    def testApplyAndPushOnBranch(self):
        clone(self.repodir, self.wc)
        def c(repo, attempt):
            run_cmd(['hg', 'branch', 'branch3'], cwd=repo)
            run_cmd(['hg', 'tag', '-f', 'TEST'], cwd=repo)
        apply_and_push(self.wc, self.repodir, c)
        self.assertEquals(getRevisions(self.wc), getRevisions(self.repodir))

    def testApplyAndPushWithNoChange(self):
        clone(self.repodir, self.wc)
        def c(r,a):
            pass
        self.assertRaises(HgUtilError, apply_and_push, self.wc, self.repodir, c)
