package Release::Versions;

use strict;

use base qw(Exporter);
our @EXPORT_OK = qw(GetPrettyVersion);

sub GetPrettyVersion {
    my %args = @_;
    my $prettyVersion = $args{'version'};

    $prettyVersion =~ s/a([0-9]+)$/ Alpha $1/;
    $prettyVersion =~ s/b([0-9]+)$/ Beta $1/;
    $prettyVersion =~ s/rc([0-9]+)$/ RC $1/;

    return $prettyVersion;
}
