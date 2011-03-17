#!/usr/bin/env python
"""%prog [options] -x|-t|-c marfile [files]

Utility for managing mar files"""
import struct, os, bz2

class MarInfo:
    """Represents information about a member of a MAR file. The following
    attributes are supported:
        `size`:     the file's size
        `name`:     the file's name
        `flags`:    file permission flags
        `_offset`:  where in the MAR file this member exists
    """
    size = None
    name = None
    flags = None
    _offset = None

    # The member info is serialized as a sequence of 4-byte integers
    # representing the offset, size, and flags of the file followed by a null
    # terminated string representing the filename
    _member_fmt = ">LLL"

    @classmethod
    def from_fileobj(cls, fp):
        """Return a MarInfo object by reading open file object `fp`"""
        self = cls()
        data = fp.read(12)
        if not data:
            # EOF
            return None
        if len(data) != 12:
            raise ValueError("Malformed mar?")
        self._offset, self.size, self.flags = struct.unpack(cls._member_fmt, data)
        name = ""
        while True:
            c = fp.read(1)
            if c is None:
                raise ValueError("Malformed mar?")
            if c == "\x00":
                break
            name += c
        self.name = name
        return self

    def __repr__(self):
        return "<%s %o %s bytes starting at %i>" % (
                self.name, self.flags, self.size, self._offset)

    def to_bytes(self):
        return struct.pack(self._member_fmt, self._offset, self.size, self.flags) + \
                self.name + "\x00"

class MarFile:
    """Represents a MAR file on disk.

    `name`:     filename of MAR file
    `mode`:     either 'r' or 'w', depending on if you're reading or writing.
                defaults to 'r'
    """

    _longint_fmt = ">L"
    def __init__(self, name, mode="r"):
        if mode not in "rw":
            raise ValueError("Mode must be either 'r' or 'w'")

        self.name = name
        self.mode = mode
        self.fileobj = open(name, mode + 'b')

        self.members = []

        # Current offset of our index in the file. This gets updated as we add
        # files to the MAR. This also refers to the end of the file until we've
        # actually written the index
        self.index_offset = 8

        # Flag to indicate that we need to re-write the index
        self.rewrite_index = False

        if mode == "r":
            # Read the file's index
            self._read_index()
        elif mode == "w":
            # Write the magic and placeholder for the index
            self.fileobj.write("MAR1" + struct.pack(self._longint_fmt, self.index_offset))

    def _read_index(self):
        fp = self.fileobj
        fp.seek(0)
        # Read the header
        header = fp.read(8)
        magic, self.index_offset = struct.unpack(">4sL", header)
        if magic != "MAR1":
            raise ValueError("Bad magic")
        fp.seek(self.index_offset)

        # Read the index_size, we don't use it though
        # We just read all the info sections from here to the end of the file
        struct.unpack(self._longint_fmt, fp.read(4))[0]

        self.members = []

        while True:
            info = MarInfo.from_fileobj(fp)
            if not info:
                break
            self.members.append(info)

        # Sort them by where they are in the file
        self.members.sort(key=lambda info:info._offset)

    def add(self, path, name=None, fileobj=None, flags=None):
        """Adds `path` to this MAR file.

        If `name` is set, the file is named with `name` in the MAR, otherwise
        use the normalized version of `path`.

        If `fileobj` is set, file data is read from it, otherwise the file
        located at `path` will be opened and read.

        If `flags` is set, it will be used as the permission flags in the MAR,
        otherwise the permissions of `path` will be used.
        """
        if self.mode != "w":
            raise ValueError("File not opened for writing")

        # If path refers to a directory, add all the files inside of it
        if os.path.isdir(path):
            self.add_dir(path)
            return

        info = MarInfo()
        if not fileobj:
            info.name = name or os.path.normpath(path)
            info.size = os.path.getsize(path)
            info.flags = flags or os.stat(path).st_mode & 0777
            info._offset = self.index_offset

            f = open(path, 'rb')
            self.fileobj.seek(self.index_offset)
            while True:
                block = f.read(512*1024)
                if not block:
                    break
                self.fileobj.write(block)
        else:
            assert flags
            info.name = name or path
            info.size = 0
            info.flags = flags
            info._offset = self.index_offset
            self.fileobj.seek(self.index_offset)
            while True:
                block = fileobj.read(512*1024)
                if not block:
                    break
                info.size += len(block)
                self.fileobj.write(block)

        # Shift our index, and mark that we have to re-write it on close
        self.index_offset += info.size
        self.rewrite_index = True
        self.members.append(info)

    def add_dir(self, path):
        """Add all of the files under `path` to the MAR file"""
        for root, dirs, files in os.walk(path):
            for f in files:
                self.add(os.path.join(root, f))

    def close(self):
        """Close the MAR file, writing out the new index if required.

        Furthur modifications to the file are not allowed."""
        if self.mode == "w" and self.rewrite_index:
            self._write_index()
        self.fileobj.close()
        self.fileobj = None

    def __del__(self):
        """Close the file when we're garbage collected"""
        if self.fileobj:
            self.close()

    def _write_index(self):
        """Writes the index of all members at the end of the file"""
        self.fileobj.seek(self.index_offset+4)
        index_size = 0
        for m in self.members:
            member_bytes = m.to_bytes()
            index_size += len(member_bytes)
            self.fileobj.write(member_bytes)
        self.fileobj.seek(self.index_offset)
        self.fileobj.write(struct.pack(self._longint_fmt, index_size))

        # Update the offset to the index
        self.fileobj.seek(4)
        self.fileobj.write(struct.pack(self._longint_fmt, self.index_offset))

    def extractall(self, path=".", members=None):
        """Extracts members into `path`. If members is None (the default), then
        all members are extracted."""
        if members is None:
            members = self.members
        for m in members:
            self.extract(m, path)

    def extract(self, member, path="."):
        """Extract `member` into `path` which defaults to the current
        directory."""
        dstpath = os.path.join(path, member.name)
        dirname = os.path.dirname(dstpath)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.fileobj.seek(member._offset)
        open(dstpath, "wb").write(self.fileobj.read(member.size))
        os.chmod(dstpath, member.flags)

class BZ2MarFile(MarFile):
    """Subclass of MarFile that compresses/decompresses members using BZ2.

    BZ2 compression is used for most update MARs."""
    def extract(self, member, path="."):
        """Extract and decompress `member` into `path` which defaults to the
        current directory."""
        dstpath = os.path.join(path, member.name)
        dirname = os.path.dirname(dstpath)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.fileobj.seek(member._offset)
        decomp = bz2.BZ2Decompressor()
        output = open(dstpath, "wb")
        toread = member.size
        while True:
            thisblock = min(128*1024, toread)
            block = self.fileobj.read(thisblock)
            if not block:
                break
            toread -= len(block)
            output.write(decomp.decompress(block))
        output.close()
        os.chmod(dstpath, member.flags)

    def add(self, path, name=None, fileobj=None, mode=None):
        """Adds `path` compressed with BZ2 to this MAR file.

        If `name` is set, the file is named with `name` in the MAR, otherwise
        use the normalized version of `path`.

        If `fileobj` is set, file data is read from it, otherwise the file
        located at `path` will be opened and read.

        If `flags` is set, it will be used as the permission flags in the MAR,
        otherwise the permissions of `path` will be used.
        """
        if self.mode != "w":
            raise ValueError("File not opened for writing")
        if os.path.isdir(path):
            self.add_dir(path)
            return
        info = MarInfo()
        info.name = name or os.path.normpath(path)
        info.size = 0
        if not fileobj:
            info.flags = os.stat(path).st_mode & 0777
        else:
            info.flags = mode
        info._offset = self.index_offset

        if not fileobj:
            f = open(path, 'rb')
        else:
            f = fileobj
        comp = bz2.BZ2Compressor(9)
        self.fileobj.seek(self.index_offset)
        while True:
            block = f.read(512*1024)
            if not block:
                break
            block = comp.compress(block)
            info.size += len(block)
            self.fileobj.write(block)
        block = comp.flush()
        info.size += len(block)
        self.fileobj.write(block)

        self.index_offset += info.size
        self.rewrite_index = True
        self.members.append(info)

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(__doc__)
    parser.set_defaults(
        action=None,
        bz2=False,
        chdir=None,
        )
    parser.add_option("-x", "--extract", action="store_const", const="extract",
            dest="action", help="extract MAR")
    parser.add_option("-t", "--list", action="store_const", const="list",
            dest="action", help="print out MAR contents")
    parser.add_option("-c", "--create", action="store_const", const="create",
            dest="action", help="create MAR")
    parser.add_option("-j", "--bzip2", action="store_true", dest="bz2",
            help="compress/decompress members with BZ2")
    parser.add_option("-C", "--chdir", dest="chdir",
            help="chdir to this directory before creating or extracing; location of marfile isn't affected by this option.")

    options, args = parser.parse_args()

    if not options.action:
        parser.error("Must specify something to do (one of -x, -t, -c)")

    if not args:
        parser.error("You must specify at least a marfile to work with")

    marfile, files = args[0], args[1:]
    marfile = os.path.abspath(marfile)

    if options.bz2:
        mar_class = BZ2MarFile
    else:
        mar_class = MarFile

    # Move into the directory requested
    if options.chdir:
        os.chdir(options.chdir)

    if options.action == "extract":
        m = mar_class(marfile)
        m.extractall()

    elif options.action == "list":
        m = mar_class(marfile)
        print "%-7s %-7s %-7s" % ("SIZE", "MODE", "NAME")
        for m in m.members:
            print "%-7i %04o    %s" % (m.size, m.flags, m.name)

    elif options.action == "create":
        if not files:
            parser.error("Must specify at least one file to add to marfile")
        m = mar_class(marfile, "w")
        for f in files:
            m.add(f)
        m.close()
