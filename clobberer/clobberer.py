import sys, shutil, urllib2, urllib, os
from datetime import datetime, timedelta
PERIODIC_CLOBBER_TIME = timedelta(days=7)

def str_to_datetime(str):
  return datetime.strptime(str, "%Y-%m-%d %H:%M:%S")

def datetime_to_str(dt):
  return dt.strftime("%Y-%m-%d %H:%M:%S")

def write_file(dt, file):
  if isinstance(dt, datetime):
    dt = datetime_to_str(dt)
  f = open(file, "w")
  f.write(dt)
  f.close()

def do_clobber():
  try:
    if os.path.exists("build"):
      print "Clobbering build directory"
      shutil.rmtree("build")
  except:
    print "Couldn't clobber properly, bailing out."
    sys.exit(1)

url, = sys.argv[1:]
url = urllib.quote(url, ":=?/~")

try:
  print "Checking clobber URL: %s" % url
  cur_force_date = urllib2.urlopen(url).read()
  print "Current forced clobber date: %s" % cur_force_date
  if not os.path.exists("force-clobber"):
    write_file(cur_force_date, "force-clobber")
  else:
    old_force_date = open("force-clobber").read()
    print "Last forced clobber: %s" % old_force_date
    if old_force_date != cur_force_date:
      print "Clobber forced"
      do_clobber()
      write_file(cur_force_date, "force-clobber")
      write_file(cur_force_date, "last-clobber")
      sys.exit(0)
except SystemExit:
  # make sure to let sys.exit() through
  pass
except:
  print "Couldn't poll %s, skipping forced clobber" % url
  
if not os.path.exists("last-clobber"):
  write_file(datetime.utcnow(), "last-clobber")
else:
  last_clobber = str_to_datetime(open("last-clobber").read())
  cur_date = datetime.utcnow()
  print "Last clobber: %s" % datetime_to_str(last_clobber)
  print "Current time: %s" % datetime_to_str(cur_date)
  if (last_clobber + PERIODIC_CLOBBER_TIME < cur_date):
    print "More than %s have passed since the last clobber, clobbering "
    print "build directory" % PERIODIC_CLOBBER_TIME
    do_clobber()
    # if do_clobber fails the script will exit and this will not be executed
    write_file(cur_date, "last-clobber")

