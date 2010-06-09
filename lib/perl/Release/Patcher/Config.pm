package Release::Patcher::Config;

use strict;

use MozBuild::Util qw(GetBuildIDFromFTP);
use Bootstrap::Util qw(GetBouncerToPatcherPlatformMap GetBouncerPlatforms GetBuildbotToFTPPlatformMap);

use base qw(Exporter);
our @EXPORT_OK = qw(GetProductDetails GetReleaseBlock BumpFilePath);

sub GetProductDetails {
    my %args = @_;
    my $product = $args{'product'};
    my $appVersion = $args{'appVersion'};
    my $updateType = $args{'updateType'};

    my $endOfUrl = '/releasenotes/';
    if ($product eq 'seamonkey') {
        $endOfUrl = '/';
    }
    elsif ($updateType eq 'major') {
        $endOfUrl = '/details/index.html';
    }

    if ($product eq 'seamonkey') {
        return 'http://www.seamonkey-project.org/releases/' . $product .
               $appVersion . $endOfUrl;
    }
    elsif ($product eq 'thunderbird') {
        return 'http://www.mozillamessaging.com/%locale%/' . $product . '/' .
               $appVersion . $endOfUrl;
    }
    else {
        return 'http://www.mozilla.com/%locale%/' . $product . '/' .
               $appVersion . $endOfUrl;
    }
}

sub GetReleaseBlock {
    my %args = @_;
    my $version = $args{'version'};
    my $appVersion = $args{'appVersion'};
    my $prettyVersion = $args{'prettyVersion'};
    my $product = $args{'product'};
    my $buildStr = $args{'buildstr'};
    my $stagingServer = $args{'stagingServer'};
    my $localeInfo = $args{'localeInfo'};
    my $platforms = $args{'platforms'};

    my $releaseBlock = {};
    $releaseBlock->{'schema'} = '1';
    $releaseBlock->{'version'} = $appVersion;
    $releaseBlock->{'extension-version'} = $appVersion;
    $releaseBlock->{'prettyVersion'} = $prettyVersion;

    my $candidateDir = '/pub/mozilla.org/' . $product . '/nightly/' .
      $version . '-candidates/' . $buildStr;

    $releaseBlock->{'platforms'} = {};
    my %platformFTPMap = GetBuildbotToFTPPlatformMap();
    foreach my $os (@$platforms){
        my $buildID = GetBuildIDFromFTP(os => $os,
                                        releaseDir => $candidateDir,
                                        stagingServer => $stagingServer);
        if (exists($platformFTPMap{$os})){
            my $ftp_platform = $platformFTPMap{$os};
            $releaseBlock->{'platforms'}->{$ftp_platform} = $buildID;
        } else {
            die("ASSERT: GetReleaseBlock(): unknown OS $os");
        }
    }
    
    $releaseBlock->{'locales'} = join(' ', sort (keys(%{$localeInfo})));
    
    $releaseBlock->{'completemarurl'} = 'http://' . $stagingServer .
      '/pub/mozilla.org/' . $product . '/nightly/' . $version . '-candidates/' .
      $buildStr . '/update/%platform%/%locale%/' . $product . '-' . $version .
      '.complete.mar';

    $releaseBlock->{'exceptions'} = {};

    my %platformMap = GetBouncerToPatcherPlatformMap();
    foreach my $locale (keys(%{$localeInfo})) {
        my $allPlatformsHash = {};
        foreach my $platform (GetBouncerPlatforms()) {
            $allPlatformsHash->{$platform} = 1;
        }

        foreach my $localeSupportedPlatform (@{$localeInfo->{$locale}}) {
            die 'ASSERT: GetReleaseBlock(): platform in locale, but not in' .
             ' all locales? Invalid platform?' if
             (!exists($allPlatformsHash->{$localeSupportedPlatform}));

            delete $allPlatformsHash->{$localeSupportedPlatform};
        }

        my @supportedPatcherPlatforms = ();
        foreach my $platform (@{$localeInfo->{$locale}}) {
            push(@supportedPatcherPlatforms, $platformMap{$platform});
        }

        if (keys(%{$allPlatformsHash}) > 0) {
            $releaseBlock->{'exceptions'}->{$locale} =
             join(', ', sort(@supportedPatcherPlatforms));
        }
    }

    return $releaseBlock;
}

sub BumpFilePath {
    my %args = @_;
    my $oldFilePath = $args{'oldFilePath'};
    my $product = $args{'product'};
    my $version = $args{'version'};
    my $oldVersion = $args{'old-version'};

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

1;
