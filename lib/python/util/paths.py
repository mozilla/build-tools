import os.path
import sys

def windows2msys(path):
    """Translate a Windows pathname to an MSYS pathname.
    Necessary because we call out to ssh/scp, which are MSYS binaries
    and expect MSYS paths."""
    if not sys.platform.startswith('win32'):
        return path
    (drive, path) = os.path.splitdrive(os.path.abspath(path))     
    return "/" + drive[0] + path.replace('\\','/')

