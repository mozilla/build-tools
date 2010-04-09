#!/usr/bin/perl -w
use strict;

use Config::General;
use File::Spec::Functions;
use File::Temp qw(tempdir);
use Getopt::Long;
use Storable;

use Bootstrap::Util qw(LoadLocaleManifest);

use Release::Patcher::Config qw(GetProductDetails GetReleaseBlock);
use Release::Versions qw(GetPrettyVersion);

$|++;

# we disable this for bug 498273
# my $RELEASE_CANDIDATE_CHANNELS = ['betatest', 'DisableCompleteJump'];
# This will be put into all patcher configs, but it will have no effect for
# those which don't generate partials (eg, major updates).
my $FORCE_FILES = ['freebl3.chk', 'softokn3.chk', 'nssdbm3.chk',
                   'components/components.list',
                   'Contents/MacOS/components/components.list'];

my %config;

ProcessArgs();
if (defined $config{'run-tests'}) {
    RunUnitTests();
} else {
    CreatePatcherConfig();
}

sub ProcessArgs {
    GetOptions(
        \%config,
        "product|p=s", "brand|r=s", "version|v=s", "old-version|o=s",
        "app-version|a=s", "old-app-version=s", "build-number|b=s",
        "old-build-number=s", "patcher-config|c=s", "staging-server|t=s",
        "ftp-server|f=s", "bouncer-server|d=s", "use-beta-channel|u",
        "shipped-locales|l=s", "old-shipped-locales=s", "update-type=s",
        "releasenotes-url|n=s", "help|h", "run-tests"
    );

    if ($config{'help'}) {
        print <<__USAGE__;
Usage: patcher-config-creator.pl [options]
This script depends on the Bootstrap::Util, Release::Versions, and
Release::Patcher::Config modules.
Options: 
  -p The product name (eg. firefox, thunderbird, seamonkey, etc.)
  -r The brand name (eg. Firefox, Thunderbird, SeaMonkey, etc.)
     If not specified, a first-letter-uppercased product name is assumed.
  -v The current version of the product (eg. 3.1a1, 3.0rc1)
  -o The previous version of the product (eg. 3.0, 3.0b5)
  -a The current 'app version' of the product (eg. 3.1a1, 3.0). If not
     specified is assumed to be the same as version
  --old-app-version The previous 'app version' of the product. Assumed to be the
                    same as old version if not speicfied
  -b The current build number of this release. (eg, 1, 2, 3)
  --old-build-number The build number of the previous release.
  -c The path and filename of the config file to be created.
  -f The FTP server to serve beta builds from. Typically is ftp.mozilla.org
  -t The staging server to serve test builds from. Typically is
     stage.mozilla.org or stage-old.mozilla.org
  -d The hostname of the Bouncer server to serve release builds from.
     Typically is download.mozilla.org.
  -l The path and filename to the shipped-locales file for this release.
  --old-shipped-locales The path and filename to the shipped-locales file for
                        the previous release
  -u When not passed, the Beta channel will be considered the channel for final
     release. Specifically, this will cause the 'beta' channel snippets to
     point at the Bouncer server (rather than FTP). When passed, the
     'release' channel will be considered the channel for final release.
     This means that 'release' channel snippets will point to bouncer and
     'beta' channel ones will point to FTP.
     Generally, Alphas and Betas do not pass this, final and point releases do.
  --update-type The update type (minor, major). Defaults to minor.
  -n Release notes URL.
  -h This usage message.
  --run-tests will run the (very basic) unit tests included with this script.
__USAGE__

        exit(0);
    }

    my $error = 0;

    # Just some input validation, not necessary if we're only running tests
    if (! defined $config{'run-tests'}) {
        for my $arg ('product', 'version', 'old-version', 'build-number',
                     'old-build-number', 'staging-server', 'ftp-server',
                     'bouncer-server', 'patcher-config') {
            if (! defined $config{$arg}) {
                print "$arg must be defined.\n";
                $error = 1;
            }
        }
        if (! defined $config{'shipped-locales'} or
                 ! -e $config{'shipped-locales'}) {
            print "shipped locales file must exist.\n";
            $error = 1;
        }
        if (! defined $config{'old-shipped-locales'} or
                 ! -e $config{'old-shipped-locales'}) {
            print "old shipped locales file must exist.\n";
            $error = 1;
        }
        if ($error) {
            exit($error);
        }
    }

    # set sane defaults
    if (! defined $config{'brand'}) {
        $config{'brand'} = ucfirst($config{'product'});
    }
    if (! defined $config{'app-version'}) {
        $config{'app-version'} = $config{'version'};
    }
    if (! defined $config{'old-app-version'}) {
        $config{'old-app-version'} = $config{'old-version'};
    }
    if (! defined $config{'use-beta-channel'}) {
        $config{'use-beta-channel'} = 0;
    }
    if (! defined $config{'update-type'}) {
        $config{'update-type'} = 'minor';
    }
}    
    
sub CreatePatcherConfig {
    my $product = $config{'product'};
    my $brand = $config{'brand'};
    my $version = $config{'version'};
    my $oldVersion = $config{'old-version'};
    my $appVersion = $config{'app-version'};
    my $oldAppVersion = $config{'old-app-version'};
    my $build = $config{'build-number'};
    my $oldBuild = $config{'old-build-number'};
    my $patcherConfig = $config{'patcher-config'};
    my $stagingServer = $config{'staging-server'};
    my $ftpServer = $config{'ftp-server'};
    my $bouncerServer = $config{'bouncer-server'};
    my $useBetaChannel = $config{'use-beta-channel'};
    my $shippedLocales = $config{'shipped-locales'};
    my $oldShippedLocales = $config{'old-shipped-locales'};
    my $updateType = $config{'update-type'};
    my $configBumpDir = '.';
    my $releaseNotesUrl = $config{'releasenotes-url'};

    my $prettyVersion = GetPrettyVersion(version => $version);

    my $oldPrettyVersion = GetPrettyVersion(version => $oldVersion);

    my @channels = ('beta');
    if ($useBetaChannel) {
        push(@channels, 'release');
    }
    my @testChannels = ('betatest', 'releasetest');

    my $details = $releaseNotesUrl || GetProductDetails(product => $product,
        appVersion => $appVersion, updateType => $updateType);

    my $buildStr = 'build' . $build;
    my $oldBuildStr = 'build' . $oldBuild;

    my $localeInfo = {};
    if (not LoadLocaleManifest(localeHashRef => $localeInfo,
                               manifest => $shippedLocales)) {
        die "Could not load locale manifest from $shippedLocales";
    }
    my $oldLocaleInfo = {};
    if (not LoadLocaleManifest(localeHashRef => $oldLocaleInfo,
                               manifest => $oldShippedLocales)) {
        die "Could not load locale manifest from $oldShippedLocales";
    }

    my $rawConfig = {};
    $rawConfig->{'app'} = {};
    $rawConfig->{'app'}->{$brand} = {};
    my $currentUpdateObj = $rawConfig->{'app'}->{$brand}->{'current-update'} = {};
    my $releaseObj = $rawConfig->{'app'}->{$brand}->{'release'} = {};

    if ($updateType ne 'minor') {
        $currentUpdateObj->{'updateType'} = $updateType;
    }
    if ($useBetaChannel) {
        $currentUpdateObj->{'beta-dir'} = 'beta';
    }
    $currentUpdateObj->{'force'} = $FORCE_FILES;
    $currentUpdateObj->{'from'} = $oldVersion;
    $currentUpdateObj->{'to'} = $version;
    $currentUpdateObj->{'channel'} = join(' ', @channels);
    $currentUpdateObj->{'testchannel'} = join(' ', @testChannels);
    $currentUpdateObj->{'details'} = $details;
    $currentUpdateObj->{'complete'} = {};
    $currentUpdateObj->{'complete'}->{'url'} = 'http://' . $bouncerServer .
      '/?product=' . $product . '-' . $version .
      '-complete&os=%bouncer-platform%&lang=%locale%';
    if ($updateType eq 'major') {
        $currentUpdateObj->{'complete'}->{'path'} = $product . '-' . $version .
          '.%locale%.%platform%.complete.mar';
    }
    else {
        $currentUpdateObj->{'complete'}->{'path'} = catfile($product, 'nightly',
          $version . '-candidates', $buildStr, 'update', '%platform%',
          '%locale%', $product . '-' . $version . '.complete.mar');
    }
    $currentUpdateObj->{'complete'}->{'betatest-url'} = 'http://' .
      $stagingServer . '/pub/mozilla.org/' . $product . '/nightly/' . $version .
      '-candidates/' . $buildStr . '/update/%platform%/%locale%/' . $product .
      '-' . $version . '.complete.mar';
    if ($updateType eq 'major') {
        my %completeCopy = %{$currentUpdateObj->{'complete'}};
        $currentUpdateObj->{'partial'} = \%completeCopy;
    }
    else {
        $currentUpdateObj->{'partial'} = {};
        $currentUpdateObj->{'partial'}->{'url'} = 'http://' . $bouncerServer .
          '/?product=' . $product . '-' . $version . '-partial-' . $oldVersion .
          '&os=%bouncer-platform%&lang=%locale%';
        $currentUpdateObj->{'partial'}->{'path'} = catfile($product, 'nightly',
          $version . '-candidates', $buildStr, 'update', '%platform%',
          '%locale%', $product . '-' . $oldVersion . '-' . $version .
          '.partial.mar');
        $currentUpdateObj->{'partial'}->{'betatest-url'} = 'http://' .
          $stagingServer . '/pub/mozilla.org/' . $product . '/nightly/' .
          $version . '-candidates/' . $buildStr .
          '/update/%platform%/%locale%/' . $product . '-' . $oldVersion . '-' .
          $version . '.partial.mar';
    }

    $releaseObj->{$oldVersion} = GetReleaseBlock(version => $oldVersion,
                                                 appVersion => $oldAppVersion,
                                                 prettyVersion => $oldPrettyVersion,
                                                 product => $product,
                                                 buildstr => $oldBuildStr,
                                                 stagingServer => $stagingServer,
                                                 localeInfo => $oldLocaleInfo);
    
    $releaseObj->{$version} = GetReleaseBlock(version => $version,
                                              appVersion => $appVersion,
                                              prettyVersion => $prettyVersion,
                                              product => $product,
                                              buildstr => $buildStr,
                                              stagingServer => $stagingServer,
                                              localeInfo => $localeInfo);


    my $patcherConfigObj = new Config::General($rawConfig);
    $patcherConfigObj->save_file($patcherConfig);
}

sub RunUnitTests {
    # CreatePatcherConfig() pulls build IDs from the stagingServer it is given,
    # which means our tests depend on certain files existing on it, too.
    # Specifically, we need:
    #  http://$stagingServer/pub/mozilla.org/$product/nightly/$version-candidates/build$buildNumber/$platform_info.txt
    # and the equivalent for oldVersion.
    ExecuteTest(
        product => 'firefox',
        brand => 'Firefox',
        version => '3.6b1',
        appVersion => '3.6b1',
        prettyVersion => '3.6 Beta 1',
        oldVersion => '3.6a1',
        oldAppVersion => '3.6a1',
        oldPrettyVersion => '3.6 Alpha 1',
        build => 3,
        oldBuild => 1,
        useBetaChannel => 0,
        updateType => 'minor',
        referenceConfig => 'patcher-configs/moz-minor-patcher-unit-test.cfg',
        locales => ['af', 'en-US', 'gu-IN', 'ja linux win32',
                    'ja-JP-mac osx', 'uk'],
        oldLocales => ['en-US']
    );
    ExecuteTest(
        product => 'firefox',
        brand => 'Firefox',
        version => '3.6rc2',
        appVersion => '3.6',
        prettyVersion => '3.6 RC 2',
        oldVersion => '3.5.7',
        oldAppVersion => '3.5.7',
        oldPrettyVersion => '3.5.7',
        build => 1,
        oldBuild => 1,
        useBetaChannel => 1,
        updateType => 'major',
        referenceConfig => 'patcher-configs/moz-major-patcher-unit-test.cfg',
        locales => ['af', 'en-US', 'gu-IN', 'ja linux win32',
                    'ja-JP-mac osx', 'uk'],
        oldLocales => ['af', 'en-US', 'gu-IN', 'ja linux win32',
                       'ja-JP-mac osx', 'uk'],
    );
}

sub ExecuteTest {
    my %args = @_;
    my $workdir = tempdir(CLEANUP => 1);
    my $product = $args{'product'};
    my $brand = $args{'brand'};
    my $version = $args{'version'};
    my $appVersion = $args{'appVersion'};
    my $prettyVersion = $args{'prettyVersion'};
    my $oldVersion = $args{'oldVersion'};
    my $oldAppVersion = $args{'oldAppVersion'};
    my $oldPrettyVersion = $args{'oldPrettyVersion'};
    my $build = $args{'build'};
    my $oldBuild = $args{'oldBuild'};
    my $useBetaChannel = $args{'useBetaChannel'};
    my $updateType = $args{'updateType'};
    my $referenceConfig = $args{'referenceConfig'};
    my @locales = @{$args{'locales'}};
    my @oldLocales = @{$args{'oldLocales'}};
    my $patcherConfig = catfile($workdir, 'moztest-patcher2.cfg');
    # Using this update-bump-unit-tests dir makes the mar URLs less realistic
    # but doesn't affect the validity of the tests.
    my $stagingServer = 'build.mozilla.org/update-bump-unit-tests';
    my $ftpServer = 'ftp.mozilla.org';
    my $bouncerServer = 'download.mozilla.org';

    my $shippedLocales = catfile($workdir, 'shipped-locales');
    open (SHIPPED_LOCALES, ">$shippedLocales");
    for my $l (@locales) {
        print SHIPPED_LOCALES "$l\n";
    }
    close(SHIPPED_LOCALES);
    my $oldShippedLocales = catfile($workdir, 'old-shipped-locales');
    open (OLD_SHIPPED_LOCALES, ">$oldShippedLocales");
    for my $l (@oldLocales) {
        print OLD_SHIPPED_LOCALES "$l\n";
    }
    close(OLD_SHIPPED_LOCALES);

    # We need to build up the global config object before calling
    # BumpPatcherConfig
    $config{'product'} = $product;
    $config{'brand'} = $brand;
    $config{'version'} = $version;
    $config{'old-version'} = $oldVersion;
    $config{'app-version'} = $appVersion;
    $config{'old-app-version'} = $oldAppVersion;
    $config{'build-number'} = $build;
    $config{'old-build-number'} = $oldBuild;
    $config{'patcher-config'} = $patcherConfig;
    $config{'staging-server'} = $stagingServer;
    $config{'ftp-server'} = $ftpServer;
    $config{'bouncer-server'} = $bouncerServer;
    $config{'use-beta-channel'} = $useBetaChannel;
    $config{'shipped-locales'} = $shippedLocales;
    $config{'old-shipped-locales'} = $oldShippedLocales;
    $config{'update-type'} = $updateType;
    CreatePatcherConfig();

    # Now, read the newly bumped patcher config file back in
    my $bumpedConfigObj = new Config::General(-ConfigFile => $patcherConfig);
    my %bumpedConfig = $bumpedConfigObj->getall;
    my $refConfigObj = new Config::General(-ConfigFile => $referenceConfig);
    my %referenceConfig = $refConfigObj->getall;

    if (deeply_equal(\%bumpedConfig, \%referenceConfig)) {
        print "PASS\n";
        return 0;
    } else {
        print "FAIL\n";
        $bumpedConfigObj->save_file("bumped-patcher.cfg");
        print "Boostrapped patcher config written to bumped-patcher.cfg\n";
        my $referenceConfigObj = new Config::General($referenceConfig);
        $referenceConfigObj->save_file("reference-patcher.cfg");
        print "Reference patcher config written to reference-patcher.cfg\n";
        print "Please examine them to debug the problem.\n";
        return 1;
    }
}


# Taken from http://www.perlmonks.org/?node_id=121559
sub deeply_equal {
  my ( $a_ref, $b_ref ) = @_;
    
  local $Storable::canonical = 1;
  return Storable::freeze( $a_ref ) eq Storable::freeze( $b_ref );
}
