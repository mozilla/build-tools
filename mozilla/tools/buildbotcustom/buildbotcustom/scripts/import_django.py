import os, sys, re, pickle
from glob import glob
import time
from datetime import datetime

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from buildbotcustom.builds.models import *
from buildbotcustom.status.dbbuilds import updateBuildFrom

isBuild = re.compile('/\d+$')

for bname in sys.argv[1:]:
  print "importing " + bname
  builder,created = Builder.objects.get_or_create(name=bname)

  buildFiles = [f for f in glob(bname + '/*') if isBuild.search(f)]

  for f in buildFiles:
    bs = pickle.load(open(f, 'rb'))
    b, created = builder.builds.get_or_create(builder=builder,
                                              buildnumber=bs.getNumber())
    if not created:
      # we already have this build
      continue
    updateBuildFrom(b, bs)
