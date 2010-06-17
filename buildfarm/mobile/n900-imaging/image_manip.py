#!/bin/echo
import subprocess
import re
import os
import tempfile
import time
import select

def path_lookup(program):
    if os.path.exists(program):
        return program
    else:
        if os.environ.has_key('PATH'):
            path=os.environ['PATH'].split(':')
            for i in path:
                if os.path.exists(os.path.join(i, program)):
                    return os.path.join(i, program)
        else:
            return None
    return None

def runcmd(args, input=None, quiet_on_fail=False, **kwargs):
    p = subprocess.Popen(args, stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, **kwargs)
    output=[]
    while p.poll() is None:
        r,w,x = select.select([p.stdout,p.stderr],[],[],1)
        for f in r:
            output += f.readlines()
    rc=p.wait()
    if rc != 0 and not quiet_on_fail:
        print 'Error(%d) while executing: %s' % (rc, args)
        print 'Last KB of output: %s' % output[-1024:]
    return (rc, output)

def cmd(args, **kwargs):
    return runcmd(args, **kwargs)[0]
    
def check_output(args, patterns=[], input=None, **kwargs):
    (rc, output)=runcmd(args, input, **kwargs)
    msgs = []
    assert type(patterns) is list, 'patterns must be a list'
    for pattern in patterns:
        for line in output:
            m=re.search(pattern, line)
            if m:
                msg = {'ungrouped': m.group()}
                msg.update(m.groupdict())
                msgs.append(msg)
    return (rc, msgs)

def rmmod_modules(modules=['ubifs', 'ubi', 'nandsim']):
    module_file=open('/proc/modules')
    data = module_file.readlines()
    active_modules = []
    for line in data:
        active_modules.append(line.split(' ')[0])
    for mod in ['ubifs', 'ubi', 'nandsim']:
        if mod in active_modules:
            rc = cmd(['rmmod', mod], quiet_on_fail=True)
            assert rc == 0, 'Could not remove %s from kernel' % mod

def umount_all_ubi():
    rc, msgs = mounted_devices=check_output(['mount'], 
            patterns=['^(?P<dev>.*?) on (?P<mountpoint>.*?) type (?P<type>.*?) '])
    assert rc == 0, 'Could not figure out which devices are mounted'
    for msg in msgs:
        if msg['type'] != 'ubifs':
            continue
        rc = cmd(['umount', msg['dev']])
        assert rc == 0, 'Could not umount device "%s"' % msg['dev']
    rmmod_modules()

def extract_fiasco(fiasco, flasher, wanted_file):
    tmpdir=tempfile.mkdtemp(prefix='imaging-tools.py')
    fiasco_dir=os.path.join(tmpdir, 'fiasco-contents')
    os.mkdir(fiasco_dir)
    print 'Extracting Fiasco Image'
    rc = cmd([os.path.abspath(flasher), '-F', os.path.abspath(fiasco), '--unpack'], cwd=fiasco_dir)
    assert rc == 0, 'Flasher (%s) failed to extract (%s) to (%s)' % (flasher, 
                                                os.path.abspath(fiasco),  fiasco_dir)
    return (tmpdir, os.path.abspath(os.path.join(fiasco_dir, wanted_file)))

def extract_ubifile(ubifile, output, mtd, rsync,tmpdir=None):
    if tmpdir is None:
        tmpdir=tempfile.mkdtemp(prefix='imaging-tools.py')
    mount_point=os.path.join(tmpdir, 'mount-point')
    os.mkdir(mount_point)
    umount_all_ubi()
    rc = cmd(['modprobe', 'nandsim', 'first_id_byte=0x20', 'second_id_byte=0xaa',
                       'third_id_byte=0x00', 'fourth_id_byte=0x15'])
    assert rc == 0, 'Could not probe the nandsim module'
    time.sleep(1) # make sure device node shows up if it is going to
    if not os.path.exists(mtd):
        rc = cmd(['mknod', mtd, 'c', '90', '0'])
        assert rc == 0, 'Could not create device node %s' % mtd
    print 'Copying UBI image to MTD device'
    rc = cmd(['dd', 'if=%s' % ubifile, 'of=%s' % mtd, 'bs=2048'])
    assert rc == 0, 'Could not write ubifile to mtd device'
    rc = cmd(['modprobe', 'ubi', 'mtd=%s' % mtd.replace('/dev/mtd', '')])
    assert rc == 0, 'Could not probe the ubi module'
    rc = cmd(['mount', '-t', 'ubifs',
              '/dev/ubi%s_0' % mtd.replace('/dev/mtd', ''), mount_point])
    assert rc == 0, 'Could not mount filesystem'
    print 'Copying data from mounted UBI image to harddisk'
    os.makedirs(output)
    rc = cmd([rsync, '-av', '%s/.' % os.path.abspath(mount_point), 
              '%s/.' % os.path.abspath(output)])
    assert rc == 0, 'Could not RSYNC filesystem off the nandsim'
    rc = cmd(['umount', mount_point])
    assert rc == 0, 'Could not umount the filesystem we are working with'
    umount_all_ubi()
    
def generate_ubifile(rootdir, output, rsync, mkfs, ubinize):
    print 'Creating %s.ubifs' % output
    rc=cmd([mkfs, '-m', '2048', '-e', '129024', '-c', '2047', '-r', rootdir,
            '%s.ubifs' % output])
    assert rc == 0, 'Could not generate UBIFS image'
    assert os.name == 'posix', 'This script must be run on unix'
    tmpfile = tempfile.NamedTemporaryFile()
    print >>tmpfile, '[rootfs]'
    print >>tmpfile, 'mode=ubi'
    print >>tmpfile, 'image=%s.ubifs' % output
    print >>tmpfile, 'vol_id=0'
    print >>tmpfile, 'vol_size=200MiB'
    print >>tmpfile, 'vol_type=dynamic'
    print >>tmpfile, 'vol_name=rootfs'
    print >>tmpfile, 'vol_flags=autoresize'
    print >>tmpfile, 'vol_alignment=1'
    print 'Creating %s.ubi' % output
    rc=cmd([ubinize, '-o', '%s.ubi' % output, '-p', '128KiB', '-m', '2048',
            '-s', '512', tmpfile.name])
    tmpfile.close()
    assert rc == 0, 'Could not create %s.ubi' % output

