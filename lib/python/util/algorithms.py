import sys
import struct
from copy import copy


class ChunkingError(Exception):
    pass


def getChunk(things, chunks, thisChunk):
    if thisChunk > chunks:
        raise ChunkingError("thisChunk (%d) is greater than total"
                            "chunks (%d)" % (thisChunk, chunks)
                            )
    possibleThings = copy(things)
    nThings = len(possibleThings)
    for c in range(1, chunks + 1):
        n = nThings / chunks
        # If our things aren't evenly divisible by the number of chunks
        # we need to append one more onto some of them
        if c <= (nThings % chunks):
            n += 1
        if c == thisChunk:
            return possibleThings[0:n]
        del possibleThings[0:n]


## console width code courtesy of Alex Martelli
# http://stackoverflow.com/questions/1396820/
# With modifications to conform to pep8 and some style nits.
def find_console_width():
    if sys.platform.startswith('win'):
        return _find_windows_console_width()
    else:
        return _find_unix_console_width()


def _find_unix_console_width():
    """Return the width of the Unix terminal

    If `stdout` is not a real terminal, return the default value (80)
    """
    import termios
    import fcntl

    # fcntl.ioctl will fail if stdout is not a tty
    if not sys.stdout.isatty():
        return 80

    s = struct.pack("HHHH", 0, 0, 0, 0)
    fd_stdout = sys.stdout.fileno()
    size = fcntl.ioctl(fd_stdout, termios.TIOCGWINSZ, s)
    height, width = struct.unpack("HHHH", size)[:2]
    return width


def _find_windows_console_width():
    """Return the width of the Windows console

    If the width cannot be determined, return the default value (80)
    """
    # http://code.activestate.com/recipes/440694/
    from ctypes import windll, create_string_buffer
    STDIN, STDOUT, STDERR = -10, -11, -12

    h = windll.kernel32.GetStdHandle(STDERR)
    csbi = create_string_buffer(22)
    res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)

    if res:
        (bufx, bufy, curx, cury, wattr,
         left, top, right, bottom,
         maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
        sizex = right - left + 1
        sizey = bottom - top + 1
    else:
        sizex, sizey = 80, 25
    return sizex
