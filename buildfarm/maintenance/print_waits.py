import cPickle, os, re, math, time

def format_hist(h, units=1):
    retval = []
    if not h:
        h[0] = 0
    keys = sorted(h.keys())
    min_key = min(keys)
    max_key = max(keys)

    for i in range(min_key, max_key+1):
        n = h.get(i, 0)
        bar = "#" * n

        retval.append("%4i %s (%i)" % (i*units, bar, n))
    return "\n".join(retval)

def scan_builder(builder, starttime, endtime, minutes_per_block, times, change_as_submittime=True):
    """Scans the build pickle files in the builder directory, and updates the dictionary `times`."""
    if not os.path.exists(builder):
        return
    for f in os.listdir(builder):
        if re.match("^\d+$", f):
            try:
                b = cPickle.load(open('%s/%s' % (builder, f)))
            except:
                continue

            if change_as_submittime:
                if len(b.changes) == 0:
                    continue
                submittime = b.changes[0].when
            else:
                submittime = b.requests[0].submittedAt

            if starttime < submittime < endtime:
                w = int(math.floor((b.started - submittime)/(minutes_per_block*60.0)))
                times[w] = times.get(w, 0) + 1

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.set_defaults(
            minutes_per_block=15,
            change_as_submittime=True,
            name=os.uname()[1],
            builders={},
            directory=None,
            starttime=time.time()-24*3600,
            endtime=time.time(),
            )

    def add_builder(option, opt_str, value, parser, *args, **kwargs):
        if ":" in value:
            platform, builders = value.split(":", 1)
            builders = [b.strip() for b in builders.split(",")]
        else:
            platform = value
            builders = [platform]

        if platform not in parser.values.builders:
            parser.values.builders[platform] = []

        parser.values.builders[platform].extend(builders)

    parser.add_option("-m", "--minutes-per-block", type="int", help="How many minutes per block", dest="minutes_per_block")
    parser.add_option("-r", "--request-as-submittime", action="store_false", dest="change_as_submittime")
    parser.add_option("-n", "--name", dest="name")
    parser.add_option("-b", "--builders", dest="builders", action="callback", nargs=1, type="string", callback=add_builder, help="platform:builder1,builder2,...")
    parser.add_option("-d", "--directory", dest="directory")
    parser.add_option("-s", "--start-time", dest="starttime", type="int")
    parser.add_option("-e", "--end-time", dest="endtime", type="int")

    options, args = parser.parse_args()

    if not options.builders:
        parser.error("Must specify some builders")

    if options.directory:
        os.chdir(options.directory)

    print "Wait time report for %s for jobs submitted since" % options.name, time.ctime(options.starttime)
    print

    for platform, builders in options.builders.items():
        hist = {}
        for builder in builders:
            scan_builder(builder, options.starttime, options.endtime, options.minutes_per_block, hist, options.change_as_submittime)

        print platform
        print format_hist(hist, options.minutes_per_block)
        print

    print "The number on the left is how many minutes a build waited to start, rounded down"
    print "The number of hashes indicates how many builds waited that long"
