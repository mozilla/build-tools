from distutils.version import StrictVersion

try:
    import simplejson as json
except ImportError:
    import json

from release.info import getProductDetails
from release.paths import makeCandidatesDir
from release.platforms import buildbot2updatePlatforms, buildbot2bouncer, \
  buildbot2ftp
from release.versions import getPrettyVersion
from balrog.submitter.api import Release, SingleLocale, Rule
from util.algorithms import recursive_update


def get_nightly_blob_name(productName, branch, build_type, suffix, dummy=False):
    if dummy:
        branch = '%s-dummy' % branch
    return '%s-%s-%s-%s' % (productName, branch, build_type, suffix)


def get_release_blob_name(productName, version, build_number, dummy=False):
    name = '%s-%s-build%s' % (productName, version, build_number)
    if dummy:
        name += '-dummy'
    return name


class ReleaseCreatorBase(object):
    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def generate_data(self, appVersion, productName, version, buildNumber,
                      partialUpdates, updateChannels, stagingServer,
                      bouncerServer, enUSPlatforms, schemaVersion):
        assert schemaVersion in (2, 3), 'Unhandled schema version %s' % schemaVersion
        self.name = get_release_blob_name(productName, version, buildNumber)
        data = {
            'name': self.name,
            'detailsUrl': getProductDetails(productName.lower(), appVersion),
            'platforms': {},
            'fileUrls': {},
            'ftpFilenames': {},
            'bouncerProducts': {},
        }
        data['appVersion'] = appVersion
        data['platformVersion'] = appVersion
        data['displayVersion'] = getPrettyVersion(version)


        for channel in updateChannels:
            if channel in ('betatest', 'esrtest'):
                dir_ = makeCandidatesDir(productName.lower(), version,
                                         buildNumber, server=stagingServer, protocol='http')
                data['fileUrls'][channel] = '%supdate/%%OS_FTP%%/%%LOCALE%%/%%FILENAME%%' % dir_
            else:
                url = 'http://%s/?product=%%PRODUCT%%&os=%%OS_BOUNCER%%&lang=%%LOCALE%%' % bouncerServer
                data['fileUrls'][channel] = url

        for platform in enUSPlatforms:
            updatePlatforms = buildbot2updatePlatforms(platform)
            bouncerPlatform = buildbot2bouncer(platform)
            ftpPlatform = buildbot2ftp(platform)
            data['platforms'][updatePlatforms[0]] = {
                'OS_BOUNCER': bouncerPlatform,
                'OS_FTP': ftpPlatform
            }
            for aliasedPlatform in updatePlatforms[1:]:
                data['platforms'][aliasedPlatform] = {
                    'alias': updatePlatforms[0]
                }

        return data

    def run(self, appVersion, productName, version, buildNumber,
            partialUpdates, updateChannels, stagingServer, bouncerServer,
            enUSPlatforms, hashFunction, schemaVersion):
        api = Release(auth=self.auth, api_root=self.api_root)
        data = self.generate_data(appVersion, productName, version,
                                  buildNumber, partialUpdates, updateChannels,
                                  stagingServer, bouncerServer, enUSPlatforms,
                                  schemaVersion)
        current_data, data_version = api.get_data(self.name)
        data = recursive_update(current_data, data)
        api = Release(auth=self.auth, api_root=self.api_root)
        api.update_release(name=self.name,
                           version=appVersion,
                           product=productName,
                           hashFunction=hashFunction,
                           releaseData=json.dumps(data),
                           data_version=data_version)


class V2ReleaseCreator(ReleaseCreatorBase):
    def run(self, *args, **kwargs):
        return ReleaseCreatorBase.run(self, *args, schemaVersion=2, **kwargs)

    def _get_update_data(self, productName, version, partialUpdates):
        data = {}
        previousVersion = str(max(StrictVersion(v) for v in partialUpdates))

        data['ftpFilenames']['complete'] = '%s-%s.complete.mar' % (productName.lower(), version)
        data['ftpFilenames']['partial'] = '%s-%s-%s.partial.mar' % (productName.lower(), previousVersion, version)
        data['bouncerProducts']['complete'] = '%s-%s-Complete' % (productName.capitalize(), version)
        data['bouncerProducts']['partial'] = '%s-%s-Partial-%s' % (productName.capitalize(), version, previousVersion)

        return data


class NightlySubmitterBase(object):
    build_type = 'nightly'

    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def run(self, platform, buildID, productName, branch, appVersion, locale,
            hashFunction, extVersion, schemaVersion, isOSUpdate=None, **updateKwargs):
        assert schemaVersion in (2, 3), 'Unhandled schema version %s' % schemaVersion
        targets = buildbot2updatePlatforms(platform)
        build_target = targets[0]
        alias = None
        if len(targets) > 1:
            alias = targets[1:]

        data = {
            'buildID': buildID,
        }
        data['appVersion'] = appVersion
        data['platformVersion'] = extVersion
        data['displayVersion'] = appVersion
        if isOSUpdate:
            data['isOSUpdate'] = isOSUpdate

        data.update(self._get_update_data(productName, branch, **updateKwargs))

        name = get_nightly_blob_name(productName, branch, self.build_type, buildID, self.dummy)
        data = json.dumps(data)
        api = SingleLocale(auth=self.auth, api_root=self.api_root)
        copyTo = [get_nightly_blob_name(
            productName, branch, self.build_type, 'latest', self.dummy)]
        copyTo = json.dumps(copyTo)
        alias = json.dumps(alias)
        api.update_build(name=name, product=productName,
                         build_target=build_target,
                         version=appVersion, locale=locale,
                         hashFunction=hashFunction,
                         buildData=data, copyTo=copyTo, alias=alias,
                         schemaVersion=schemaVersion)


class V2NightlySubmitter(NightlySubmitterBase):
    def run(self, *args, **kwargs):
        return NightlySubmitterBase.run(self, *args, schemaVersion=2, **kwargs)

    def _get_update_data(self, productName, branch, completeMarSize,
                         completeMarHash, completeMarUrl, partialMarSize=None,
                         partialMarHash=None, partialMarUrl=None,
                         previous_buildid=None):
        data = {}
        data['complete'] = {
            'from': '*',
            'filesize': completeMarSize,
            'hashValue': completeMarHash,
            'fileUrl': completeMarUrl
        }
        if partialMarSize:
            data['partial'] = {
                'from': get_nightly_blob_name(productName, branch,
                                              self.build_type,
                                              previous_buildid,
                                              self.dummy),
                'filesize': partialMarSize,
                'hashValue': partialMarHash,
                'fileUrl': partialMarUrl
            }

        return data


class ReleaseSubmitterBase(object):
    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def run(self, platform, productName, appVersion, version, build_number, locale,
            hashFunction, extVersion, buildID, schemaVersion, **updateKwargs):
        assert schemaVersion in (2, 3), 'Unhandled schema version %s' % schemaVersion
        targets = buildbot2updatePlatforms(platform)
        # Some platforms may have alias', but those are set-up elsewhere
        # for release blobs.
        build_target = targets[0]

        name = get_release_blob_name(productName, version, build_number,
                                     self.dummy)

        data = {
            'buildID': buildID,
        }
        data['appVersion'] = appVersion
        data['platformVersion'] = extVersion
        data['displayVersion'] = getPrettyVersion(version)

        data.update(self._get_update_data(**updateKwargs))

        data = json.dumps(data)
        api = SingleLocale(auth=self.auth, api_root=self.api_root)
        schemaVersion = json.dumps(schemaVersion)
        api.update_build(name=name, product=productName,
                         build_target=build_target, version=appVersion,
                         locale=locale, hashFunction=hashFunction,
                         buildData=data, schemaVersion=schemaVersion)


class V2ReleaseSubmitter(ReleaseSubmitterBase):
    def run(self, *args, **kwargs):
        return ReleaseSubmitterBase.run(self, *args, schemaVersion=2, **kwargs)

    def _get_update_data(self, completeMarSize, completeMarHash):
        data = {}

        data['complete'] = {
            'from': '*',
            'filesize': completeMarSize,
            'hashValue': completeMarHash,
        }
        # XXX: We never supported partials in schema 2 for releases.

        return data

class ReleasePusher(object):
    def __init__(self, api_root, auth, dummy=False):
        self.api_root = api_root
        self.auth = auth
        self.dummy = dummy

    def run(self, productName, version, build_number, rule_ids):
        name = get_release_blob_name(productName, version, build_number,
                                     self.dummy)
        api = Rule(auth=self.auth, api_root=self.api_root)
        for id_ in rule_ids:
            api.update_rule(id_, mapping=name)
