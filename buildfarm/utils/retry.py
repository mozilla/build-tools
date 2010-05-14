#!/usr/bin/python
"""retry.py [options] cmd [arg arg1 ...]

Retries cmd and args with configurable timeouts and delays between retries.

Return code is 0 if cmd succeeds, and is 1 if cmd fails after all the retries.
"""

import time, subprocess, logging, os, sys
log = logging.getLogger()

if sys.platform.startswith('win'):
    from win32_util import kill, which
else:
    from unix_util import kill

def run_with_timeout(cmd, timeout):
    proc = subprocess.Popen(cmd)
    start_time = time.time()
    log.info("Executing: %s", cmd)
    while True:
        rc = proc.poll()
        if rc is not None:
            log.debug("Process returned %s", rc)
            return rc == 0

        if start_time + timeout < time.time():
            log.warn("WARNING: Timeout (%i) exceeded, killing process %i", timeout,
                     proc.pid)
            rc = kill(proc.pid)
            log.debug("Process returned %s", rc)
            return False

        # Check again in a sec...
        time.sleep(0.25)

def retry_command(cmd, retries, timeout, sleeptime):
    # Which iteration we're on
    i = 0

    # Current return code
    rc = False

    while True:
        i += 1

        rc = run_with_timeout(cmd, timeout)

        if rc:
            break

        if retries > 0 and i >= retries:
            log.info("Number of retries exceeded maximum (%i), giving up.",
                     retries)
            break

        if sleeptime:
            log.info("Sleeping for %i.", sleeptime)
            time.sleep(sleeptime)

    return rc

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(__doc__)
    parser.disable_interspersed_args()

    parser.add_option("-r", "--retries", type="int", dest="retries", 
                      help="""retry this many times.  Set 0 to retry forever.
                      Defaults to 10""")
    parser.add_option("-t", "--timeout", type="int", dest="timeout",
                      help="""timeout each request after this many seconds.  Set
                      to 0 to have no timeout.  Defaults to 300""")
    parser.add_option("-s", "--sleeptime", type="int", dest="sleeptime",
                      help="""sleep this many seconds between tries.
                      Defaults to 30""")

    parser.set_defaults(
            retries=10,
            timeout=300,
            sleeptime=30,
            )

    options, args = parser.parse_args()

    if len(args) == 0:
        parser.error("Command argument missing")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Another dirty hack... :(
    # Special care for programs w/o extensions on Windows
    if sys.platform.startswith('win') and  not os.path.splitext(args[0])[1]:
        args[0] = which(args[0])

    try:
        if not retry_command(args, retries=options.retries,
                             timeout=options.timeout,
                             sleeptime=options.sleeptime):
            sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
