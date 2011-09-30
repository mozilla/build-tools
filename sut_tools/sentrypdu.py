import telnetlib

class SentryPDU(object):
    """
    Class to interact with a Sentry CDU
    """

    def __init__(self, hostname, username='admn', password='admn', timeout=30, debuglevel=0):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.debuglevel = debuglevel
        self.conn = None

    def _login(self):
        # cache the connection
        if self.conn:
            return self.conn

        t = self.conn = telnetlib.Telnet()
        t.set_debuglevel(self.debuglevel)
        t.open(self.hostname, 23, self.timeout)
        t.read_until('sername:', self.timeout)
        t.write(self.username + '\n')
        t.read_until('ssword:', self.timeout)
        t.write(self.password + '\n')
        t.read_until('Switched CDU:', self.timeout)
        return t

    def _status(self, tegra=None):
        t = self._login()
        if tegra:
            t.write('status %s\n' % tegra)
        else:
            t.write('status\n')

        result = ''
        while 1:
            found, mo, text = t.expect([ 'More .Y/es N/o.:', 'Switched CDU:' ])
            result += text
            if found == 1:
                break
            elif found == -1:
                raise EOFError # uhoh..
            t.write('y\n')

        return result

    def status(self, tegra=None):
        """
        Get the status of all tegras attached to this PDU, or just one if that
        tegra is specified.  The return value is a dict of dicts, where the
        outer is keyed by the tegra name, and the inner dicts have keys id,
        name, status, and state.
        """
        status = {}
        status_text = self._status(tegra)
        if '-- name not found' in status_text.strip().lower():
            status_text = self._status()
        for line in status_text.split('\n'):
            line = line.strip()
            # all interesting lines seem to start with '.'
            if not line or line[0] != '.':
                continue
            line = line.split()
            if len(line) != 4:
                continue
            name = line[1]
            if not name.startswith('tegra-'):
                continue
            status[name] = dict(id=line[0], name=line[1],
                               status=line[2], state=line[3])
        return status

    def _op(self, op, tegra):
        t = self._login()
        t.write('%s %s\n' % (op, tegra))
        return 'Command successful' in t.read_until('Switched CDU:', self.timeout)

    def turn_on(self, tegra):
        """
        Turn the given tegra on.  Returns True if successful.
        """
        return self._op('on', tegra)

    def turn_off(self, tegra):
        """
        Turn the given tegra off.  Returns True if successful.
        """
        return self._op('off', tegra)

    def reboot(self, tegra):
        """
        Reboot the given tegra.  Returns True if successful.
        """
        id     = None
        status = self.status(tegra)
        if tegra in status:
            id = status[tegra]['id']
        return self._op('reboot', tegra)
