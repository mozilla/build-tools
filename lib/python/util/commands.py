"""Functions for running commands"""
import subprocess, os
import time

import logging
log = logging.getLogger(__name__)

def log_cmd(cmd, **kwargs):
    # cwd is special in that we always want it printed, even if it's not
    # explicitly chosen
    if 'cwd' not in kwargs:
        kwargs['cwd'] = os.getcwd()
    def escape(s):
        s = s.encode('unicode_escape').encode('string_escape')
        if ' ' in s:
            # don't need to escape ', since string_escape already does that
            return "'%s'" % s
        else:
            return s
    log.info("command: START")
    log.info("command: %s", " ".join(escape(s) for s in cmd))
    for key,value in kwargs.iteritems():
        log.info("command: %s: %s", key, str(value))
    log.info("command: output:")

def merge_env(env):
    new_env = os.environ.copy()
    new_env.update(env)
    return new_env

def run_cmd(cmd, **kwargs):
    """Run cmd (a list of arguments).  Raise subprocess.CalledProcessError if
    the command exits with non-zero.  If the command returns successfully,
    return 0."""
    log_cmd(cmd, **kwargs)
    # We update this after logging because we don't want all of the inherited
    # env vars muddling up the output
    if 'env' in kwargs:
        kwargs['env'] = merge_env(kwargs['env'])
    try:
        t = time.time()
        return subprocess.check_call(cmd, **kwargs)
    finally:
        elapsed = time.time() - t
        log.info("command: END (%.2fs elapsed)\n", elapsed)

def run_remote_cmd(cmd, server, username=None, sshKey=None, ssh='ssh',
                   **kwargs):
    cmd_prefix = [ssh]
    if username:
        cmd_prefix.extend(['-l', username])
    if sshKey:
        cmd_prefix.extend(['-i', sshKey])
    cmd_prefix.append(server)
    if isinstance(cmd, basestring):
        cmd = [cmd]
    run_cmd(cmd_prefix + cmd, **kwargs)

def get_output(cmd, include_stderr=False, dont_log=False, **kwargs):
    """Run cmd (a list of arguments) and return the output.  If include_stderr
    is set, stderr will be included in the output, otherwise it will be sent to
    the caller's stderr stream.

    Warning that you shouldn't use this function to capture a large amount of
    output (> a few thousand bytes), it will deadlock."""
    if include_stderr:
        stderr = subprocess.STDOUT
    else:
        stderr = None

    log_cmd(cmd, **kwargs)
    if 'env' in kwargs:
        kwargs['env'] = merge_env(kwargs['env'])
    try:
        t = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr,
                **kwargs)
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        output = proc.stdout.read()
        if not dont_log:
            log.info(output)
        return output
    finally:
        elapsed = time.time() - t
        log.info("command: END (%.2f elapsed)\n", elapsed)

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
