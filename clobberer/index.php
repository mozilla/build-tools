<!---
This is a web interface that allows developers to clobber mozilla-central,
actionmonkey, and tracemonkey builds.

This script simply updates a database that Buildbot reads from at the start of
every build. The BuildStep that does this is here:
http://mxr.mozilla.org/mozilla/source/tools/buildbotcustom/steps/misc.py#167
-->

<?php
$CLOBBERER_DB = '/var/www/html/build/clobberer/clobberer.db';

$dbh = new PDO("sqlite:$CLOBBERER_DB");
if (!$dbh) {
  header('HTTP/1.0 500 Internal Server Error');
  print("<h1>Error: couldn't connect</h1>");
  print($error);
  exit(0);
}

$q = $dbh->query('SELECT count(*) FROM sqlite_master WHERE NAME="CLOBBERS"');
$exists = $q->fetch(PDO::FETCH_NUM);
if (!$exists[0]) {
  $dbh->exec('CREATE TABLE CLOBBERS (short_name VARCHAR(30),'
            .'long_name VARCHAR(50),'
            .'lastclobber VARCHAR(30),'
            .'clobberer VARCHAR(50))');
}

function e($str)
{
  global $dbh;
  return $dbh->quote($str);
}

if ($_POST['form_submitted']) {
  $clobbers = array();
  foreach ($_POST as $k => $v) {
    $t = explode('-', $k, 2);
    if ($t[0] == 'clobber') {
      array_push($clobbers, $t[1]);
    }
  }
  foreach ($clobbers as $c) {
    $dbh->exec('UPDATE CLOBBERS SET lastclobber = DATETIME("NOW"), clobberer = ' . e($_SERVER['REMOTE_USER']) . ' WHERE short_name = ' . e($c));
  }
}

$tree = $_GET['tree'];
if (!$tree) {
  $alltrees = $dbh->query('SELECT short_name, long_name, lastclobber, clobberer FROM CLOBBERS ORDER BY long_name ASC');
?>
<head>
<title>Mozilla Buildbot Clobberer</title>
</head>
<table border="1" cellspacing="0" cellpadding="1">
 <form action="<?php print htmlspecialchars($_SERVER['REQUEST_URI']);?>" method="POST">
 <thead>
  <tr><td>Name <td>Last Forced Clobber <td>Clobber?<td>Clobbered By
 <tbody>
<?php
  while ($r = $alltrees->fetch(PDO::FETCH_ASSOC)) {
    print '<tr><td>'.htmlspecialchars($r['long_name']).'<td>'.htmlspecialchars($r['lastclobber']);
    print '<td><input type="checkbox" name="clobber-'.htmlspecialchars($r['short_name']).'">';
    print '<td>'.htmlspecialchars($r['clobberer']);
  }
?>
</table>
<input type="hidden" name="form_submitted" value="true">
<input type="submit" value="Clobber now">
</form>
<?php
  exit(0);
}

$s = $dbh->query('SELECT lastclobber FROM CLOBBERS WHERE long_name = '.e($tree));
$r = $s->fetch(PDO::FETCH_ASSOC);
if (!$r) {
  header('HTTP/1.x 500 Internal Server Error');
  print "Couldn't get last clobber time for $tree";
}
else {
  header('HTTP/1.x 200 OK');
  print $r['lastclobber'];
}
?>
