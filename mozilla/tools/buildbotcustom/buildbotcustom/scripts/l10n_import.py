from optparse import OptionParser

usage = '%prog builder-name [startbuild [endbuild]]'
p = OptionParser(usage=usage)

opts, args = p.parse_args()

if len(args) < 1:
  p.error('builder name required')

buildername = args.pop(0)

import pickle
builder = pickle.load(open(buildername + '/builder'))
builder.basedir = buildername
builder.determineNextBuildNumber()

from buildbotcustom.status import l10ndb
from sqlalchemy.exceptions import IntegrityError

try:
  startbuild = int(args.pop(0))
except IndexError:
  try:
    startbuild = l10ndb.q.filter_by(buildername=buildername).order_by(l10ndb.Build.buildnumber.desc()).first().buildnumber + 1
  except:
    startbuild = 0
try:
  endbuild = int(args.pop(0))
except IndexError:
  endbuild = builder.nextBuildNumber

kinds = {}

for build in xrange(startbuild, endbuild):
  bs = builder.getBuild(build)
  b = l10ndb.Build(bs)
  l10ndb.session.save(b)
  kinds[(b.buildername, b.tree, b.app, b.locale)] = b

l10ndb.session.commit()

q = l10ndb.session.query(l10ndb.Active)

for kind, b in kinds.iteritems():
  if not q.filter_by(**dict(zip(['buildername', 'tree', 'app', 'locale'],
                                kind))).first():
    a = l10ndb.Active(b)
    l10ndb.session.save(a)
l10ndb.session.commit()
