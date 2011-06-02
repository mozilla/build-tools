<?php
$the_future = time() + 3600;
$builddir = urldecode($_GET['builddir']);
print "$builddir:$the_future:clobber_always\n";
?>
