#!/usr/bin/env python
import subprocess
import os
import sys
import re
import time
import select
import signal
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class FlasherFailedException(Exception):
    pass

class Throbber:

    def __init__(self, length=50, throbber=None):
        self.length=50
        if throbber is None:
            self.throbber = []
            for i in range(0,self.length + 1):
                line = '=' * i
                line += '0'
                line += '-' * (self.length - i)
                if i != self.length:
                    self.throbber.insert(0, line)
                if i != 0:
                    self.throbber.insert(len(self.throbber), line)
        else:
            self.throbber = throbber

    def run(self):
        i = 0
        self.pid = os.fork()
        if self.pid == 0:
            while True:
                sys.stdout.write(self.throbber[i])
                i += 1
                if i >= len(self.throbber):
                    i = 0
                time.sleep(0.1)
                sys.stdout.flush()
                sys.stdout.write('\b'*len(self.throbber[i - 1]))

    def kill(self):
        if self.pid:
            os.kill(self.pid, signal.SIGTERM)


class Flasher:

    error_codes = {
        0: 'Something is wrong with %s.Flasher THIS SHOULD NOT BE A FAILURE' % __name__,
        1: 'This operation is not supported in the current device mode',
        2: 'No operation was specified',
        3: 'Error opening USB Device, try again',
        126: 'Trying to run flasher on the wrong architecture',
    }

    rd_flags = ['no-omap-wd',
                'no-ext-wd',
                'no-lifeguard-reset',
                'serial-console',
                'no-usb-timeout',
                'sti-console',
                'no-charging',
                'force-power-key']

    waiting_pattern='Suitable USB device not found, waiting.'
    underway_pattern='Sending and flashing'

    def __init__(self, flasher_bin='flasher-3.5', debug=False):
        self.flasher_bin = flasher_bin
        self.debug = debug

    def execute(self, args, regex=[]):
        if self.debug:
            print 'Executing: ', [self.flasher_bin] + args
        p = subprocess.Popen([self.flasher_bin] + args,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout=p.stdout
        stderr=p.stderr
        re_dict={}
        command_output = StringIO.StringIO()
        if not self.debug:
            throbber = Throbber(20)
            throbber.run()
        while p.poll() == None:
            r,w,x = select.select([stdout,stderr],[],[],0.5)
            for f in r:
                data = f.readline()
                if data == '':
                    continue
                if self.debug:
                    if f is stdout:
                        stream='stdout'
                    elif f is stderr:
                        stream='stderr'
                    else:
                        stream='???'
                    print 'DEBUG(%s): "%s"' % (stream, data[:-1].replace('\b', ''))
                command_output.write('%s: %s' % ('STDOUT' if f is stdout else 'STDERR',
                                                 data))
            for r in regex:
                m=r.search(data)
                if m:
                    re_dict.update(m.groupdict())

            if stdout.closed or stderr.closed:
                raise FlasherFailedException('Broken pipe to flasher program')
        if not self.debug:
            throbber.kill()
            print ''
        rc = p.poll()
        if self.debug:
            print 'DEBUG: RC=%s' % str(rc)
        if rc != 0 and not self.debug:
            command_output.seek(0)
            while True:
                data = command_output.readline()
                if data == '':
                    break
                else:
                    print 'DEBUG: %s' % data[:-1]
        command_output.close()
        if rc!= 0:
            if Flasher.error_codes.has_key(rc):
                raise FlasherFailedException(Flasher.error_codes[rc])
            else:
                raise FlasherFailedException('%s failed for an unknown reason (rc:%s)' % (self.flasher_bin,str(rc)))
        return re_dict


    def fiasco_flash(self, fiasco_file, cold_flash=False, h_rev=None, serial='usb'):
        assert os.path.exists(fiasco_file), 'missing fiasco file %s' % fiasco_file
        args=['-F', fiasco_file, '-f']
        if cold_flash:
            assert serial and h_rev, 'coldflashing requires a hardware revision and serial device'
            args += ['-c', '-h', h_rev, '-S', serial]
        print 'Flashing: "%s"' % fiasco_file
        self.execute(args)

    def query_h_rev(self):
        args = ['-i']
        regex = re.compile('Found device (?P<model>.*?), hardware revision (?P<rev>[0-9]{4})')
        info=self.execute(args, regex=[regex])
        if info is None:
            return None
        if '0000' == info.get('rev'):
            raise ValueError('The device attached does not have a valid hardware revision')
        return info


    def rootfs_flash(self, rootfs_file):
        assert os.path.exists(rootfs_file), 'missing rootfs file'
        args=['--rootfs', rootfs_file, '-f']
        print 'Flashing: "%s"' % rootfs_file
        self.execute(args)

    def set_rd(self):
        args=['--enable-rd-mode']
        self.execute(args)

    def set_rd_flags(self, flags=[]):
        if len(flags) == 0:
            flags=self.rd_flags
        self.execute(['--set-rd-flags=%s' % ','.join(flags)])

    def clear_rd_flags(self, flags=[]):
        if len(flags) == 0:
            flags=self.rd_flags
        self.execute(['--clear-rd-flags=%s' % ','.join(flags)])

    def reboot_device(self):
        self.execute(['--reboot'])
        time.sleep(5) # ensure no other flasher command puts device into firmware update mode

    def flasher_custom(self, args=[]):
        assert type(args) is list, 'arguments must be in a list'
        self.execute(args)

class USBBlocker:

    cmds={
        'Darwin': ['ioreg', '-c', 'IOUSBDevice'],
        'Linux': ['lsusb'],
    }

    patterns={
        'Darwin': [],
        'Linux': [],
    }

    timeout=1

    def __init__(self):
        self.platform=os.uname()[0]

    def substr_in_list(self, substr, list):
        for i in list:
            if substr in i:
                return True
        return False

    def substrs_in_list(self, substrs, data):
        for substr in substrs:
            if self.substr_in_list(substr, data):
                return True
        return False

    def block(self, mode='while'):
        if mode == 'while':
            while self._block_once():
                time.sleep(self.timeout)
                print '\b.',
        elif mode == 'until':
            while not self._block_once():
                time.sleep(self.timeout)
                print '\b.',
        print '\b.... Done!'

    def _block_once(self):
        p=subprocess.Popen(self.__class__.cmds[self.platform],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output=p.stdout.readlines()
        output.extend(p.stderr.readlines())
        p.wait()
        return self.substrs_in_list(self.__class__.patterns[self.platform],
                                    output)


class ReadyToFlashBlocker(USBBlocker):
    patterns={
        'Darwin': [
            'N900 (Update mode)',
        ],
        'Linux': [],
    }

    def block(self):
        USBBlocker.block(self, mode='until')

class UnplugDeviceBlocker(USBBlocker):
    patterns={
        'Darwin': [
            'N900 (Storage Mode)',
            'N900 (PC-Suite Mode)',
        ],
        'Linux': [],
    }



def flash_n900(main, emmc, rootfs=None, cold_flash=False, debug=False):
    try:
        rv=True
        f=Flasher(debug=debug)
        ready_to_flash=ReadyToFlashBlocker()
        unplug_device=UnplugDeviceBlocker()
        print 'Plug in n900 in firmware update mode'
        print '='*80
        print '  1) remove battery'
        print '  2) plug in MicroUSB cable'
        print '  3) press and hold "u" on N900 keyboard'
        print '  4) insert battery'
        print 'Waiting to remove N900s in the wrong mode',
        unplug_device.block()
        print 'Waiting for an N900 in the right mode',
        ready_to_flash.block()
        if cold_flash:
            h_rev = f.query_h_rev()
            assert not h_rev is None, 'Could not determine the hardware revision of device'
            assert len(h_rev) == 2, 'h_rev too short'
            assert re.match(r'\w{2}-\w{2}:\d{4}', revision), 'Hardware revision %s is invalid' % revision
            revision = ':'.join(h_rev)
            f.fiasco_flash(fiasco_file=main, cold_flash=True, h_rev=revision)
        else:
            f.fiasco_flash(fiasco_file=main)
        if rootfs:
            f.rootfs_flash(rootfs)
        f.fiasco_flash(fiasco_file=emmc)
        print 'Done! Unplug device'
        f.reboot_device
        unplug_device.block()
    except FlasherFailedException, ffe:
        print 'Flashing failed with the message: "%s"' % ffe.args[0]
        rv=False
    except KeyboardInterrupt:
        print '\n\nFlashing cancelled'
        exit(1)
    return rv


if __name__ == "__main__":
    print flash_n900(
        main='RX-51_2009SE_10.2010.19-1.002_PR_COMBINED_002_ARM.bin',
        emmc='RX-51_2009SE_10.2010.13-2.VANILLA_PR_EMMC_MR0_ARM.bin',
        rootfs='moz-n900-v1.6.ubi',
        debug=False,
    )
