<?php

include("clobberer_creds.php");

// disallow unless the correct token is given
if ($_GET['pass'] != $CLEANUP_PASSWORD) {
  header('HTTP/1.0 500 Internal Server Error');
  echo "no.";
  exit;
}

$dbh = new PDO($CLOBBERER_DSN, $CLOBBERER_USERNAME,
        $CLOBBERER_PASSWORD, $CLOBBERER_PDO_OPTIONS);
if (!$dbh) {
  header('HTTP/1.0 500 Internal Server Error');
  print("<h1>Error: couldn't connect</h1>");
  print($error);
  exit(0);
}

header("Content-type: text/plain");
if (substr($CLOBBERER_DSN, 0, 5) == 'mysql') {
	$q = "delete from builds where last_build_time < unix_timestamp(adddate(now(), interval -21 day)) and buildername not like 'rel%'";
	echo "$q\n";
	$dbh->exec($q) === false and die(print_r($dbh->errorInfo(), TRUE));

	$q = "delete from clobber_times where lastclobber < unix_timestamp(adddate(now(), interval -21 day))";
	echo "$q\n";
	$dbh->exec($q) === false and die(print_r($dbh->errorInfo(), TRUE));

	// optimize table?  Only reclaims table space, so probably not helpful..
} else {
	// sqlite
	$q = "delete from builds where last_build_time < strftime('%s', 'now', '-21 days') and buildername not like 'rel%'";
	echo "$q\n";
	$dbh->exec($q) === false and die(print_r($dbh->errorInfo(), TRUE));

	$q = "delete from clobber_times where lastclobber < strftime('%s', 'now', '-21 days')";
	echo "$q\n";
	$dbh->exec($q) === false and die(print_r($dbh->errorInfo(), TRUE));

	$q = "vacuum";
	echo "$q\n";
	$dbh->exec($q) === false and die(print_r($dbh->errorInfo(), TRUE));
}

echo "OK";
