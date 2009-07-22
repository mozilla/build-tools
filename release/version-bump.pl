#!/usr/bin/perl -w
use strict;

use File::Copy qw(move);
use File::Spec::Functions;
use Getopt::Long;

$|++;

my %config;

ProcessArgs();
Bump();

sub ProcessArgs {
    GetOptions(
        \%config,
        "workdir|w=s", "release-tag|t=s", "app|a=s", "version|v=s",
        "milestone|m=s", "help|h"
    );

    if ($config{'help'}) {
        print "Usage: version-bump.pl -w dir -t tag -a app -v version\n";
        print "        list of files to bump\n";
        print "  -w The directory containing files to bump.\n";
        print "     Must be the root of a mozilla tree.\n";
        print "  -t The current release tag (eg. FIREFOX_3_1a1_RELEASE).\n";
        print "  -a The app name (eg. browser, mail, etc.).\n";
        print "  -v The current version of the app (eg. 3.1a1, 3.0.1, etc.).\n";
        print "  -m The current milestone of the platform (eg, 1.8.1.1).\n";
        print "     Only necessary if milestone.txt is being bumped.\n";
        print "  -h This usage message.\n";
        print " Additional arguments are interpreted as a list of files to be ";
        print " bumped.\n";
        exit(0);
    }

    my $error = 0;

    if (! -e $config{'workdir'}) {
        print "workdir must exist.\n";
        $error = 1;
    }
    if (! defined $config{'release-tag'}) {
        print "release-tag must be defined.\n";
        $error = 1;
    }
    if (! defined $config{'app'}) {
        print "app must be defined.\n";
        $error = 1;
    }
    if (! defined $config{'version'}) {
        print "version must be defined.\n";
        $error = 1;
    }
    if (! defined $config{'milestone'}) {
        print "milestone must be defined.\n";
        $error = 1;
    }
    if ($error) {
        exit(1);
    }

    $config{'bumpFiles'} = \@ARGV;
}

sub Bump {
    my $workDir = $config{'workdir'};
    my $releaseTag = $config{'release-tag'};
    my $appName = $config{'app'};
    my $appVersion = $config{'version'};
    my $milestone = $config{'milestone'};
    my @bumpFiles = @{$config{'bumpFiles'}};
    
    my $moduleVer = catfile($appName, 'app', 'module.ver');
    my $versionTxt = catfile($appName, 'config', 'version.*\.txt');
    my $milestoneTxt = catfile('config', 'milestone.txt');
    my $jsMilestoneTxt = catfile('js', 'src', 'config', 'milestone.txt');
    
    foreach my $fileName (@bumpFiles) {
        my $found = 0;
             
        my $file = catfile($workDir, $fileName);
        
        my $bumpVersion = undef;
        my $preVersion = undef;
        my %searchReplace = ();
    
        # Order or searching for these values is not preserved, so make
        # sure that the order replacement happens does not matter.
        if ($fileName eq 'client.mk') {
            %searchReplace = (
             # MOZ_CO_TAG is commented out on some branches, make sure to
             # accommodate that
             '^#?MOZ_CO_TAG\s+=.+$' =>
              'MOZ_CO_TAG           = ' . $releaseTag,
             '^NSPR_CO_TAG\s+=\s+\w*' =>
              'NSPR_CO_TAG          = ' . $releaseTag,
             '^NSS_CO_TAG\s+=\s+\w*' =>
              'NSS_CO_TAG           = ' . $releaseTag,
             '^LOCALES_CO_TAG\s+=.*$' =>
              'LOCALES_CO_TAG       = ' . $releaseTag,
             '^LDAPCSDK_CO_TAG\s+=.*$' =>
              'LDAPCSDK_CO_TAG      = ' . $releaseTag);
        } elsif ($fileName eq $moduleVer) {
            $preVersion = $appVersion . 'pre';
            %searchReplace = ('^WIN32_MODULE_PRODUCTVERSION_STRING=' .
             $preVersion . '$' => 'WIN32_MODULE_PRODUCTVERSION_STRING=' .
             $appVersion);
        } elsif ($fileName =~ /$versionTxt/) {
            $preVersion = $appVersion . 'pre';
            %searchReplace = ('^' . $preVersion . '$' => $appVersion);
        } elsif ($fileName eq $milestoneTxt || $fileName eq $jsMilestoneTxt) {
            $preVersion = $milestone . 'pre';
            %searchReplace = ('^' . $preVersion . '$' => $milestone);
        } else {
            die("ASSERT: do not know how to bump file $fileName");
        }
    
        if (scalar(keys(%searchReplace)) <= 0) {
            die("ASSERT: no search/replace to perform");
        }
    
        open(INFILE,  "< $file") or die("Could not open $file: $!");
        open(OUTFILE, "> $file.tmp") or die("Could not open $file.tmp: $!");
        while(<INFILE>) {
            foreach my $search (keys(%searchReplace)) {
                my $replace = $searchReplace{$search};
                if($_ =~ /$search/) {
                    print "$file: $search found\n";
                    $found = 1;
                    $_ =~ s/$search/$replace/;
                    print "$file: $search replaced with $replace\n";
                }
            }
    
            print OUTFILE $_;
        }
        close INFILE or die("Could not close $file: $!");
        close OUTFILE or die("Could not close $file.tmp: $!");
        if (not $found) {
            die("None of " . join(' ', keys(%searchReplace)) .
             " found in file $file: $!");
        }
    
        if (not move("$file.tmp",
                     "$file")) {
            die("Cannot rename $file.tmp to $file: $!");
        }
    }
}
