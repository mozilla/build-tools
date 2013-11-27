try:
    import simplejson as json
except ImportError:
    import json

from release.platforms import buildbot2updatePlatforms
from balrog.submitter.api import SingleLocale


def get_nightly_blob_name(appName, branch, build_type, suffix, dummy=False):
    if dummy:
        branch = '%s-dummy' % branch
    return '%s-%s-%s-%s' % (appName, branch, build_type, suffix)


def get_release_blob_name(appName, version, build_number, dummy=False):
    name = '%s-%s-build%s' % (appName, version, build_number)
    if dummy:
        name += '-dummy'
    return name


class NightlySubmitter(object):

    build_type = 'nightly'

    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def run(self, platform, buildID, appName, branch, appVersion, locale,
            hashFunction, extVersion, completeMarSize, completeMarHash,
            completeMarUrl, partialMarSize, partialMarHash=None,
            partialMarUrl=None, previous_buildid=None):
        targets = buildbot2updatePlatforms(platform)
        build_target = targets[0]
        alias = None
        if len(targets) > 1:
            alias = targets[1:]

        name = get_nightly_blob_name(appName, branch, self.build_type, buildID, self.dummy)
        data = {
            'appv': appVersion,
            'extv': extVersion,
            'buildID': buildID,
        }
        data['complete'] = {
            'from': '*',
            'filesize': completeMarSize,
            'hashValue': completeMarHash,
            'fileUrl': completeMarUrl
        }
        if partialMarSize:
            data['partial'] = {
                'from': get_nightly_blob_name(appName, branch,
                                              self.build_type,
                                              previous_buildid,
                                              self.dummy),
                'filesize': partialMarSize,
                'hashValue': partialMarHash,
                'fileUrl': partialMarUrl
            }

        data = json.dumps(data)
        api = SingleLocale(auth=self.auth, api_root=self.api_root)
        copyTo = [get_nightly_blob_name(
            appName, branch, self.build_type, 'latest', self.dummy)]
        copyTo = json.dumps(copyTo)
        alias = json.dumps(alias)
        api.update_build(name=name, product=appName,
                         build_target=build_target,
                         version=appVersion, locale=locale,
                         hashFunction=hashFunction,
                         buildData=data, copyTo=copyTo, alias=alias)


class ReleaseSubmitter(object):
    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def run(self, platform, appName, appVersion, version, build_number, locale,
            hashFunction, extVersion, buildID, completeMarSize, completeMarHash):
        targets = buildbot2updatePlatforms(platform)
        # Some platforms may have alias', but those are set-up elsewhere
        # for release blobs.
        build_target = targets[0]

        appName = appName
        appVersion = appVersion
        version = version
        build_number = build_number
        name = get_release_blob_name(appName, version, build_number,
                                     self.dummy)
        data = {
            'appv': appVersion,
            'extv': extVersion,
            'buildID': buildID,
        }
        data['complete'] = {
            'from': '*',
            'filesize': completeMarSize,
            'hashValue': completeMarHash,
        }

        data = json.dumps(data)
        api = SingleLocale(auth=self.auth, api_root=self.api_root)
        api.update_build(name=name, product=appName,
                         build_target=build_target, version=appVersion,
                         locale=locale, hashFunction=hashFunction,
                         buildData=data)
