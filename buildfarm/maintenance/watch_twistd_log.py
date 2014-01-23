#!/usr/bin/python
# Script for watching twistd.log and looking for exceptions, and mailing them
# to an email address
"""%prog [options] dir [dir...]

Scans directories for exceptions in twistd.log files"""

import os
import re
import time
from smtplib import SMTP
from email.mime.text import MIMEText
import email.utils


def find_files(dirs, lasttime):
    """Return a list of twisted log files in directories `dirs` that have been
    modified since `lasttime`"""
    retval = []
    for d in dirs:
        for f in os.listdir(d):
            if not f.startswith("twistd.log"):
                continue

            f = os.path.join(d, f)
            mtime = os.path.getmtime(f)
            if mtime > lasttime:
                retval.append((mtime, f))

    retval.sort()
    return [r[1] for r in retval]


def send_msg(fromaddr, emails, hostname, excs, name):
    """Send an email to each address in `emails`, from `fromaddr`

    The message will contain the hostname and list of exceptions `excs`"""
    msg = "The following exceptions (total %i) were detected on %s %s:\n\n" % (
        len(excs), hostname, name)
    msg += ("\n" + "-" * 80 + "\n").join(excs)

    s = SMTP()
    s.connect()

    for addr in emails:
        m = MIMEText(msg)
        m['date'] = email.utils.formatdate()
        m['to'] = addr
        m['subject'] = "twistd.log exceptions on %s %s" % (hostname, name)
        s.sendmail(fromaddr, [addr], m.as_string())

    s.quit()


def parse_time(line):
    """Returns a timestamp from a datestring in the given line"""
    m = re.search("(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if m:
        return time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))

    return None


class Scanner:
    ignore_patterns = [
        re.compile(re.escape("Failure: twisted.spread.pb.PBConnectionLost: [Failure instance: Traceback (failure with no frames): <class 'twisted.internet.error.ConnectionLost'>: Connection to the other side was lost in a non-clean fashion.")),
        re.compile("schedulers/triggerable.py\", line \d+, in run.*d = self.parent.db.runInteraction\(self._run\).*exceptions.AttributeError: 'NoneType' object has no attribute 'db'", re.M + re.S),
        # Ignore errors caused by older buildbot versions on the masters.
        re.compile(re.escape("exceptions.AttributeError: BuildSlave instance has no attribute 'perspective_shutdown'")),
        # Ignore users cancelling try runs
        re.compile(re.escape("Failure: exceptions.RuntimeError")),
        # Ignore clean-close "errors" from tegras
        re.compile(re.escape("Failure: twisted.spread.pb.PBConnectionLost: [Failure instance: Traceback (failure with no frames): <class 'twisted.internet.error.ConnectionDone'>: Connection was closed cleanly")),
        # Ignore stale broker refs we can't do anything about.
        re.compile("twisted.spread.pb.DeadReferenceError: Calling Stale Broker"),
        # Ignore exceptions triggered by NoneType objects.
        re.compile(re.escape("exceptions.AttributeError: 'NoneType' object has no attribute")),
        # Ignore PB connect errors.
        re.compile(re.escape("Failure: twisted.spread.pb.PBConnectionLost: [Failure instance: Traceback (failure with no frames): <class 'socket.error'>: [Errno 9] Bad file descriptor")),
    ]

    def __init__(self, lasttime=0):
        # Buffer of unhandled lines
        self.lasttime = lasttime

    def scan_file(self, f):
        """Scans file `f` for exceptions.

        Returns a list of exception logs"""
        current_exc = None
        retval = []
        for line in open(f):
            # If we're processing an exception log, append this line to the
            # current exception
            if current_exc is not None:
                # Blank lines mean the end of the exception
                if line.strip() == "":
                    current_exc = "".join(current_exc)
                    for p in self.ignore_patterns:
                        if p.search(current_exc):
                            break
                    else:
                        retval.append(current_exc)
                    current_exc = None
                else:
                    current_exc.append(line)
            elif line.strip().endswith("Unhandled Error"):
                # Ignore exceptions in this file that are older than
                # lasttime
                t = parse_time(line)
                if not t:
                    print "Couldn't parse time in", line
                elif t > self.lasttime:
                    current_exc = [line]

        # Handle exceptions printed out at the end of the file
        if current_exc:
            current_exc = "".join(current_exc)
            for p in self.ignore_patterns:
                if p.search(current_exc):
                    break
            else:
                retval.append(current_exc)

        return retval

    def scan_dirs(self, dirs):
        retval = []
        new_lasttime = self.lasttime

        # Find which files are newer than lasttime
        # This won't handle the case where the logs are rotated while this
        # script is running. FIXME?
        files = find_files(dirs, self.lasttime)
        for f in files:
            for e in self.scan_file(f):
                retval.append("Exception in %s:\n%s" % (f, e))
            new_lasttime = max(new_lasttime, os.path.getmtime(f))
        self.lasttime = new_lasttime

        return retval

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-t", "--timefile", dest="timefile",
                      help="where to save time of last handled file")
    parser.add_option("-e", "--email", dest="emails", action="append",
                      help="email address to send exceptions to")
    parser.add_option("-f", "--fromaddr", dest="fromaddr",
                      help="From address for email notifications")
    parser.add_option("-n", "--name", dest="name", help="Short description")

    parser.set_defaults(
        emails=[],
        fromaddr="reply@not.possible",
    )

    options, args = parser.parse_args()

    if len(args) < 1:
        parser.error("Must specify at least one directory to scan")

    # Try and get the time we last ran from the timefile
    lasttime = 0
    if options.timefile:
        try:
            lasttime = float(open(options.timefile).read())
        except:
            pass

    exceptions = []
    s = Scanner(lasttime)
    exceptions.extend(s.scan_dirs(args))

    if exceptions:
        if options.emails:
            hostname = os.uname()[1]
            send_msg(options.fromaddr, options.emails,
                     hostname, exceptions, options.name)
        else:
            print "\n".join(exceptions)

    if options.timefile:
        open(options.timefile, "w").write(str(s.lasttime))
