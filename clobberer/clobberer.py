import sys, shutil, urllib2, urllib, os
from datetime import datetime, timedelta

clobber_suffix='.deleteme'

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

def rmdirRecursive(dir):
    """This is a replacement for shutil.rmtree that works better under
    windows. Thanks to Bear at the OSAF for the code.
    (Borrowed from buildbot.slave.commands)"""
    if not os.path.exists(dir):
        # This handles broken links
        if os.path.islink(dir):
            os.remove(dir)
        return

    if os.path.islink(dir):
        os.remove(dir)
        return

    # Verify the directory is read/write/execute for the current user
    os.chmod(dir, 0700)

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                # I think this is now redundant, but I don't have an NT
                # machine to test on, so I'm going to leave it in place
                # -warner
                os.chmod(full_name, 0600)

        if os.path.isdir(full_name):
            rmdirRecursive(full_name)
        else:
            # Don't try to chmod links
            if not os.path.islink(full_name):
                os.chmod(full_name, 0700)
            os.remove(full_name)
    os.rmdir(dir)

def do_clobber(dir, dryrun=False, skip=None):
  try:
    for f in os.listdir(dir):
      if skip is not None and f in skip:
        print "Skipping", f
        continue
      clobber_path=f+clobber_suffix
      if os.path.isfile(f):
        print "Removing", f
        if not dryrun:
          if os.path.exists(clobber_path):
            os.unlink(clobber_path)
          # Prevent repeated moving.
          if f.endswith(clobber_suffix):
            os.unlink(f)
          else:
            shutil.move(f, clobber_path)
            os.unlink(clobber_path)
      elif os.path.isdir(f):
        print "Removing %s/" % f
        if not dryrun:
          if os.path.exists(clobber_path):
            rmdirRecursive(clobber_path)
          # Prevent repeated moving.
          if f.endswith(clobber_suffix):
            rmdirRecursive(f)
          else:              
            shutil.move(f, clobber_path)
            rmdirRecursive(clobber_path)
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
  parser.add_option('-d', '--dir', help='clobber this directory',
      dest='dir', default='.', type='string')

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

  # If we don't have a last clobber date, then this is probably a fresh build.
  # We should only do a forced server clobber if we know when our last clobber
  # was, and if the server date is more recent than that.
  if server_clobber_date is not None and our_clobber_date is not None:
    # If the server is giving us a clobber date, compare the server's idea of
    # the clobber date to our last clobber date
    if server_clobber_date > our_clobber_date:
      # If the server's clobber date is greater than our last clobber date,
      # then we should clobber.
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
    if os.path.exists(options.dir):
      print "Clobbering..."
      do_clobber(options.dir, options.dryrun, options.skip)
    else:
      print "Clobber failed because '%s' doesn't exist" % options.dir
    write_file(our_clobber_date, "last-clobber")
