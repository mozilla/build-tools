#!/usr/bin/env python

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
    if len(sys.argv) == 1:
        import doctest
        doctest.testmod(verbose=True)
    else:
        cfg  = initConfig()
        args = sys.argv[1:]

        # hack time - right now it's assumed that the call will look like:
        # mozpass.py <apk name>
        # and we will build the parameters
        args = ['jarsigner', '-keystore', '$android-keystore',
                             '-storepass', '$android-storepass',
                             '-keypass', '$android-keypass',
                             args[0], '$android-alias']

        processCommand(args, cfg)

