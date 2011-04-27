<?php
$an_hour_ago = time() + 3600;
$builddir = urldecode($_GET['builddir']);
print "$builddir:$an_hour_ago:clobber_always\n";
?>
