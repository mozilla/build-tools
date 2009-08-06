#!/usr/bin/perl -w
use strict;

use Config::General;
use File::Spec::Functions;
use File::Temp qw(tempdir);
use Getopt::Long;
use Storable;

use MozBuild::Util qw(GetBuildIDFromFTP);

use Bootstrap::Util qw(GetBouncerPlatforms GetBouncerToPatcherPlatformMap
                       LoadLocaleManifest);

$|++;

# we disable this for bug 498273
# my $RELEASE_CANDIDATE_CHANNELS = ['betatest', 'DisableCompleteJump'];

my %config;

ProcessArgs();
if (defined $config{'run-tests'}) {
    RunUnitTests();
} else {
    BumpPatcherConfig();
}

sub ProcessArgs {
    GetOptions(
        \%config,
        "product|p=s", "brand|r=s", "version|v=s", "old-version|o=s",
        "app-version|a=s", "build-number|b=s", "patcher-config|c=s",
        "staging-server|t=s", "ftp-server|f=s", "bouncer-server|d=s",
        "use-beta-channel|u", "shipped-locales|l=s", "help|h", "run-tests"
    );

    if ($config{'help'}) {
        print <<__USAGE__;
Usage: bump-patcher-config.pl [options]
This script depends on the MozBuild::Util and Bootstrap::Util modules.
Options: 
  -p The product name (eg. firefox, thunderbird, seamonkey, etc.)
  -r The brand name (eg. Firefox, Thunderbird, SeaMonkey, etc.)
     If not specified, a first-letter-uppercased product name is assumed.
  -v The current version of the product (eg. 3.1a1, 3.0rc1)
  -a The current 'app version' of the product (eg. 3.1a1, 3.0). If not
     specified is assumed to be the same as version
  -o The previous version of the product (eg. 3.0, 3.0b5)
  -b The current build number of this release. (eg, 1, 2, 3)
  -c The path and filename of the config file to be bumped.
  -f The FTP server to serve beta builds from. Typically is ftp.mozilla.org
  -t The staging server to serve test builds from. Typically is
     stage.mozilla.org or stage-old.mozilla.org
  -d The hostname of the Bouncer server to serve release builds from.
     Typically is download.mozilla.org.
  -u When not passed, the Beta channel will be considered the channel for final
     release. Specifically, this will cause the 'beta' channel snippets to
     point at the Bouncer server (rather than FTP). When passed, the
     'release' channel will be considered the channel for final release.
     This means that 'release' channel snippets will point to bouncer and
     'beta' channel ones will point to FTP.
     Generally, Alphas and Betas do not pass this, final and point releases do.
  -l The path and filename to the shipped-locales file for this release.
  -h This usage message.
  --run-tests will run the (very basic) unit tests included with this script.
__USAGE__

        exit(0);
    }

    my $error = 0;

    # Just some input validation, not necessary if we're only running tests
    if (! defined $config{'run-tests'}) {
        for my $arg ('product', 'version', 'old-version', 'build-number',
                     'staging-server', 'ftp-server', 'bouncer-server') {
            if (! defined $config{$arg}) {
                print "$arg must be defined.\n";
                $error = 1;
            }
        }
        if (! defined $config{'patcher-config'} or
                 ! -w $config{'patcher-config'}) {
            print "patcher config file must exist and be writable.\n";
            $error = 1;
        }
        if (! defined $config{'shipped-locales'} or
                 ! -e $config{'shipped-locales'}) {
            print "shipped locales file must exist.\n";
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
    if (! defined $config{'use-beta-channel'}) {
        $config{'use-beta-channel'} = 0;
    }

}    

sub BumpFilePath {
    my %args = @_;
    my $oldFilePath = $args{'oldFilePath'};
    my $product = $config{'product'};
    my $version = $config{'version'};
    my $oldVersion = $config{'old-version'};

    # we need an escaped copy of oldVersion so we can accurately match
    # filenames
    my $escapedOldVersion = $oldVersion;
    $escapedOldVersion =~ s/\./\\./g;
    my $escapedVersion = $version;
    $escapedVersion =~ s/\./\\./g;

    # strip out everything up to and including 'buildN/'
    my $newPath = $oldFilePath;
    $newPath =~ s/.*\/build\d+\///;
    # We need to handle partials and complete MARs differently
    if ($newPath =~ m/\.partial\.mar$/) {
        $newPath =~ s/$product-.+?-($escapedOldVersion|$escapedVersion)\.
                     /$product-$oldVersion-$version./x
                     or die("ASSERT: BumpFilePath() - Could not bump path: " .
                            "$oldFilePath");
    } elsif ($newPath =~ m/\.complete\.mar$/) {
        $newPath =~ s/$product-($escapedOldVersion|$escapedVersion)\.
                     /$product-$version./x
                     or die("ASSERT: BumpFilePath() - Could not bump path: " .
                            "$oldFilePath");
    } else {
        die("ASSERT: BumpFilePath() - Unknown file type for '$oldFilePath'");
    }

    return $newPath;
}

sub BumpPatcherConfig {
    my $product = $config{'product'};
    my $brand = $config{'brand'};
    my $version = $config{'version'};
    my $oldVersion = $config{'old-version'};
    my $appVersion = $config{'app-version'};
    my $build = $config{'build-number'};
    my $patcherConfig = $config{'patcher-config'};
    my $stagingServer = $config{'staging-server'};
    my $ftpServer = $config{'ftp-server'};
    my $bouncerServer = $config{'bouncer-server'};
    my $useBetaChannel = $config{'use-beta-channel'};
    my $configBumpDir = '.';

    my $prettyVersion = $version;
    $prettyVersion =~ s/a([0-9]+)$/ Alpha $1/;
    $prettyVersion =~ s/b([0-9]+)$/ Beta $1/;
    $prettyVersion =~ s/rc([0-9]+)$/ RC $1/;

    my $localeInfo = {};
    if (not LoadLocaleManifest(localeHashRef => $localeInfo,
                               manifest => $config{'shipped-locales'})) {
        die "Could not load locale manifest";
    }

    my $patcherConfigObj = new Config::General(-ConfigFile => $patcherConfig);

    my %rawConfig = $patcherConfigObj->getall();
    die "ASSERT: BumpPatcherConfig(): null rawConfig" 
     if (0 == scalar(keys(%rawConfig)));

    my $appObj = $rawConfig{'app'}->{$brand};
    die "ASSERT: BumpPatcherConfig(): null appObj" if (! defined($appObj));

    my $currentUpdateObj = $appObj->{'current-update'};

    # Add the release we're replacing to the past-releases array, but only if
    # it's a new release; we used to determine this by looking at the build 
    # value, but that can be misleading because sometimes we may not get to
    # the update step before a respin; so what we really need to compare is 
    # whether our current version in bootstrap.cfg is in the to clause of the 
    # patcher config file/object; we now control this via doOnetimePatcherBumps.
    #
    # More complicated than it needs to be because it handles the (uncommon)
    # case that there is no past-update yet (e.g. Firefox 3.0)

    my $doOnetimePatcherBumps = ($currentUpdateObj->{'to'} ne $version);

    if ($doOnetimePatcherBumps) {
        my $pastUpdateObj = $appObj->{'past-update'};
        if (ref($pastUpdateObj) ne 'ARRAY') {
            my $oldSinglePastUpdateStr = $pastUpdateObj;
            $appObj->{'past-update'} = $pastUpdateObj = [];
            push(@{$pastUpdateObj}, $oldSinglePastUpdateStr);
        }

        my @pastUpdateChannels = (split(/[\s,]+/,
                                   $currentUpdateObj->{'testchannel'}),
                                  split(/[\s,]+/,
                                   $currentUpdateObj->{'channel'}));

        push(@{$pastUpdateObj}, join(' ', $currentUpdateObj->{'from'},
         $currentUpdateObj->{'to'}, @pastUpdateChannels));
    }

    # Now we can replace information in the "current-update" object; start
    # with the to/from versions, the rc channels, then the information for
    # the partial and complete update patches
    #
    # Only bump the to/from versions if we're really a new release. We used
    # to determine this by looking at the build value, but now we use
    # doOnetimePatcherBump 
    
    if ($doOnetimePatcherBumps) {
        $currentUpdateObj->{'to'} = $version;
        $currentUpdateObj->{'from'} = $oldVersion;
    }

    if ($product eq 'seamonkey') {
      $currentUpdateObj->{'details'} = 'http://www.seamonkey-project.org/releases/' .
                                        $product . $appVersion . '/';
    }
    else {
      $currentUpdateObj->{'details'} = 'http://www.mozilla.com/%locale%/' .
                                        $product . '/' . $appVersion . '/releasenotes/';
    }

    # we disable this for bug 498273, except for ensuring the block is empty
    #if ($useBetaChannel) {
    #    push(@{$RELEASE_CANDIDATE_CHANNELS},'beta');
    #}
    $currentUpdateObj->{'rc'} = {};
    #foreach my $c (@{$RELEASE_CANDIDATE_CHANNELS}) {
    #    $currentUpdateObj->{'rc'}->{$c} = "$build";
    #}

    my $buildStr = 'build' . $build;

    my $partialUpdate = {};
    $partialUpdate->{'url'} = 'http://' . $bouncerServer . '/?product=' .
                              $product. '-' . $version . '-partial-' . 
                              $oldVersion .
                             '&os=%bouncer-platform%&lang=%locale%';

    my $pPath = BumpFilePath(
      oldFilePath => $currentUpdateObj->{'partial'}->{'path'});
    $partialUpdate->{'path'} = catfile($product, 'nightly', $version .
                               '-candidates', $buildStr, $pPath);

    my $pBetatestPath = BumpFilePath(
      oldFilePath => $currentUpdateObj->{'partial'}->{'betatest-url'});
    $partialUpdate->{'betatest-url'} =
     'http://' . $stagingServer. '/pub/mozilla.org/' . $product . 
     '/nightly/' .  $version . '-candidates/' . $buildStr . '/' .
     $pBetatestPath;

    if ($useBetaChannel) {
      my $pBetaPath = BumpFilePath(
        oldFilePath => $currentUpdateObj->{'partial'}->{'beta-url'});
      $partialUpdate->{'beta-url'} =
       'http://' . $ftpServer . '/pub/mozilla.org/' . $product. '/nightly/' . 
        $version . '-candidates/' . $buildStr . '/' . 
        $pBetaPath;
    }
    $currentUpdateObj->{'partial'} = $partialUpdate;

    # Now the same thing, only complete update
    my $completeUpdate = {};
    $completeUpdate->{'url'} = 'http://' . $bouncerServer . '/?product=' .
     $product . '-' . $version . 
     '-complete&os=%bouncer-platform%&lang=%locale%';

    my $cPath = BumpFilePath(
      oldFilePath => $currentUpdateObj->{'complete'}->{'path'});
    $completeUpdate->{'path'} = catfile($product, 'nightly', $version . 
     '-candidates', $buildStr, $cPath);

    my $cBetatestPath = BumpFilePath(
      oldFilePath => $currentUpdateObj->{'complete'}->{'betatest-url'});
    $completeUpdate->{'betatest-url'} = 
     'http://' . $stagingServer . '/pub/mozilla.org/' . $product . 
     '/nightly/' .  $version . '-candidates/' . $buildStr . '/' .
     $cBetatestPath;

    if ($useBetaChannel) {
       my $cBetaPath = BumpFilePath(
         oldFilePath => $currentUpdateObj->{'complete'}->{'beta-url'});
       $completeUpdate->{'beta-url'} = 
        'http://' . $ftpServer . '/pub/mozilla.org/' . $product. '/nightly/' .
        $version . '-candidates/' . $buildStr .  '/' . $cBetaPath;
    }
    $currentUpdateObj->{'complete'} = $completeUpdate;

    # Now, add the new <release> stanza for the release we're working on

    my $releaseObj;
    $appObj->{'release'}->{$version} = $releaseObj = {};

    $releaseObj->{'schema'} = '1';
    $releaseObj->{'version'} = $releaseObj->{'extension-version'} = $appVersion;
    # we disable this for bug 498273, human friendly versions can't be used any more
    #$releaseObj->{'prettyVersion'} = $prettyVersion;

    my $linBuildId;
    my $winBuildId;
    my $macBuildId;

    my $candidateDir = '/pub/mozilla.org/' . $product . '/nightly/' .
                       $version . '-candidates/build' . $build;
    foreach my $os ('linux', 'macosx', 'win32') {
        my $buildID = GetBuildIDFromFTP(os => $os,
                                        releaseDir => $candidateDir,
                                        stagingServer => $stagingServer);
        if ($os eq 'linux') {
            $linBuildId = "$buildID";
        } elsif ($os eq 'macosx') {
            $macBuildId = "$buildID";
        } elsif ($os eq 'win32') {
            $winBuildId = "$buildID";
        } else {
            die("ASSERT: BumpPatcherConfig(): unknown OS $os");
        }
    }

    $releaseObj->{'platforms'} = { 'linux-i686' => $linBuildId,
                                   'win32' => $winBuildId,
                                   'mac' => $macBuildId };

    $releaseObj->{'locales'} = join(' ', sort (keys(%{$localeInfo})));

    my $oldCompleteMarPath =
      $appObj->{'release'}->{$oldVersion}->{'completemarurl'};
    my $completeMarPath = BumpFilePath(oldFilePath => $oldCompleteMarPath);
    $releaseObj->{'completemarurl'} = 
     'http://' . $stagingServer . '/pub/mozilla.org/' . $product. 
     '/nightly/' .  $version . '-candidates/' . $buildStr . '/' .
     $completeMarPath;

    # Compute locale exceptions; 
    # $localeInfo is hash ref of locales -> array of platforms the locale
    # is for.
    #
    # To calculate the exceptions to this rule, create a hash with 
    # all known platforms in it. It's a hash so we can easily delete() keys
    # out of it. Then, we iterate through all the platforms we should build
    # this locale for, and delete them from the list of all known locales.
    #
    # If we should build it for all the loclaes, then this hash should be
    # empty after this process. If it's not, those are the platforms we would
    # __NOT__ build this locale for. But, that doesn't matter; what we're 
    # interested in is that it is such a locale, so we can create a list of
    # platforms we *do* build it for; such information is in the original
    # localeInfo hash, so this is a lot of work to make sure that we do
    # the right thing here.

    $releaseObj->{'exceptions'} = {};

    my %platformMap = GetBouncerToPatcherPlatformMap();
    foreach my $locale (keys(%{$localeInfo})) {
        my $allPlatformsHash = {};
        foreach my $platform (GetBouncerPlatforms()) {
            $allPlatformsHash->{$platform} = 1;
        }

        foreach my $localeSupportedPlatform (@{$localeInfo->{$locale}}) {
            die 'ASSERT: BumpPatcherConfig(): platform in locale, but not in' .
             ' all locales? Invalid platform?' if 
             (!exists($allPlatformsHash->{$localeSupportedPlatform}));

            delete $allPlatformsHash->{$localeSupportedPlatform};
        }
      
        my @supportedPatcherPlatforms = ();
        foreach my $platform (@{$localeInfo->{$locale}}) {
            push(@supportedPatcherPlatforms, $platformMap{$platform});
        }

        if (keys(%{$allPlatformsHash}) > 0) {
            $releaseObj->{'exceptions'}->{$locale} =
             join(', ', sort(@supportedPatcherPlatforms));
        }
    }

    $patcherConfigObj->save_file($patcherConfig);
}


sub RunUnitTests {
    my $workdir = tempdir(CLEANUP => 1);
    my $product = 'firefox';
    my $brand = 'Firefox';
    my $version = '2.0.0.16';
    my $appVersion = '2.0.0.16';
    my $prettyVersion = "2.0.0.16";
    my $oldVersion = '2.0.0.15';
    my $oldOldVersion = '2.0.0.14';
    my $build = '1';
    my $patcherConfig = catfile($workdir, 'moztest-patcher2.cfg');
    my $stagingServer = 'stage.mozilla.org';
    my $ftpServer = 'ftp.mozilla.org';
    my $bouncerServer = 'download.mozilla.org';

    # create shipped-locales
    my $shippedLocales = catfile($workdir, 'shipped-locales');
    open (SHIPPED_LOCALES, ">$shippedLocales");
    print SHIPPED_LOCALES "af\n";
    print SHIPPED_LOCALES "en-US\n";
    print SHIPPED_LOCALES "gu-IN linux win32\n";
    print SHIPPED_LOCALES "ja linux win32\n";
    print SHIPPED_LOCALES "ja-JP-mac osx\n";
    print SHIPPED_LOCALES "uk";
    close(SHIPPED_LOCALES);

    my $localeInfo = {};
    if (not LoadLocaleManifest(localeHashRef => $localeInfo,
                               manifest => $shippedLocales)) {
        die "Could not load locale manifest";
    }

    # We need to create before and after reference patcher configs by hand.
    # The before one will be printed to $patcherConfig and then bumped.
    # When that is complete we will read it in again and compare it
    # against the after reference config. If the two are identical, victory!
    my $beforeConfig = {};
    my $bCurrentUpdate = {};
    my $bReleases = {};
    my $afterConfig = {};
    my $aCurrentUpdate = {};
    my $aReleases = {};
    my $bumpedAfterConfig = {};

    # create the before config
    $bCurrentUpdate->{'beta-dir'} = "beta";
    $bCurrentUpdate->{'channel'} = "beta release";
    $bCurrentUpdate->{'testchannel'} = "betatest releasetest";
    $bCurrentUpdate->{'details'} = "http://www.mozilla.com/%locale%/$product/$oldVersion/releasenotes/";
    $bCurrentUpdate->{'from'} = $oldOldVersion;
    $bCurrentUpdate->{'to'} = $oldVersion;
    $bCurrentUpdate->{'complete'} = {};
    $bCurrentUpdate->{'complete'}->{'beta-url'} = "http://$ftpServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldVersion.%locale%.%platform%.complete.mar";
    $bCurrentUpdate->{'complete'}->{'betatest-url'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldVersion.%locale%.%platform%.complete.mar";
    $bCurrentUpdate->{'complete'}->{'path'} = "$product/nightly/$oldVersion-candidates/build$build/$product-$oldVersion.%locale%.%platform%.complete.mar";
    $bCurrentUpdate->{'complete'}->{'url'} = "http://$bouncerServer/?product=$product-$oldVersion-complete&os=%bouncer-platform%&lang=%locale%";
    $bCurrentUpdate->{'partial'} = {};
    $bCurrentUpdate->{'partial'}->{'beta-url'} = "http://$ftpServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldOldVersion-$oldVersion.%locale%.%platform%.partial.mar";
    $bCurrentUpdate->{'partial'}->{'betatest-url'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldOldVersion-$oldVersion.%locale%.%platform%.partial.mar";
    $bCurrentUpdate->{'partial'}->{'path'} = "$product/nightly/$oldVersion-candidates/build$build/$product-$oldOldVersion-$oldVersion.%locale%.%platform%.partial.mar";
    $bCurrentUpdate->{'partial'}->{'url'} = "http://$bouncerServer/?product=$product-$oldVersion-partial-$oldOldVersion&os=%bouncer-platform%&lang=%locale%";
    $bCurrentUpdate->{'rc'} = {};
    $bCurrentUpdate->{'rc'}->{'DisableCompleteJump'} = $build;
    $bCurrentUpdate->{'rc'}->{'beta'} = $build;
    $bCurrentUpdate->{'rc'}->{'betatest'} = $build;

    $bReleases->{$oldOldVersion} = {};
    $bReleases->{$oldOldVersion}{'completemarurl'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldOldVersion-candidates/build$build/$product-$oldOldVersion.%locale%.%platform%.complete.mar";
    $bReleases->{$oldOldVersion}{'exceptions'} = {};
    $bReleases->{$oldOldVersion}{'exceptions'}{'gu-IN'} = "linux-i686, win32";
    $bReleases->{$oldOldVersion}{'exceptions'}{'ja'} = "linux-i686, win32";
    $bReleases->{$oldOldVersion}{'exceptions'}{'ja-JP-mac'} = "mac";
    $bReleases->{$oldOldVersion}{'extension-version'} = $oldOldVersion;
    $bReleases->{$oldOldVersion}{'locales'} = 'af en-US gu-IN ja ja-JP-mac uk';
    $bReleases->{$oldOldVersion}{'prettyVersion'} = $oldOldVersion;
    $bReleases->{$oldOldVersion}{'schema'} = '1';
    $bReleases->{$oldOldVersion}{'version'} = $oldOldVersion;
    $bReleases->{$oldOldVersion}{'platforms'} = {};
    $bReleases->{$oldOldVersion}{'platforms'}{'linux-i686'} = '2008070712';
    $bReleases->{$oldOldVersion}{'platforms'}{'win32'} = '2008070712';
    $bReleases->{$oldOldVersion}{'platforms'}{'mac'} = '2008070712';

    $bReleases->{$oldVersion} = {};
    $bReleases->{$oldVersion}{'completemarurl'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldVersion.%locale%.%platform%.complete.mar";
    $bReleases->{$oldVersion}{'exceptions'} = {};
    $bReleases->{$oldVersion}{'exceptions'}{'gu-IN'} = "linux-i686, win32";
    $bReleases->{$oldVersion}{'exceptions'}{'ja'} = "linux-i686, win32";
    $bReleases->{$oldVersion}{'exceptions'}{'ja-JP-mac'} = "mac";
    $bReleases->{$oldVersion}{'extension-version'} = $oldVersion;
    $bReleases->{$oldVersion}{'locales'} = 'af en-US gu-IN ja ja-JP-mac uk';
    $bReleases->{$oldVersion}{'prettyVersion'} = $oldVersion;
    $bReleases->{$oldVersion}{'schema'} = '1';
    $bReleases->{$oldVersion}{'version'} = $oldVersion;
    $bReleases->{$oldVersion}{'platforms'} = {};
    $bReleases->{$oldVersion}{'platforms'}{'linux-i686'} = '2008070824';
    $bReleases->{$oldVersion}{'platforms'}{'win32'} = '2008070824';
    $bReleases->{$oldVersion}{'platforms'}{'mac'} = '2008070824';

    $beforeConfig->{'app'} = {};
    $beforeConfig->{'app'}->{$brand} = {};
    $beforeConfig->{'app'}->{$brand}->{'current-update'} = $bCurrentUpdate;
    $beforeConfig->{'app'}->{$brand}->{'release'} = $bReleases;

    # now create the after config
    $aCurrentUpdate->{'beta-dir'} = "beta";
    $aCurrentUpdate->{'channel'} = "beta release";
    $aCurrentUpdate->{'testchannel'} = "betatest releasetest";
    $aCurrentUpdate->{'details'} = "http://www.mozilla.com/%locale%/$product/$version/releasenotes/";
    $aCurrentUpdate->{'from'} = $oldVersion;
    $aCurrentUpdate->{'to'} = $version;
    $aCurrentUpdate->{'complete'} = {};
    $aCurrentUpdate->{'complete'}->{'beta-url'} = "http://$ftpServer/pub/mozilla.org/$product/nightly/$version-candidates/build$build/$product-$version.%locale%.%platform%.complete.mar";
    $aCurrentUpdate->{'complete'}->{'betatest-url'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$version-candidates/build$build/$product-$version.%locale%.%platform%.complete.mar";
    $aCurrentUpdate->{'complete'}->{'path'} = "$product/nightly/$version-candidates/build$build/$product-$version.%locale%.%platform%.complete.mar";
    $aCurrentUpdate->{'complete'}->{'url'} = "http://$bouncerServer/?product=$product-$version-complete&os=%bouncer-platform%&lang=%locale%";
    $aCurrentUpdate->{'partial'} = {};
    $aCurrentUpdate->{'partial'}->{'beta-url'} = "http://$ftpServer/pub/mozilla.org/$product/nightly/$version-candidates/build$build/$product-$oldVersion-$version.%locale%.%platform%.partial.mar";
    $aCurrentUpdate->{'partial'}->{'betatest-url'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$version-candidates/build$build/$product-$oldVersion-$version.%locale%.%platform%.partial.mar";
    $aCurrentUpdate->{'partial'}->{'path'} = "$product/nightly/$version-candidates/build$build/$product-$oldVersion-$version.%locale%.%platform%.partial.mar";
    $aCurrentUpdate->{'partial'}->{'url'} = "http://$bouncerServer/?product=$product-$version-partial-$oldVersion&os=%bouncer-platform%&lang=%locale%";
    $aCurrentUpdate->{'rc'} = {};
    $aCurrentUpdate->{'rc'}->{'DisableCompleteJump'} = $build;
    $aCurrentUpdate->{'rc'}->{'beta'} = $build;
    $aCurrentUpdate->{'rc'}->{'betatest'} = $build;

    $aReleases->{$oldOldVersion} = {};
    $aReleases->{$oldOldVersion}{'completemarurl'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldOldVersion-candidates/build$build/$product-$oldOldVersion.%locale%.%platform%.complete.mar";
    $aReleases->{$oldOldVersion}{'exceptions'} = {};
    $aReleases->{$oldOldVersion}{'exceptions'}{'gu-IN'} = "linux-i686, win32";
    $aReleases->{$oldOldVersion}{'exceptions'}{'ja'} = "linux-i686, win32";
    $aReleases->{$oldOldVersion}{'exceptions'}{'ja-JP-mac'} = "mac";
    $aReleases->{$oldOldVersion}{'extension-version'} = $oldOldVersion;
    $aReleases->{$oldOldVersion}{'locales'} = 'af en-US gu-IN ja ja-JP-mac uk';
    $aReleases->{$oldOldVersion}{'prettyVersion'} = $oldOldVersion;
    $aReleases->{$oldOldVersion}{'schema'} = '1';
    $aReleases->{$oldOldVersion}{'version'} = $oldOldVersion;
    $aReleases->{$oldOldVersion}{'platforms'} = {};
    $aReleases->{$oldOldVersion}{'platforms'}{'linux-i686'} = '2008070712';
    $aReleases->{$oldOldVersion}{'platforms'}{'win32'} = '2008070712';
    $aReleases->{$oldOldVersion}{'platforms'}{'mac'} = '2008070712';

    $aReleases->{$oldVersion} = {};
    $aReleases->{$oldVersion}{'completemarurl'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$oldVersion-candidates/build$build/$product-$oldVersion.%locale%.%platform%.complete.mar";
    $aReleases->{$oldVersion}{'exceptions'} = {};
    $aReleases->{$oldVersion}{'exceptions'}{'gu-IN'} = "linux-i686, win32";
    $aReleases->{$oldVersion}{'exceptions'}{'ja'} = "linux-i686, win32";
    $aReleases->{$oldVersion}{'exceptions'}{'ja-JP-mac'} = "mac";
    $aReleases->{$oldVersion}{'extension-version'} = $oldVersion;
    $aReleases->{$oldVersion}{'locales'} = 'af en-US gu-IN ja ja-JP-mac uk';
    $aReleases->{$oldVersion}{'prettyVersion'} = $oldVersion;
    $aReleases->{$oldVersion}{'schema'} = '1';
    $aReleases->{$oldVersion}{'version'} = $oldVersion;
    $aReleases->{$oldVersion}{'platforms'} = {};
    $aReleases->{$oldVersion}{'platforms'}{'linux-i686'} = '2008070824';
    $aReleases->{$oldVersion}{'platforms'}{'win32'} = '2008070824';
    $aReleases->{$oldVersion}{'platforms'}{'mac'} = '2008070824';

    $aReleases->{$version} = {};
    $aReleases->{$version}{'completemarurl'} = "http://$stagingServer/pub/mozilla.org/$product/nightly/$version-candidates/build$build/$product-$version.%locale%.%platform%.complete.mar";
    $aReleases->{$version}{'exceptions'} = {};
    $aReleases->{$version}{'exceptions'}{'gu-IN'} = "linux-i686, win32";
    $aReleases->{$version}{'exceptions'}{'ja'} = "linux-i686, win32";
    $aReleases->{$version}{'exceptions'}{'ja-JP-mac'} = "mac";
    $aReleases->{$version}{'extension-version'} = $version;
    $aReleases->{$version}{'locales'} = 'af en-US gu-IN ja ja-JP-mac uk';
    $aReleases->{$version}{'prettyVersion'} = $version;
    $aReleases->{$version}{'schema'} = '1';
    $aReleases->{$version}{'version'} = $version;
    $aReleases->{$version}{'platforms'} = {};
    $aReleases->{$version}{'platforms'}{'linux-i686'} = '2008070204';
    $aReleases->{$version}{'platforms'}{'win32'} = '2008070205';
    $aReleases->{$version}{'platforms'}{'mac'} = '2008070205';

    $afterConfig->{'app'} = {};
    $afterConfig->{'app'}->{$brand} = {};
    $afterConfig->{'app'}->{$brand}->{'current-update'} = $aCurrentUpdate;
    $afterConfig->{'app'}->{$brand}->{'release'} = $aReleases;
    # The patcher config we're bumping does not contain any past-update lines.
    # Patcher doesn't deal with this well - it will insert an empty
    # past-update line along with the valid one. Rather than fix this bug we'll
    # just test patcher's existing behaviour.
    $afterConfig->{'app'}->{$brand}->{'past-update'} = [
        "",
        "$oldOldVersion $oldVersion betatest releasetest beta release"
    ];

    # Now it's time to write out the before config and bump it
    my $beforeObj = new Config::General($beforeConfig);
    $beforeObj->save_file($patcherConfig);

    # We need to build up the global config object before calling
    # BumpPatcherConfig
    $config{'product'} = $product;
    $config{'brand'} = $brand;
    $config{'version'} = $version;
    $config{'old-version'} = $oldVersion;
    $config{'app-version'} = $appVersion;
    $config{'build-number'} = $build;
    $config{'patcher-config'} = $patcherConfig;
    $config{'staging-server'} = $stagingServer;
    $config{'ftp-server'} = $ftpServer;
    $config{'bouncer-server'} = $bouncerServer;
    $config{'use-beta-channel'} = 1;
    $config{'shipped-locales'} = $shippedLocales;
    BumpPatcherConfig();

    # Now, read the newly bumped patcher config file back in
    my $bumpedConfigObj = new Config::General(-ConfigFile => $patcherConfig);
    my %bumpedConfig = $bumpedConfigObj->getall;

    if (deeply_equal(\%bumpedConfig, $afterConfig)) {
        print "PASS\n";
        exit(0);
    } else {
        print "FAIL\n";
        $bumpedConfigObj->save_file("bumped-patcher.cfg");
        print "Bumped patcher config written to bumped-patcher.cfg\n";
        my $afterConfigObj = new Config::General($afterConfig);
        $afterConfigObj->save_file("reference-patcher.cfg");
        print "Reference patcher config written to reference-patcher.cfg\n";
        print "Please examine them to debug the problem.\n";
        exit(1);
    }
}


# Taken from http://www.perlmonks.org/?node_id=121559
sub deeply_equal {
  my ( $a_ref, $b_ref ) = @_;
    
  local $Storable::canonical = 1;
  return Storable::freeze( $a_ref ) eq Storable::freeze( $b_ref );
}
