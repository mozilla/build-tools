import unittest

from models import *

class Models(unittest.TestCase):
  '''Testing the basic functionality of the model wrapper classes
  and the db impl'''

  def tearDown(self):
    '''tearDown needs to prune the test database as far as possible'''
    Change.objects.all().delete()
    Property.objects.all().delete()
    Build.objects.all().delete()
    Builder.objects.all().delete()

  def createBuilder(self):
    return Builder.objects.get_or_create(name="testBuilder")
  def testBuilder(self):
    builder, created = self.createBuilder()
    self.assert_(created)
    self.assertEquals(builder.name, "testBuilder")
    self.assertEquals(builder.basedir, None)
    self.assertEquals(builder.category, None)

  def createBuild(self, number = 0):
    builder, created = self.createBuilder()
    build, created = Build.objects.get_or_create(builder = builder,
                                                 buildnumber = number)
    return build, builder, created
  def testBuild(self):
    build, builder, created = self.createBuild()
    self.assert_(created)
    self.assertEquals(build.builder, builder)

  def testProperties(self):
    build = self.createBuild()[0]

    build.setProperty('first', 'first value')
    self.assertEquals(Property.objects.count(), 1)
    self.assertEquals(Property.objects.filter(name='first').count(), 1)
    # check json encoding
    self.assertEquals(Property.objects.get(name='first').value,
                      '"first value"')

    build.setProperty('second', 'other value')
    self.assertEquals(Property.objects.count(), 2)
    self.assertEquals(Property.objects.filter(name='second').count(), 1)
    # check json encoding
    self.assertEquals(Property.objects.get(name='second').value,
                      '"other value"')

    build.setProperty('first', 'another first value')
    self.assertEquals(Property.objects.count(), 2)
    self.assertEquals(Property.objects.filter(name='first').count(), 1)
    # check json encoding
    self.assertEquals(Property.objects.get(name='first').value,
                      '"another first value"')

  def testChanges(self):
    build1 = self.createBuild(0)[0]
    build2 = self.createBuild(1)[0]
    c, created = Change.objects.get_or_create(pk=1)
    self.assert_(created)
    build1.changes.add(c)
    build2.changes.add(c)
    build1.changes.clear()
    self.assertEquals(build2.changes.count(), 1)
    self.assertEquals(build2.changes.all()[0].id, 1)
    self.assertEquals(build1.changes.count(), 0)
