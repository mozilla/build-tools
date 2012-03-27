try:
    import simplejson as json
except ImportError:
    import json

from release.platforms import buildbot2updatePlatforms
from balrog.client.api import API


def get_nightly_blob_name(appName, branch, build_type, suffix, dummy=False):
    if dummy:
        branch = '%s-dummy' % branch
    return '%s-%s-%s-%s' % (appName, branch, build_type, suffix)


class NightlyRunner(object):

    build_type = 'nightly'
    appName = None
    branch = None
    build_target = None
    appVersion = None
    name = None
    locale = None

    def __init__(self, buildprops_file, api_root, auth, dummy=False):
        self.buildbprops_file = buildprops_file
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def generate_blob(self):
        fp = open(self.buildbprops_file)
        bp = json.load(fp)
        fp.close()

        props = bp['properties']
        self.build_target = buildbot2updatePlatforms(props['platform'])[0]
        buildID = props['buildid']

        self.appName = props['appName']
        self.branch = props['branch']
        self.appVersion = props['appVersion']
        self.name = get_nightly_blob_name(self.appName, self.branch,
                                          self.build_type, buildID, self.dummy)
        self.locale = props.get('locale', 'en-US')
        blob = {
            'appv': self.appVersion,
            'extv': props.get('extVersion', self.appVersion),
            'buildID': props['buildid'],
        }
        blob['complete'] = {
            'from': '*',
            'filesize': props['completeMarSize'],
            'hashValue': props['completeMarHash'],
            'fileUrl': props['completeMarUrl']
        }
        if props.get('partialMarFilename'):
            blob['partial'] = {
                'from': get_nightly_blob_name(self.appName, self.branch,
                                              self.build_type,
                                              props['previous_buildid'],
                                              self.dummy),
                'filesize': props['partialMarSize'],
                'hashValue': props['partialMarHash'],
                'fileUrl': props['partialMarUrl']
            }
        return blob

    def run(self):
        blob = self.generate_blob()
        blob = json.dumps(blob)
        api = API(auth=self.auth, api_root=self.api_root)
        copy_to = [get_nightly_blob_name(
            self.appName, self.branch, self.build_type, 'latest', self.dummy)]
        copy_to = repr(copy_to)
        api.update_build(name=self.name, product=self.appName,
                         build_target=self.build_target,
                         version=self.appVersion, locale=self.locale,
                         details=blob, copy_to=copy_to)
