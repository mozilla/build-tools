"""Functions for running commands"""
import subprocess, os

import logging
log = logging.getLogger(__name__)

def run_cmd(cmd, **kwargs):
    """Run cmd (a list of arguments).  Raise subprocess.CalledProcessError if
    the command exits with non-zero.  If the command returns successfully,
    return 0."""
    if 'cwd' in kwargs and kwargs['cwd']:
        log.info("%s in %s", " ".join(cmd), kwargs['cwd'])
    else:
        log.info(" ".join(cmd))
    return subprocess.check_call(cmd, **kwargs)

def get_output(cmd, include_stderr=False, **kwargs):
    """Run cmd (a list of arguments) and return the output.  If include_stderr
    is set, stderr will be included in the output, otherwise it will be sent to
    the caller's stderr stream.

    Warning that you shouldn't use this function to capture a large amount of
    output (> a few thousand bytes), it will deadlock."""
    if include_stderr:
        stderr = subprocess.STDOUT
    else:
        stderr = None

    if 'cwd' in kwargs and kwargs['cwd']:
        log.info("%s in %s", " ".join(cmd), kwargs['cwd'])
    else:
        log.info(" ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr,
            **kwargs)
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    output = proc.stdout.read()
    return output

def remove_path(path):
    """This is a replacement for shutil.rmtree that works better under
    windows. Thanks to Bear at the OSAF for the code.
    (Borrowed from buildbot.slave.commands)"""
    log.debug("Removing %s", path)
    if not os.path.exists(path):
        # This handles broken links
        if os.path.islink(path):
            os.remove(path)
        return

    if os.path.islink(path):
        os.remove(path)
        return

    # Verify the directory is read/write/execute for the current user
    os.chmod(path, 0700)

    for name in os.listdir(path):
        full_name = os.path.join(path, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                # I think this is now redundant, but I don't have an NT
                # machine to test on, so I'm going to leave it in place
                # -warner
                os.chmod(full_name, 0600)

        if os.path.isdir(full_name):
            remove_path(full_name)
        else:
            # Don't try to chmod links
            if not os.path.islink(full_name):
                os.chmod(full_name, 0700)
            os.remove(full_name)
    os.rmdir(path)
