import time
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import create_engine, MetaData, Table, Column, \
    String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import sessionmaker, mapper, relation

engine = create_engine('sqlite:///builds.txt')
Session = sessionmaker(bind=engine, autoflush=True, transactional=True)

metadata = MetaData()
builds_table = Table('builds', metadata,
                     Column('id', Integer, primary_key=True),
                     Column('buildername', String(30), index=True),
                     Column('slavename', String(30)),
                     Column('buildnumber', Integer),
                     Column('locale', String(30), index=True),
                     Column('app', String(30), index=True),
                     Column('tree', String(20), index=True),
                     Column('l10nchange', Boolean),
                     Column('starttime', DateTime, index=True),
                     Column('endtime', DateTime, index=True),
                     Column('c_missing', Integer, index=True),
                     Column('c_missingInFiles', Integer, index=True),
                     Column('c_obsolete', Integer, index=True),
                     Column('c_total', Integer),
                     Column('c_changed', Integer),
                     Column('c_unchanged', Integer),
                     Column('c_keys', Integer),
                     Column('c_completion', Integer),
                     Column('results', Integer))

active_table = Table('active', metadata,
                     Column('id', Integer, primary_key=True),
                     Column('buildername', String(30), index=True),
                     Column('locale', String(30), index=True),
                     Column('app', String(30), index=True),
                     Column('tree', String(20), index=True),
                     UniqueConstraint('buildername', 'tree',
                                      'app', 'locale'))


metadata.create_all(engine)

class Build(object):
  def __init__(self, bs):
    for k in ['buildername', 'slavename', 'buildnumber', 'locale','app','tree']:
      setattr(self, k, bs.getProperty(k))
    l10nchange = False
    prefix = 'l10n/' + self.locale
    def isL10n(bs_):
      for c in bs_.getChanges():
        if hasattr(c, 'locale') and c.locale is self.locale:
          return True
        for f in c.files:
          if f.startswith(prefix):
            return True
      return False
    self.l10nchange = isL10n(bs)
    self.results = bs.getResults()
    times = map(round, bs.getTimes())
    self.starttime = datetime.utcfromtimestamp(times[0])
    self.endtime = datetime.utcfromtimestamp(times[1])
    summary = bs.getProperty('coverage-result')
    for k in ['completion', 'missing', 'keys', 'unchanged', 'changed',
              'missingInFiles', 'obsolete', 'total']:
      setattr(self, 'c_' + k, (k in summary and summary[k]) or 0)

  def tuple(self):
    return (self.buildername, self.tree, self.app, self.locale)

  def dict(self):
    return dict(buildername = self.buildername,
                tree = self.tree,
                app = self.app,
                locale = self.locale)

  def __repr__(self):
    return "<Build (%s/%d)>" % (self.buildername, self.buildnumber)

mapper(Build, builds_table)


class Active(object):
  def __init__(self, build):
    self.buildername = build.buildername
    self.tree = build.tree
    self.app = build.app
    self.locale = build.locale
  def tuple(self):
    return (self.buildername, self.tree, self.app, self.locale)
  def dict(self):
    return dict(buildername = self.buildername,
                tree = self.tree,
                app = self.app,
                locale = self.locale)
  def __repr__(self):
    return "<active>"

mapper(Active, active_table)

session = Session()

q = session.query(Build)

# not yet used

def computeStats(days = 5):
  now = datetime.utcnow()
  cut = now - timedelta(days)
  class td(timedelta):
    def __floordiv__(self, other):
      othersec = other.days * 60.0 * 60 * 24 + other.seconds\
          + other.microseconds * 0.001
      selfsec = self.days * 60.0 * 60 * 24 + self.seconds\
          + self.microseconds * 0.001
      return int(selfsec // othersec)
    def __iadd__(self, other):
      return type(self).fromdelta(self + other)
    @classmethod
    def fromdelta(cls, other):
      return cls(days = other.days, seconds = other.seconds,
                 microseconds = other.microseconds)
  class V:
    def __init__(self):
      self.start = cut
      self.build = None
      self.last = 0
      self.w_miss = td()
    def update(self, build):
      if not self.build:
        self.last = build.c_missing + build.c_missingInFiles
        self.build = build
        self.start = max(cut, build.starttime)
        return
      # got results, really update
      self.w_miss += self.last * (build.starttime - self.build.starttime)
      self.build = build
      self.last = build.c_missing + build.c_missingInFiles
    def finalize(self, dt):
      self.w_miss += self.last * (dt - self.build.starttime)
      self.out = self.w_miss // (dt - self.start)

  stats = defaultdict(V)
  for act in session.query(Active):
    print act.tuple()
    b = q.filter_by(**act.dict()).order_by(Build.starttime.desc()).filter(Build.starttime < cut).first()
    if b:
      stats[act.tuple()].update(b)
  # update with all current builds
  for b in q.filter(Build.starttime >= cut):
    stats[b.tuple()].update(b)
  # finalize stats
  items = []
  for k, v in stats.iteritems():
    v.finalize(now)
    item = dict((k, getattr(v.build, k)) for k in v.build.c.keys())
    item['id'] = '/'.join(k)
    item['label'] = item['locale']
    item['starttime'] = item['starttime'].isoformat() + 'Z'
    item['endtime'] = item['endtime'].isoformat() + 'Z'
    item['weighted_red'] = v.out
    item['type'] = 'Build2'
    items.append(item)
  return items
