from pwd import getpwnam
import urllib2
import json
import re
import os

# 0) constants and helping functions
basedir = "/builds"
slavealloc_host = "http://slavealloc.build.mozilla.org/gettac"
toolsdir = "/builds/tools"
path_to_bmm_host = "/builds/bmm.hostname.txt"
# cltbld's uid and gid
const_uid=getpwnam('cltbld')[2]
const_gid=getpwnam('cltbld')[3]

def download_file(url, save_as, uid=const_uid, gid=const_gid):
    response = urllib2.urlopen(url)
    local_file = open(save_as, 'wb')
    local_file.write(response.read())
    local_file.close()
    os.chown(save_as, uid, gid)

# 1) load the configuration
f = open('devices.json', 'r')
j = json.load(f)
foopies = {}
for device in j:
    foopy = j[device]["foopy"]
    if foopy != "None":
        if foopies.has_key(foopy):
            foopies[foopy].append(device)
        else:
            foopies[foopy] = [device]

# 2) take note of our imaging server
hostname=os.environ['HOSTNAME']
match=re.search("(foopy[0-9]*)\..*",hostname)
foopy_name=match.group(1)
match=re.search(".*.p([0-9]*)\..*", hostname)
vlan=int(match.group(1))
if not os.path.exists(path_to_bmm_host):
    local_file = open(path_to_bmm_host, 'wb')
    local_file.write("mobile-imaging-%03i.p%i.releng.scl1.mozilla.com" % (vlan, vlan))
    local_file.close()

# 3) setup every directory for every device
list_devices = foopies[foopy_name]

for device in sorted(list_devices):
    # create the directory for the device
    device_dir = "%s/%s" % (basedir, device)
    if not os.path.exists(device_dir):
        os.makedirs(device_dir)
        os.chown(device_dir, const_uid, const_gid)
    # download buildbot.tac if not existant
    buildbot_tac_path = os.path.join(device_dir, 'buildbot.bat')
    if not os.path.isfile(buildbot_tac_path):
        download_file('%s/%s' % (slavealloc_host, device), buildbot_tac_path)
    # download manage_buildslave_path if not existant
    manage_buildslave_path = os.path.join(device_dir, 'manage_buildslave.sh')
    if not os.path.isfile(manage_buildslave_path):
        os.symlink(os.path.join(toolsdir, "buildfarm/mobile/manage_buildslave.sh"), manage_buildslave_path)
        os.lchown(manage_buildslave_path, const_uid, const_gid)
