from sqlalchemy import *
from sqlalchemy.orm import *

from datetime import datetime
import time
import random
from enum import Enum

db = create_engine('sqlite:///builds.db')

metadata = MetaData(db)

builds_table = Table('builds', metadata,
                     Column('build_id', Integer, primary_key=True),
                     Column('type', Enum(['clobber', 'depend', 'repack', 'langpack'])),
                     Column('product', String),
                     Column('platform', String),
                     Column('branch', String),
                     Column('locale', String),
                     Column('startTime', DateTime),
                     Column('endTime', DateTime),
                     Column('sourceTime', DateTime),
                     Column('status', String))

if not builds_table.exists():
  builds_table.create()

repacks_table = Table('repacks', metadata,
                      Column('build_id', Integer,
                             ForeignKey('builds.build_id'), primary_key=True),
                      Column('enUSbranch', String),
                      Column('enUSsourceTime', DateTime),
                      Column('packaged_build_id', Integer,
                             ForeignKey('builds.build_id')))

if not repacks_table.exists():
  repacks_table.create()

l10n_tests_table = Table('l10n_tests', metadata,
                         Column('run', Integer, primary_key=True),
                         Column('build_id', Integer,
                                ForeignKey('builds.build_id')),
                         Column('missing', Integer),
                         Column('changed', Integer),
                         Column('unchanged', Integer),
                         Column('keys', Integer))
if not l10n_tests_table.exists():
  l10n_tests_table.create()

files_table = Table('files', metadata,
                    Column('id', Integer, primary_key=True),
                    Column('module', String),
                    Column('path', String))
if not files_table.exists():
  files_table.create()
                    
entities_table = Table('entities', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('file', Integer, ForeignKey('files.id')),
                       Column('key', String))
if not entities_table.exists():
  entities_table.create()

compare_details_table = Table('compare_details', metadata,
                              Column('id', Integer, primary_key=True),
                              Column('build', Integer,
                                     ForeignKey('l10n_tests_table.run')),
                              Column('entity', Integer,
                                     ForeignKey('entities.id')),
                              Column('is_missing', Boolean))
if not compare_details_table.exists():
  compare_details_table.create()

print builds_table.c.keys()

class Build(object):
  def __init__(self, clobber=True):
    if clobber:
      self.type = 'clobber'
    else:
      self.type = 'depend'
    self.start_now()
  
  def start_now(self):
    self.startTime = datetime.utcnow()
  
  def finish_now(self):
    self.endTime = datetime.utcnow()
  
  def __repr__(self):
    build_id = 'TBD'
    if self.build_id:
      build_id = str(self.build_id)
    return "Build %s" % build_id

class Repack(Build):
  def __init__(self):
    self.start_now()
    self.type = 'repack'
  
  def __repr__(self):
    build_id = 'TBD'
    if self.build_id:
      build_id = str(self.build_id)
    locale = 'x-UNKNOWN'
    if self.locale:
      locale = self.locale
    return 'Repack (Build %s, %s)' % (build_id, locale)

class L10nTestResult(object):
  def __init__(self):
    pass
  def __repr__(self):
    f = 'passed'
    if self.missing:
      f = 'failed'
    return 'L10n test %d (%s)' % (self.run, f)

build_mapper = mapper(Build, builds_table,
                      properties = {'localizations':
                                    relation(Repack,
                                             primaryjoin=builds_table.c.build_id==repacks_table.c.packaged_build_id,
                                             backref='repacked_build')})

l10n_mapper = mapper(Repack, repacks_table, inherits=build_mapper,
                     inherit_condition=builds_table.c.build_id==repacks_table.c.build_id)

l10n_test_mapper = mapper(L10nTestResult, l10n_tests_table,
                          properties = {'build':
                                          relation(Repack)})

session = create_session()
