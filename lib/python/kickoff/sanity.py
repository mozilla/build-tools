"""
Release sanity lib module in the new release promotion world.
It's functionality is to replace the old way of doing it in
http://hg.mozilla.org/build/tools/file/old-release-runner/buildbot-helpers/release_sanity.py

Additionally, more checks are performed to cope with the new release promotion
world regulations and constraints.
"""
import sys
import site
import logging
from os import path

import requests

site.addsitedir(path.join(path.dirname(__file__), ".."))
from util.retry import retry
from util.hg import make_hg_url
from release.versions import getL10nDashboardVersion
from kickoff import matches

log = logging.getLogger(__name__)

CANDIDATES_SHA512_URL_TEMPLATE = "https://archive.mozilla.org/pub/firefox/candidates/{version}-candidates/build{build_number}/SHA512SUMS"
RELEASES_SHA512_URL_TEMPLATE= "https://archive.mozilla.org/pub/firefox/releases/{version}/SHA512SUMS"
L10N_DASHBOARD_URL_TEMPLATE = "https://l10n.mozilla.org/shipping/l10n-changesets?ms={milestone}"
LOCALE_BASE_URL_TEMPLATE = "{hg_l10n_base}/{locale}/raw-file/{revision}"
SINGLE_LOCALE_CONFIG_URI_TEMPLATE = "testing/mozharness/configs/single_locale/{branch}.py"
VERSION_DISPLAY_CONFIG_URI = "browser/config/version_display.txt"
SHIPPED_LOCALES_CONFIG_URI = "browser/locales/shipped-locales"
BETA_PATTERNS = [r"\d+\.0b\d+"]


def make_generic_head_request(page_url):
    """Make generic HEAD request to check page existence"""
    def _get():
        req = requests.head(page_url, timeout=60)
        req.raise_for_status()

    retry(_get, attempts=5, sleeptime=1)


def make_generic_get_request(page_url):
    """Make generic GET request to retrieve some page content"""
    def _get():
        req = requests.get(page_url, timeout=60)
        req.raise_for_status()
        return req.content

    return retry(_get, attempts=5, sleeptime=1)


def make_hg_get_request(repo_path, revision,
                        filename=None, hg_url='hg.mozilla.org'):
    """Wrapper to make a GET request for a specific URI under hg repo"""
    url = make_hg_url(hg_url, repo_path, revision=revision, filename=filename)
    return make_generic_get_request(url)


def is_candidate_release(channels):
    """Determine if this is a candidate release or not

    Because ship-it can not tell us if this is a candidate release (yet!),
    we assume it is when we have determined, based on version,
    that we are planning to ship to more than one update_channel
    e.g. for candidate releases we have:
     1) one channel to test the 'candidate' release with: 'beta' channel
     2) once verified, we ship to the main channel: 'release' channel
    """
    return len(channels) > 1


def get_l10_dashboard_changeset(version, product):
    """Helper function to retrieve l10n dashboard changesets

    >>> get_l10_dashboard_changeset('47.0, 'firefox')
    ach revision_123
    af revision_245
    an revision_456
    ...
    """
    l10n_dashboard_version = getL10nDashboardVersion(version, product)
    url = L10N_DASHBOARD_URL_TEMPLATE.format(milestone=l10n_dashboard_version)

    ret = make_generic_get_request(url).strip()

    dash_dict = dict()
    for line in ret.splitlines():
        locale, revision = line.split()
        dash_dict[locale] = revision

    return dash_dict


def get_single_locale_config(repo_path, revision, branch):
    """Get single locale from remote mh configs
    Example for mozilla-beta, random revision:

    >>>
    config = {
        "nightly_build": True,
        "branch": "mozilla-beta",
        ...
        # l10n
        "hg_l10n_base": "https://hg.mozilla.org/releases/l10n/mozilla-beta",
        # repositories
        "mozilla_dir": "mozilla-beta",
        'purge_minsize': 12,
        'is_automation': True,
        ...
    }
    """
    filename = SINGLE_LOCALE_CONFIG_URI_TEMPLATE.format(branch=branch)
    return make_hg_get_request(repo_path, revision, filename=filename)


class SanityException(Exception):
    """Should the release sanity process collect any errors, this
    custom exception is to be thrown in release runner.
    """
    pass


class OpsMixin(object):
    """Helper class Mixin to enrich ReleaseSanitizerTestSuite behavior
    """
    def assertEqual(self, result, first, second, err_msg):
        """Method inspired from unittest implementation
        The :result is the aggregation object to collect all potential errors
        """
        if not first == second:
            result.add_error(err_msg)


class ReleaseSanitizerTestSuite(OpsMixin):
    """Main release sanity class - the one to encompass all test methods and
    all behavioral changes that need to be addressed. It is inspired by
    the functionality of unittest module classes. It needs to be used
    along with a ReleaseSanitizerResult object to aggregate all potential
    exceptions.

    Once instance needs to hold the task graph arguments that come from
    Ship-it via release runner. Using the arguments, certain behaviors are
    tested (e.g. partials, l10n, versions, config, etc)

    To add more testing methods, please prefix the method with 'test_' in
    order to have it run by sanitize() main method.
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.repo_path = self.kwargs["repo_path"]
        self.revision = self.kwargs["revision"]
        self.version = self.kwargs["version"]
        self.branch = self.kwargs["branch"]
        self.locales = self.kwargs["l10n_changesets"]
        self.product = self.kwargs["product"]
        self.partial_updates = self.kwargs["partial_updates"]

    def sanitize(self, result):
        """Main method to run all the sanity checks. It collects all the
        methods prefixed with 'test_' and runs them accordingly.
        It runs all the test and collects any potential errors in the :result
        object.
        """
        test_methods = [m for m in filter(lambda k: k.startswith("test_"), dir(self))
                        if callable(getattr(self, m))]
        for test_method in test_methods:
            log.debug("Calling testing method %s", test_method)
            getattr(self, test_method)(result)

    def test_versions_repo_and_revision_check(self, result):
        """test_versions method
        Tests if the indicated branch and revision repo exists
        """
        log.info("Testing repo and revision in tree ...")
        try:
            make_hg_get_request(self.repo_path, self.revision).strip()
        except requests.HTTPError as err:
            err_msg = "{path} repo does not exist with {rev} revision. URL: {url}".format(
                path=self.repo_path, rev=self.revision, url=err.request.url)
            result.add_error(err_msg, sys.exc_info())

    def test_versions_display_validation_in_tree(self, result):
        """test_versions method
        Tests if the upstream display version exists and if it is the same
        with the current one coming from release runner
        """
        log.info("Testing version display validation in tree ...")
        # esr-hack: ensure trimming the suffix before comparing
        version = self.version.replace("esr", "")

        try:
            display_version = make_hg_get_request(self.repo_path, self.revision,
                                                  filename=VERSION_DISPLAY_CONFIG_URI).strip()
        except requests.HTTPError as err:
            err_msg = ("display_version config file not found in {path} under"
                       " {rev} revision. URL: {url}").format(
                           path=self.repo_path,
                           rev=self.revision,
                           url=err.request.url)
            result.add_error(err_msg, sys.exc_info())
            return

        err_msg = ("In-tree display version {tree_version} doesn't "
                   "match ship-it version {version}").format(
                       tree_version=display_version, version=version)
        self.assertEqual(result, version, display_version, err_msg)

    def test_partials_validity(self, result):
        """test_partials method
        Tests some validity checks against the partials. It goes over the list
        of specified partials and performs some tests:
            1. Firstly, checks the partial version has a corresponding
            (version, buildnumer) under the candidates directory on S3.
            In order to perform this check, rather than checking the complete
            mar (CMAR) files, we check the SHA512 checksums file. Upon a
            successful release build, the checksums file is the last one
            to be generated since it contains all the hashes for all the files.
            Therefore, if the checksums file exist, it means allthe other files
            made it through the candidates directory (including CMAR)

            2. Secondly, checks if the partial versions has a corresponding
            of that specific version under releases directory on S3.
            The first check ensured that we had a release build that made it
            through the candidates directory, now we need to checck if we
            actually had a successful ship for that particular partial version.
            For that, we follow the same logic as above by checking the SHA512
            checksums under the releases directory. If it's there, it means we
            have successfully shipped. If something went wrong, we'll hit an
            error.

            3. Ultimately it makes sure the partial version build from
            candidates is actually the same that shipped under releases.
            This check prevents one possible fail-scenario in which the build
            under canidates is good and valid, but a follow-up build was
            actually shipped under releases. Since shipping to releases
            implies an actual copy of the files, for that particular reason we
            make sure that SHA512 checksums of the build under candidates is
            bitwise the same as the one from releases.
        """
        log.info("Testing partials validity ...")
        def grab_partial_sha(url):
            """Quick helper function to grab a SHA512 file"""
            sha_sum = None
            try:
                sha_sum = make_generic_get_request(url).strip()
            except requests.HTTPError:
                err_msg = "Broken build - hash {url} not found".format(url=url)
                result.add_error(err_msg, sys.exc_info())

            return sha_sum

        for pversion, info in self.kwargs["partial_updates"].iteritems():
            buildno = info["buildNumber"]

            # make sure partial is valid and shipped correctly to /candidates
            _url = CANDIDATES_SHA512_URL_TEMPLATE.format(version=pversion,
                                                         build_number=buildno)
            candidate_sha = grab_partial_sha(_url)

            # make sure partial has a shipped release under /releases
            _url = RELEASES_SHA512_URL_TEMPLATE.format(version=pversion)
            releases_sha = grab_partial_sha(_url)

            err_msg = ("{version}-build{build_number} is a good candidate"
                       " build, but not the one we shipped! URL: {url}").format(
                           version=pversion,
                           build_number=buildno,
                           url=_url)
            self.assertEqual(result, releases_sha, candidate_sha, err_msg)

    def test_partials_release_candidate_validity(self, result):
        """test_partials method
        Tests if a RC contains both beta and release in list of partials.
        We hit this issue in bug 1265579 in which the updates builder failed
        if partials were all-beta OR if no-beta at all
        """
        log.info("Testing RC partials ...")
        if not is_candidate_release(self.kwargs["release_channels"]):
            log.info("Skipping this test as we're not dealing with a RC now")
            return

        ret = [matches(name, BETA_PATTERNS) for name in self.partial_updates]
        at_least_one_beta = any(ret)
        all_betas = all(ret) and ret != []

        partials = ["{name}".format(name=p) for p in self.partial_updates]
        err_msg = "No beta found in the RC list of partials: {l}".format(l=partials)
        self.assertEqual(result, at_least_one_beta, True, err_msg)

        err_msg = ("All partials in the RC list are betas. At least a non-beta"
                   " release is needed in {l}").format(l=partials)
        self.assertEqual(result, all_betas, False, err_msg)

    def test_l10n_shipped_locales(self, result):
        """test_l10n method
        Tests if the current locales coming from release runner are in fact
        the same as the shipped locales.
        """
        log.info("Testing l10n shipped locales ...")
        try:
            # TODO: mind that we will need something similar for Fennec
            ret = make_hg_get_request(self.repo_path, self.revision,
                                      filename=SHIPPED_LOCALES_CONFIG_URI).strip()
        except requests.HTTPError as err:
            err_msg = ("Shipped locale file not found in {path} repo under rev"
                       " {revision}. URL: {url}").format(
                           path=self.repo_path,
                           revision=self.revision,
                           url=err.request.url)
            result.add_error(err_msg, sys.exc_info())
            return

        shipped_l10n = set([l.split()[0] for l in ret.splitlines()])
        current_l10n = set(self.locales.keys())

        err_msg = "Current l10n changesets and shipped locales differ!"
        # we have en-US in shipped locales, but not in l10n changesets, because
        # there is no en-US repo
        self.assertEqual(result, shipped_l10n.difference(current_l10n),
                         set(['en-US']),
                         err_msg)
        self.assertEqual(result, current_l10n.difference(shipped_l10n),
                         set([]),
                         err_msg)

    def test_l10n_verify_changesets(self, result):
        """test_l10n method
        Tests if the l10n changesets (locale, revision) are actually valid.
        It does a validity check on each of the locales revision. In order
        to query that particular l10n release url, the single locale
        config file from mozharness is grabbed first.
        """
        log.info("Testing current l10n changesets ...")
        try:
            ret = get_single_locale_config(self.repo_path,
                                           self.revision,
                                           self.branch).strip()
        except requests.HTTPError as err:
            err_msg = ("Failed to retrieve single locale config file for"
                       " {path}, revision {rev}. URL: {url}").format(
                           path=self.repo_path,
                           rev=self.revision,
                           branch=self.branch,
                           url=err.request.url)
            result.add_error(err_msg, sys.exc_info())
            return

        locals_dict = dict()
        exec(ret, {}, locals_dict)
        single_locale_config = locals_dict.get('config')

        for locale in sorted(self.locales.keys()):
            revision = self.locales[locale]
            locale_url = LOCALE_BASE_URL_TEMPLATE.format(
                hg_l10n_base=single_locale_config["hg_l10n_base"].strip('/'),
                locale=locale,
                revision=revision
            )

            try:
                make_generic_head_request(locale_url)
            except requests.HTTPError:
                err_msg = "Locale {locale} not found".format(locale=locale_url)
                result.add_error(err_msg, sys.exc_info())

    def test_l10n_dashboard(self, result):
        """test_l10n method
        Tests if l10n dashboard changesets match the current l10n changesets
        """
        log.info("Testing l10n dashboard changesets ...")
        if not self.kwargs["dashboard_check"]:
            log.info("Skipping l10n dashboard check")
            return

        try:
            dash_changesets = get_l10_dashboard_changeset(self.version,
                                                          self.product)
        except requests.HTTPError as err:
            err_msg = ("Failed to retrieve l10n dashboard changes for"
                       " {product} product, version {version}. URL: {url}").format(
                           product=self.product,
                           version=self.version,
                           url=err.request.url)
            result.add_error(err_msg, sys.exc_info())
            return

        err_msg = ("Current ship-it changesets are not the same as the l10n"
                   " dashboard changesets")
        self.assertEqual(result, self.locales, dash_changesets, err_msg)


class ReleaseSanitizerResult(object):
    """Aggregate exceptions result-object like. It's passed down in all
    ReleaseSanitizerTestSuite methods to collect all potential errors.
    This is usefule to avoid incremenatal fixes in release sanity
    """
    def __init__(self):
        self.errors = []

    def add_error(self, err_msg, err=None):
        """Method to collect a new errors. It collects the exception
        stacktrace and stores the exception value along with the message"""
        # each error consist of a tuple containing the error message and any
        # other potential information we might get useful from the
        # sys.exc_info(). If there is no such, explanatory string will be added
        self.errors.append((err_msg, self._exc_info_to_string(err)))
        # append an empty line after each exceptions to have a nicer output
        log.info("Collecting a new exception: %s", err_msg)

    def _exc_info_to_string(self, err):
        if err is None:
            return "Result of assertion, no exception stacktrace available"
        # trim the traceback part from the exc_info result tuple
        _, value = err[:2]
        return value

    def __str__(self):
        """Define the output to be user-friendly readable"""
        # make some room to separate the output from the exception stacktrace
        ret = "\n\n"
        for msg, err in self.errors:
            ret += "* {msg}:\n{err}\n\n".format(msg=msg, err=err)
        return ret


class ReleaseSanitizerRunner(object):
    """Runner class that is to be called from release runner. It wraps up
    the logic to interfere with both the ReleaseSanitizerTestSuite and the
    ReleaseSanitizerResult. Upon successful run, errors in results should be
    an empty list. Otherwise, the errors list can be retrieved and processed.
    """
    resultClass = ReleaseSanitizerResult
    testSuite = ReleaseSanitizerTestSuite

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.result = self.resultClass()

    def run(self):
        """Main method to call for the actual test of release sanity"""
        test_suite = self.testSuite(**self.kwargs)
        log.info("Attempting to sanitize ...")
        test_suite.sanitize(self.result)

    def was_successful(self):
        """Tells whether or not the result was a success"""
        return len(self.result.errors) == 0

    def get_errors(self):
        """Retrieves the list of errors from the result objecti
        in a nicely-formatted string
        """
        return self.result
