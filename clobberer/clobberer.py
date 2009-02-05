import sys, shutil, urllib2, urllib, os
from datetime import datetime, timedelta

def str_to_datetime(s):
  return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

def datetime_to_str(dt):
  return dt.strftime("%Y-%m-%d %H:%M:%S")

def write_file(dt, fn):
  assert isinstance(dt, datetime)
  dt = datetime_to_str(dt)
  f = open(fn, "w")
  f.write(dt)
  f.close()

def read_file(fn):
  if not os.path.exists(fn):
    return None

  data = open(fn).read().strip()
  try:
    return str_to_datetime(data)
  except ValueError:
    return None

def do_clobber(dryrun=False, skip=None):
  try:
    for f in os.listdir("."):
      if skip is not None and f in skip:
        print "Skipping", f
        continue
      if os.path.isfile(f):
        print "Removing", f
        if not dryrun:
          os.unlink(f)
      elif os.path.isdir(f):
        print "Removing %s/" % f
        if not dryrun:
          shutil.rmtree(f)
  except:
    print "Couldn't clobber properly, bailing out."
    sys.exit(1)

def getClobberDate(baseURL, branch, builder, slave):
  url = "%s?%s" % (baseURL,
      urllib.urlencode(dict(branch=branch, builder=builder, slave=slave)))
  print "Checking clobber URL: %s" % url
  data = urllib2.urlopen(url).read().strip()
  try:
    return str_to_datetime(data)
  except ValueError:
    return None

if __name__ == "__main__":
  from optparse import OptionParser
  parser = OptionParser()
  parser.add_option("-n", "--dry-run", dest="dryrun", action="store_true",
      default=False, help="don't actually delete anything")
  parser.add_option("-t", "--periodic", dest="period", type="float",
      default=24*7, help="hours between periodic clobbers")
  parser.add_option('-s', '--skip', help='do not delete this directory',
      action='append', dest='skip', default=['last-clobber'])

  options, args = parser.parse_args()
  periodicClobberTime = timedelta(hours = options.period)

  baseURL, branch, builder, slave = args

  try:
    server_clobber_date = getClobberDate(baseURL, branch, builder, slave)
  except:
    print "Error contacting server"
    sys.exit(1)

  our_clobber_date = read_file("last-clobber")

  clobber = False

  print "Our last clobber date: ", our_clobber_date
  print "Server clobber date:   ", server_clobber_date

  if server_clobber_date is not None:
    # If the server is giving us a clobber date, compare the server's idea of
    # the clobber date to our last clobber date
    if our_clobber_date is None or server_clobber_date > our_clobber_date:
      # If we've never been clobbered, or if the server's clobber date is greater
      # than our last clobber date, then we should clobber.
      clobber = True
      # We should also update our clobber date to match the server's
      our_clobber_date = server_clobber_date
      print "Server is forcing a clobber"

  if not clobber:
    # Next, check if more than the periodicClobberTime period has passed since
    # our last clobber
    if our_clobber_date is None:
      # We've never been clobbered
      # Set our last clobber time to now, so that we'll clobber
      # properly after periodicClobberTime
      our_clobber_date = datetime.utcnow()
      write_file(our_clobber_date, "last-clobber")
    elif datetime.utcnow() > our_clobber_date + periodicClobberTime:
      # periodicClobberTime has passed since our last clobber
      clobber = True
      # Update our clobber date to now
      our_clobber_date = datetime.utcnow()
      print "More than %s have passed since our last clobber" % periodicClobberTime

  if clobber:
    # Finally, perform a clobber if we're supposed to
    print "Clobbering..."
    do_clobber(options.dryrun, options.skip)
    write_file(our_clobber_date, "last-clobber")
