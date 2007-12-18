from datetime import datetime, timedelta
import time
import random

from status import *

def create():
  for i in range(15):
    dt = datetime.utcnow() +  i * timedelta(0, 15*60)
    b = Build()
    b.locale = 'en-US'
    b.platform = random.choice(['win32','linux','mac'])
    b.branch = 'MOZILLA_1_8_BRANCH'
    b.startTime = dt
    b.endTime = dt + timedelta(0, 10*60)
    b.sourceTime = dt - timedelta(0, 2*60)
    b.status = 'success'
    session.save(b)

  session.flush()
  builds = session.query(Build)
  for i in range(40):
    b = Repack()
    b.locale = random.choice(['de','fr','pl','zh-CN','zu'])
    b.branchTime = datetime.utcnow()
    b.branch = 'HEAD'
    b.status = random.choice(['success','success','busted','warn'])
    if b.status != 'busted':
      packed = builds.get(random.randint(1,15))
      print type(packed)
      b.packaged_build_id = packed.build_id
    session.save(b)
  
  session.flush()
