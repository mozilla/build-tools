from unittest import TestCase
import sqlite3
import os
import subprocess
import urllib
import time
import shutil

###
# For testing, update the values below to be suitable to your testing
# environment
###
clobberURL = "http://localhost/~catlee/index.php"
dbFile = "/home/catlee/public_html/db/clobberer.db"
testDir = 'test-dir'

###
# Various utility functions for setting up a test case
###
def updateBuild(branch, buildername, builddir, slave, master):
    """Send an update to the server to indicate that a slave is doing a build.
    Returns the server's response."""
    params = dict(branch=branch, buildername=buildername, builddir=builddir,
            slave=slave, master=master)
    url = "%s?%s" % (clobberURL, urllib.urlencode(params))
    data = urllib.urlopen(url).read().strip()
    return data

def setClobberPage(branch, builddir, slave, master, now):
    """Schedules a clobber by sending a POST request to the server and
       records the response"""
    params = dict(branch=branch, builddir=builddir,
            slave=slave, master=master, form_submitted=True)
    data = urllib.urlopen(clobberURL, data=urllib.urlencode(params))
    return data.read().strip()

def setClobber(branch, builddir, slave, master, now):
    """Schedules a clobber by inserting data directly into the database."""
    db = sqlite3.connect(dbFile)
    db.execute("""INSERT INTO clobber_times
            (master, branch, builddir, slave, lastclobber, who)
            VALUES (?, ?, ?, ?, ?, 'testuser')""",
        (master, branch, builddir, slave, now))
    db.commit()

def getClobbers():
    """Returns a list of all entries in the clobber_times table"""
    db = sqlite3.connect(dbFile)
    res = db.execute("SELECT * FROM clobber_times")
    return res.fetchall()

def getBuilds():
    """Returns a list of all entries in the builds table"""
    db = sqlite3.connect(dbFile)
    res = db.execute("SELECT * FROM builds")
    return res.fetchall()

def makeBuildDir(name, t):
    """Create a fake build directory in our testDir, with last-clobber set to
    `t`"""
    builddir = os.path.join(testDir, name)
    if not os.path.exists(builddir):
        os.makedirs(builddir)
    open(os.path.join(builddir, 'last-clobber'), "w").write(str(t))

def runClobberer(branch, buildername, builddir, slave, master, periodic=None,
        dry_run=True):
    """Run the clobberer.py script, and return the output"""
    if not os.path.exists(testDir):
        os.makedirs(testDir)
    cmd = ['python', os.path.abspath('clobberer.py'), '-v']
    if periodic:
        cmd.extend(['-t', str(periodic)])
    if dry_run:
        cmd.append('-n')
    cmd.extend([clobberURL, branch, buildername, builddir, slave, master])
    p = subprocess.Popen(cmd, cwd=testDir, stdout=subprocess.PIPE)
    p.wait()
    return p.stdout.read()

###
# Test cases
###
class TestClobber(TestCase):
    def setUp(self):
        if os.path.exists(dbFile):
            os.unlink(dbFile)
        # Hit the clobberURL to create the database file
        urllib.urlopen(clobberURL).read()

        # Create a working directory
        if os.path.exists(testDir):
            shutil.rmtree(testDir)
        os.makedirs(testDir)

    def tearDown(self):
        if os.path.exists(testDir):
            shutil.rmtree(testDir)

    def testUpdateBuild(self):
        # Test that build entries are getting into the DB properly
        updateBuild("branch1", "My Builder", "mybuilder", "slave01", "master01");
        updateBuild("branch1", "My Builder 2", "mybuilder2", "slave01", "master01");

        builds = getBuilds()
        # Strip out db id and time
        builds = [b[1:-1] for b in builds]
        builds.sort()
        self.assertEquals(len(builds), 2)
        self.assertEquals(builds[0],
                ("master01", "branch1", "My Builder", "mybuilder", "slave01"))
        self.assertEquals(builds[1],
                ("master01", "branch1", "My Builder 2", "mybuilder2", "slave01")
                )

    def testUpdateBuildWithClobber(self):
        # Test that build entries are getting into the DB properly
        # this time when a clobber is set
        now = int(time.time())
        setClobber("branch1", "mybuilder", "slave01", None, now)
        updateBuild("branch1", "My Builder", "mybuilder", "slave01", "master01");
        updateBuild("branch1", "My Builder 2", "mybuilder2", "slave01", "master01");

        builds = getBuilds()
        # Strip out db id and time
        builds = [b[1:-1] for b in builds]
        builds.sort()
        self.assertEquals(len(builds), 2)
        self.assertEquals(builds[0],
                ("master01", "branch1", "My Builder", "mybuilder", "slave01"))
        self.assertEquals(builds[1],
                ("master01", "branch1", "My Builder 2", "mybuilder2", "slave01")
                )

    def testSetSlaveClobber(self):
        # Clobber one builder on one slave, regardless of master
        now = int(time.time())
        setClobber("branch1", "mybuilder", "slave01", None, now)

        # Add a build on another builder, to make sure it's not getting
        # clobbered
        data = updateBuild("branch1", "My Builder 2", "mybuilder2", "slave01",
                "master01")
        self.assert_("mybuilder2" not in data, data)

        # Check that build on master01 gets clobbered
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master01")
        self.assertEquals(data, "mybuilder:%s:testuser" % now)

        # Check that build on master02 gets clobbered
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master02")
        self.assertEquals(data, "mybuilder:%s:testuser" % now)

    def testSetMasterClobber(self):
        # Clobber one builder on any slave on one master
        now = int(time.time())
        setClobber("branch1", "mybuilder", None, "master01", now)

        # Add a build on another builder, to make sure it's not getting
        # clobbered
        data = updateBuild("branch1", "My Builder 2", "mybuilder2", "slave01",
                "master01")
        self.assert_("mybuilder2" not in data, data)

        # Check that the build is clobbered on all slaves on master01
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master01")
        self.assertEquals(data, "mybuilder:%s:testuser" % now)
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave02",
                "master01")
        self.assertEquals(data, "mybuilder:%s:testuser" % now)

        # But not on master02
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master02")
        self.assertEquals(data, "")
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave02",
                "master02")
        self.assertEquals(data, "")

    def testSetSlaveMasterClobber(self):
        # Clobber one builder on one slave on one master
        now = int(time.time())
        setClobber("branch1", "mybuilder", "slave01", "master01", now)

        # Add a build on another builder, to make sure it's not getting
        # clobbered
        data = updateBuild("branch1", "My Builder 2", "mybuilder2", "slave01",
                "master01")
        self.assert_("mybuilder2" not in data, data)

        # Check that the build is clobbered on master01
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master01")
        self.assertEquals(data, "mybuilder:%s:testuser" % now)

        # But not on the other slave
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave02",
                "master01")
        self.assertEquals(data, "")

        # Or on the other master
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave01",
                "master02")
        self.assertEquals(data, "")
        data = updateBuild("branch1", "My Builder", "mybuilder", "slave02",
                "master02")
        self.assertEquals(data, "")

    def testSlaveClobber(self):
        # Test that the client will do a clobber if we tell it to
        now = int(time.time())

        makeBuildDir('mybuilder', now)
        setClobber('branch1', 'mybuilder', 'slave01', 'master01', now+1)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01')
        self.assert_('mybuilder:Server is forcing a clobber' in data, data)

    def testSlaveNoClobber(self):
        # Test that the client won't clobber if the server's clobber date is
        # too old
        now = int(time.time())

        makeBuildDir('mybuilder', now+1)
        setClobber('branch1', 'mybuilder', 'slave01', 'master01', now)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01')
        self.assert_('mybuilder:Server is forcing a clobber' not in data, data)

    def testSlaveClobberOther(self):
        # Test that other builders than the one we're running will get
        # clobbered
        now = int(time.time())

        makeBuildDir('mybuilder', now)
        makeBuildDir('linux_build', now)
        updateBuild('branch1', 'linux_build', 'linux_build', 'slave01',
                'master01')

        setClobber('branch1', 'mybuilder', 'slave01', 'master01', now-1)
        setClobber('branch1', 'linux_build', None, 'master01', now+1)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01')
        self.assert_('mybuilder:Server is forcing a clobber' not in data, data)
        self.assert_('linux_build:Server is forcing a clobber' in data, data)

    def testSlavePeriodicClobber(self):
        # Test that periodic clobbers happen if it's been longer than the
        # specified time since our last clobber
        now = int(time.time())

        makeBuildDir('mybuilder', now-3601)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01', 1)
        self.assert_('mybuilder:More than' in data, data)

    def testSlaveNoPeriodicClobber(self):
        # Test that periodic clobbers don't happen if it hasn't been longer
        # than the specified time since our last clobber
        now = int(time.time())

        makeBuildDir('mybuilder', now-3599)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01', 1)
        self.assert_('mybuilder:More than' not in data, data)

    def testSlaveNoPeriodicClobberOther(self):
        # Test that periodic clobbers don't happen on builders other than the
        # 'current' builder
        now = int(time.time())

        makeBuildDir('mybuilder', now-3599)
        makeBuildDir('mybuilder2', now-3601)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01', 1)
        self.assert_('mybuilder:More than' not in data, data)
        self.assert_('mybuilder2:More than' not in data, data)

        data = runClobberer('branch1', 'My Builder', 'mybuilder2', 'slave01',
                'master01', 1)
        self.assert_('mybuilder2:More than' in data, data)

    def testSlaveClobberRelease(self):
        # Test that clobbers on release builders work
        now = int(time.time())
        makeBuildDir('linux_build', now-10)
        updateBuild('branch1', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        updateBuild('branch2', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        now = int(time.time())
        setClobber('branch2', 'linux_build', None, None, now)

        data = runClobberer('branch2', 'Linux Release Build', 'linux_build',
                'slave01', 'master01')
        self.assert_('linux_build:Server is forcing' in data, data)

    def testSlaveClobberReleaseOtherBranch(self):
        # Test that clobbers on release builders work
        now = int(time.time())
        makeBuildDir('linux_build', now-10)
        updateBuild('branch1', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        updateBuild('branch2', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        setClobber('branch2', 'linux_build', None, None, now)

        # Even though we're running a different branch for _this_ run, our last
        # run was on branch2, so it should be clobbered
        data = runClobberer('branch1', 'Linux Release Build', 'linux_build',
                'slave01', 'master01')
        self.assert_('linux_build:Server is forcing' in data, data)

    def testSlaveClobberReleaseNotOtherBranch(self):
        # Test that clobbers on release builders don't clobber builds from
        # other branches
        now = int(time.time())
        makeBuildDir('linux_build', now-10)
        updateBuild('branch2', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        updateBuild('branch1', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        now = int(time.time())
        setClobber('branch2', 'linux_build', None, None, now)

        data = runClobberer('branch1', 'Linux Release Build', 'linux_build',
                'slave01', 'master01')
        self.assert_('linux_build:Server is forcing' not in data, data)

    def testSlaveClobberReleaseOtherBranchOtherBuilder(self):
        # Test that clobbers on release builders don't clobber builds from
        # other branches when run from another builder
        now = int(time.time())
        makeBuildDir('linux_build', now-10)
        updateBuild('branch1', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        updateBuild('branch2', 'linux_build', 'linux_build', 'slave01',
                'master01')
        time.sleep(1)
        now = int(time.time())
        setClobber('branch1', 'linux_build', None, None, now)

        data = runClobberer('branch1', 'My Builder', 'mybuilder', 'slave01',
                'master01')
        self.assert_('linux_build:Server is forcing' not in data, data)

    def testReleaseClobberPrefixBuilder(self):
        """Test that clobbers on release builders with the
        release-* prefix work"""
        now = int(time.time())
        makeBuildDir('release-mozilla-central-linux_build', now-10)
        updateBuild('branch2', 'release-mozilla-central-linux_build',
                'release-mozilla-central-linux_build', 'slave01', 'master01')
        time.sleep(1)
        data = setClobberPage('branch2', 'linux_build', None, None, now)
        self.assert_('release-mozilla-central-linux_build' in data, data)

if __name__ == '__main__':
    import unittest
    unittest.main()
