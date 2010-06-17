#!/usr/bin/env python

import ConfigParser
import optparse
import sys
import os
import hashlib

from flasher_wrapper import flash_n900

CONFIG_FILE = 'images.cfg'

class ImageFile:
    def __init__(self, name, filename, hash=None, hash_algo='sha1'):
        assert hash_algo.__class__ is str, 'specify hash algorithm as string'
        self.name = name
        self.filename = filename
        self.hash_algo = hash_algo
        if hash:
            self.hash = hash
        else:
            self.hash = hash_file(filename, algorithm=self.hash_algo)

    def exists(self):
        return self.filename and os.path.exists(self.filename)

    def valid(self):
        return self.exists() and validate_file(self.filename, good_hash=self.hash,
                                              algorithm=self.hash_algo)

    def status_str(self):
        if self.exists():
            if self.valid():
                return 'present and valid'
            else:
                return 'present and CORRUPTED'
        else:
            return 'ABSENT'

    def desc(self):
        return '%s %s\n' % (self.filename, self.status_str())

    def __str__(self):

        return 'Name: %s Status: %s Filename: %s Hash(%s): %s' % (self.name, self.status_str(),
                                                                  self.filename, self.hash_algo, self.hash)

class Image:
    def __init__(self, name, description=None, files=None, cfg_file=None):
        self.name = name
        self.description = description
        self.files = files
        self.cfg_file=cfg_file

    def update_cfg(self, config):
        section = self.name
        config.set(section, 'description', self.description)
        for file in self.files:
            name = file.name
            config.set(section, '%s-filename' % name, file.filename)
            config.set(section, '%s-hash' % name, file.hash)
            config.set(section, '%s-algo' % name, file.hash_algo)

    def store_cfg(self, config):
        if not config.has_section(self.name):
            config.add_section(self.name)
        self.update_cfg(config)

    def read_cfg(self, config, name):
        self.name=name
        self.files=[]
        items_list = config.items(name)
        items={}
        for item in config.items(name):
            k,v = item
            items[k]=v
        for i in items.keys():
            if i == 'description':
                self.description = items[i]
            elif i.endswith('-filename'):
                n=i[:-len('-filename')]
                f=items[i]
                a=items['%s-algo' % n]
                h=items['%s-hash' % n]
                file=ImageFile(n,f,h,a)
                self.files.append(file)


    def exists(self):
        if self.files:
            for file in self.files:
                if not file.exists():
                    return False
            return True
        else:
            return False

    def valid(self):
        if not self.exists():
            return False
        else:
            for file in self.files:
                if file is None or not file.valid():
                    return False
            return True

    def desc(self):
        d = '%s -- %s\n' % (self.name, self.description)
        if self.valid():
            d += 'This image is ready to flash\n'
        else:
            d += 'This image is NOT ready to flash\n'
        for f in self.files:
            d = '%s    -%s' % (d, f.desc())
        return d

    def __str__(self):
        return 'Name: %s Status: %s Description: %s ' % (self.name, 'valid' if self.valid() else 'INVALID',
                                                        self.description)

class MozillaImage(Image):

    def __init__(self, name, description=None, ubifile=None, mainfile=None, emmcfile=None):
        self.ubifile=ubifile
        self.mainfile=mainfile
        self.emmcfile=emmcfile
        self.files=[ubifile,mainfile,emmcfile]
        Image.__init__(self, name, description, self.files)

    def valid(self):
        if len(self.files) != 3:
            return False
        else:
            if self.ubifile and self.ubifile.name != 'ubi-file':
                return False
            if self.mainfile and self.mainfile.name != 'main-file':
                return False
            if self.emmcfile and self.emmcfile.name != 'emmc-file':
                return False
            return Image.valid(self)

    def read_cfg(self, config, name):
        Image.read_cfg(self, config, name)
        assert len(self.files) == 3
        for f in self.files:
            if 'ubi-file' in f.name:
                self.ubifile = f
            elif 'main-file' in f.name:
                self.mainfile = f
            elif 'emmc-file' in f.name:
                self.emmcfile = f


def hash_file(filename, chunk_size=2**10, algorithm='sha1'):
    if not filename:
        return None
    if not os.path.exists(filename):
        return None
    f = open(filename)
    if algorithm.__class__ is str:
        hash_obj = hashlib.new(algorithm)
    else:
        hash_obj = algorithm
    while True:
        data = f.read(chunk_size)
        if not data:
            break
        hash_obj.update(data)
    return hash_obj.hexdigest()

def validate_file(filename, good_hash, algorithm='sha1'):
    current_hash=hash_file(filename, algorithm=algorithm)
    if current_hash != good_hash:
        return False
    else:
        return True

def create_new_image(config):
    name = ask('What is the name of the image?')
    description = ask('What describes this image?')
    v=lambda x: type(x) is str and os.path.exists(x)
    ubi_filename = ask('What is the custom rootfs image filename', validation=v)
    ubifile=ImageFile('ubi-file', ubi_filename)
    main_filename = ask('What is the Main FIASCO image filename', validation=v)
    mainfile=ImageFile('main-file', main_filename)
    emmc_filename = ask('What is the EMMC FIASCO image filename', validation=v)
    emmcfile=ImageFile('emmc-file', emmc_filename)
    image=MozillaImage(name, description, ubifile=ubifile, mainfile=mainfile,
                       emmcfile=emmcfile)
    if image.valid():
        print 'This image is valid and will be saved to the config file'
        image.store_cfg(config)
        config_file=open(CONFIG_FILE, 'w+')
        config.write(config_file)
        config_file.close()
        return True
    else:
        if ask_yn('Would you like to try again?', default=True):
            return create_new_image(config)
        else:
            return False

def flash_image(config):
    responses=[]
    for img_name in config.sections():
        image = MozillaImage(img_name)
        image.read_cfg(config, img_name)
        responses.append(('%s -- %s' % (image.name, image.description), image))

    to_flash = choose('Which image would you like to flash?', responses)
    return flash_n900(main=to_flash.mainfile.filename, emmc=to_flash.emmcfile.filename, rootfs=to_flash.ubifile.filename)

def list_images(config):
    images=[]
    print 'Listing images -- may take a while'
    for img_name in config.sections():
        image = MozillaImage(img_name)
        image.read_cfg(config, img_name)
        images.append(image)
        print image.desc()
    return True

def choose(question, responses):
    answer=0
    answers = [x for x,y in responses]
    while answer < 1:
        print question
        print '='*80
        for i in range(0,len(answers)):
            print '%d) %s' % (i+1, answers[i])
        try:
            answer=int(raw_input('> '))
        except ValueError:
            pass
    return [y for x,y in responses][answer-1]

def ask(question, validation=lambda x: type(x) is str and x != ''):
    answer = None
    print question
    while not validation(answer):
        try:
            answer = raw_input('> ')
        except KeyboardInterrupt:
            answer = None
            break
        except EOFError:
            answer = None
            break
    return answer

def ask_yn(question, default=None):
    '''true == yes, false == no'''
    v = lambda x : x == 'y' or x == 'Y' or x == 'n' or x == 'N'
    v_none = lambda x: v(x) or x is ''
    if default is False:
        answer = ask(question + ' [y/N]', validation=v_none)
        if answer == '':
            answer = 'n'
    elif default is True:
        answer = ask(question + ' [Y/n]', validation=v_none)
        if answer == '':
            answer = 'y'
    else:
        answer = ask(question + ' [y/n]', validation=v)
    return answer



def main(config):
    print 'Welcome to the Mozilla N900 Flashing Program'
    operations=[('Flash an existing image', flash_image),
                ('Create a new image',create_new_image),
                ('List known images', list_images),
                ('Quit', None),
               ]
    while True:
        operation = choose('What would you like to do?', operations)
        if operation is None:
            exit()
        else:
            outcome = operation(config)
            print ''
            print 'The previous operation %s' % 'succeeded' if outcome else 'FAILED!'


if __name__ == "__main__":
    parser = optparse.OptionParser('usage: %prog [options]')
    parser.add_option('-v', '--debug', dest='debug',
                      help='UNIMPLEMENTED Run flasher in debug mode',
                      action='store_true', default=False)
    parser.add_option('-L', '--list-all', dest='list_all',
                      help='print a list of ALL images',
                      action='store_true', default=False)
    parser.add_option('-l', '--list', dest='list_valid',
                      help='print a list of all VALID images',
                      action='store_true', default=False)
    parser.add_option('-c', '--config', dest='config',
                      help='UNIMPLEMENTED specify a config file',
                      action='store', default=CONFIG_FILE)
    parser.add_option('-f', '--flash', dest='flash',
                      help='flash an image by name',
                      action='store')
    (options, args) = parser.parse_args()

    config = ConfigParser.SafeConfigParser()
    config.read(CONFIG_FILE)
    if options.list_all:
        print "These are all known images.  They may be invalid"
        for i in config.sections():
            print '  -"%s"' % i
        exit()
    if options.list_valid:
        list_images(config)
        exit()
    if options.flash:
        if options.flash not in config.sections():
            print 'Unknown image selected'
            exit()
        img = MozillaImage(name=options.flash)
        img.read_cfg(config, options.flash)
        flash_n900(main=img.mainfile.filename, emmc=img.emmcfile.filename)
        exit()

    try:
        main(config)
    except KeyboardInterrupt:
        print '\nYou have chosen to exit by pressing CTRL+C'
        exit
    except EOFError:
        print '\nYou have chosen to exit by entering the EOF character'
        exit
    except Exception:
        print '='*80
        print sys.exc_info()[0]
        print '='*80
    print 'Bye!'

