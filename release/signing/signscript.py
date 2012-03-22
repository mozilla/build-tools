#!/usr/bin/python
"""%prog [options] format inputfile outputfile inputfilename"""
from signing import copyfile, signfile, shouldSign, gpg_signfile, safe_unlink, mar_signfile, dmg_signpackage
import os
import logging
import sys

if __name__ == '__main__':
    from optparse import OptionParser
    from ConfigParser import RawConfigParser

    parser = OptionParser(__doc__)
    parser.set_defaults(
            fake=False,
            signcode_keydir=None,
            gpg_homedir=None,
            loglevel=logging.INFO,
            configfile=None,
            mar_cmd=None,
        )
    parser.add_option("--keydir", dest="signcode_keydir",
            help="where MozAuthenticode.spc, MozAuthenticode.spk can be found")
    parser.add_option("--gpgdir", dest="gpg_homedir",
            help="where the gpg keyrings are")
    parser.add_option("--mac_id", dest="mac_id",
            help="the mac signing identity")
    parser.add_option("--dmgkeychain", dest="dmg_keychain",
            help="the mac signing keydir")
    parser.add_option("--fake", dest="fake", action="store_true",
            help="do fake signing")
    parser.add_option("-c", "--config", dest="configfile",
            help="config file to use")
    parser.add_option("-v", action="store_const", dest="loglevel", const=logging.DEBUG)

    options, args = parser.parse_args()

    if options.configfile:
        config = RawConfigParser()
        config.read(options.configfile)
        for option, value in config.items('signscript'):
            options.ensure_value(option, value)

    logging.basicConfig(level=options.loglevel, format="%(asctime)s - %(message)s")

    if len(args) != 4:
        parser.error("Incorrect number of arguments")

    format_, inputfile, destfile, filename = args

    tmpfile = destfile + ".tmp"

    passphrase = sys.stdin.read().strip()
    if passphrase == '':
        passphrase = None

    if format_ == "signcode":
        if not options.signcode_keydir:
            parser.error("keydir required when format is signcode")
        copyfile(inputfile, tmpfile)
        if shouldSign(filename):
            signfile(tmpfile, options.signcode_keydir, options.fake, passphrase)
        else:
            parser.error("Invalid file for signing: %s" % filename)
            sys.exit(1)
    elif format_ == "gpg":
        if not options.gpg_homedir:
            parser.error("gpgdir required when format is gpg")
        safe_unlink(tmpfile)
        gpg_signfile(inputfile, tmpfile, options.gpg_homedir, options.fake, passphrase)
    elif format_ == "mar":
        if not options.mar_cmd:
            parser.error("mar_cmd is required when format is mar")
        safe_unlink(tmpfile)
        mar_signfile(inputfile, tmpfile, options.mar_cmd, options.fake, passphrase)
    elif format_ == "dmg":
        if not options.dmg_keychain:
            parser.error("dmg_keychain required when format is dmg")
        if not options.mac_id:
            parser.error("mac_id required when format is dmg")
        safe_unlink(tmpfile)
        dmg_signpackage(inputfile, tmpfile, options.dmg_keychain, options.mac_id, options.fake, passphrase)

    os.rename(tmpfile, destfile)
