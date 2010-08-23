#!/usr/bin/env python

from getpass import getpass
from optparse import OptionParser
import os, sys
import subprocess

from string import Template

"""mozpass.py

mozpass takes any parameters given to it as a command and its parameters
to process thru a very basic template replacement routine.

This modified parameter list and the command is then executed and its output
is sent to stdout (piping stderr to stdout)

The command line is not echoed to allow for password replacement to happen
without those password values to be in the output.

Replacement values are pulled from a mozpass.cfg file which lives by default in
~/.mozpass.cfg

If you call mozpass.py with no parameters it will perform a series of doctests.

Sample mozpass.cfg:

param1=value1
param2=value2

Usage:
    mozpass.py <signing target>
"""



def doCommand(cmd, env=None):
    """Execute the given command and print to stdout any output
    Pipes stderr to stdout
    
    >>> doCommand(['echo', 'foo'])
    foo
    <BLANKLINE>
    """
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    o = ''

    try:
        for item in p.stdout:
            o += item
        p.wait()
    except KeyboardInterrupt:
        p.kill()
        p.wait()

    sys.stdout.write(o)

def parseConfig(configLines):
    """Parse the given list of strings as a configuration file
    One name=value pair per line, no sections and parsed in physical order
    
    >>> parseConfig([])
    {}
    >>> parseConfig(['a=1',])
    {'a': '1'}
    >>> parseConfig(['a=1','b=this is a test'])
    {'a': '1', 'b': 'this is a test'}
    """
    result = {}

    for line in configLines:
        line = line.strip()

        if len(line) > 0 and not line.startswith('#') and '=' in line:
            key, value  = line.split('=', 1)
            result[key] = value

    return result

def initConfig():
    """Locate and parse the configuration file
    """
    homeDir = os.path.expanduser('~')
    cfgFile = os.getenv('MOZPASS_CONFIG', os.path.join(homeDir, '.mozpass.cfg'))

    if os.path.exists(cfgFile):
        lines = open(cfgFile, 'r').readlines()
    else:
        lines = []

    return parseConfig(lines)

def processCommand(argList, cfg):
    """Given the command line (argList) and the parsed configuration dictionary
    (cfg), process the parameters for any template replacements and return
    a subprocess ready command list.
    
    >>> processCommand(['echo', 'param1'], {})
    param1
    <BLANKLINE>
    
    >>> processCommand(['echo', 'test $param'], {'param': 'a'})
    test a
    <BLANKLINE>
    
    >>> processCommand(['echo', '$param1', '"$param2 $param3"', '4'], {'param1': '1', 'param2': '2', 'param3': '3'})
    1 "2 3" 4
    <BLANKLINE>
    """
    cmd = []

    if len(args) > 0:
        for item in argList:
            cmd.append(Template(item).safe_substitute(cfg))

    doCommand(cmd)


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog -i [options]\n       %prog [options] apk_file")
    parser.add_option("-i",
                      action="store_true",
                      dest="interactive",
                      default=False,
                      help="Interactive mode"
                     )
    parser.add_option("--keystore",
                      action="store",
                      dest="keystore",
                      help="Specify the keystore in interactive mode"
                     )
    parser.add_option("--alias",
                      action="store",
                      dest="alias",
                      help="Specify the key alias in interactive mode"
                     )
    parser.add_option("--apk",
                      action="store",
                      dest="apk",
                      help="Specify the apk in interactive mode"
                     )
    parser.add_option("--test-only",
                      action="store_true",
                      dest="test_only",
                      help="Only test, don't sign (noop)"
                     )
    (options, args) = parser.parse_args()

# Uncomment to test
#    if options.test_only:
#        command = ['echo', 'jarsigner']
#    else:
#        command = ['jarsigner']
    command = ['jarsigner']

    if not options.interactive:
        cfg  = initConfig()

        # hack time - right now it's assumed that the call will look like:
        # mozpass.py <apk name>
        # and we will build the parameters
        args = command + ['-keystore', '$android_keystore',
                          '-storepass', '$android_storepass',
                          '-keypass', '$android_keypass',
                          args[0], '$android_alias']

        processCommand(args, cfg)
    else:
        if not options.keystore or not options.alias or not options.apk:
            print("Interactive mode requires --keystore, --alias, and --apk!")
            sys.exit(-1)

        storepass = getpass("Store passphrase: ")
        keypass = getpass("Key passphrase: ")

        doCommand(command + ['-keystore', options.keystore,
                             '-storepass', storepass,
                             '-keypass', keypass,
                             options.apk, options.alias])
