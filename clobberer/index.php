<?php
/*
This is a web interface that allows developers to clobber buildbot
builds on a per-slave/per-builder basis.

This script simply updates a database that Buildbot reads from at the start of
every build.
http://hg.mozilla.org/build/buildbotcustom/file/default/process/factory.py
*/

$CLOBBERER_DB = '/var/www/html/build/stage-clobberer/db/clobberer.db';
//$CLOBBERER_DB = '/var/www/html/build/clobberer/clobberer.db';

$dbh = new PDO("sqlite:$CLOBBERER_DB");
if (!$dbh) {
  header('HTTP/1.0 500 Internal Server Error');
  print("<h1>Error: couldn't connect</h1>");
  print($error);
  exit(0);
}

$q = $dbh->query('SELECT count(*) FROM sqlite_master WHERE NAME="clobber_times"');
$exists = $q->fetch(PDO::FETCH_NUM);
if (!$exists or !$exists[0]) {
  $res = $dbh->exec('CREATE TABLE clobber_times ('
                   .'id INTEGER PRIMARY KEY AUTOINCREMENT,'
                   .'branch VARCHAR(50),'
                   .'builder VARCHAR(50),'
                   .'slave VARCHAR(30),'
                   .'lastclobber VARCHAR(30),'
                   .'clobberer VARCHAR(50))');
  if ($res === FALSE) {
    die(print_r($dbh->errorInfo(), TRUE));
  }
  chmod($CLOBBERER_DB, 0660);
}

function b64_encode($s)
{
  return rtrim(base64_encode($s), "=");
}

function e($str)
{
  global $dbh;
  return $dbh->quote($str);
}

//
// Handle form submission
//
if ($_POST['form_submitted']) {
  $clobbers = array();
  $slaves = array();
  foreach ($_POST as $k => $v) {
    $t = explode('-', $k, 2);
    // We only care about slave-<$row_id>
    // This corresponds to a row that specifies which branch/builder/slave to clobber
    if ($t[0] == 'slave') {
      $row_id = e($t[1]);
      $user = e($_SERVER['REMOTE_USER']);
      $dbh->exec("UPDATE clobber_times SET lastclobber = DATETIME(\"NOW\"), clobberer = $user WHERE id = $row_id");
    }
  }
  // Redirect the user to the main page
  // This prevents accidentally resubmitting the form if the user reloads the 
  // page
  header("Location: " . $_SERVER['REQUEST_URI']);
}

$builder = $_GET['builder'];
$slave = $_GET['slave'];
$branch = $_GET['branch'];
// Show the administration page if no clobber time is being queried
if (!$builder) {
?>
<html>
<head>
<title>Mozilla Buildbot Clobberer</title>
<link rel="stylesheet" href="clobberer.css" type="text/css" />
<script src="jquery.min.js" language="javascript"></script>
<script language="javascript">
function toggleall(node, klass)
{
  if (klass) {
    $("." + klass).attr("checked", node.checked);
  }
  var node_classes = $(node).attr("class").split(" ");
  if (!node.checked) {
    // If we just unchecked a node, then uncheck the parents too
    for (var i = 0; i < node_classes.length; ++i) {
      if (node_classes[i]) {
        $("#" + node_classes[i]).attr("checked", false);
      }
    }
  } else {
    // If we just checked a node, then possibly check the parents if all
    // children are checked
    var done = false;
    while (!done) {
      done = true;
      for (var i = 0; i < node_classes.length; ++i) {
        if (node_classes[i]) {
          // If none of this class is unchecked, then we can check the parent
          if ($("." + node_classes[i] + ":not(:checked)").length == 0) {
            var p = $("#" + node_classes[i]);
            if (p && !p.attr("checked")) {
              p.attr("checked", true);
              // Loop through again if we just set our parent to checked
              done = false;
            }
          }
        }
      }
    }
  }
}
</script>
</head>
<body>
<p>This page is used for clobbering buildbot-based builds.</p>
<p>Please read
<a href="https://wiki.mozilla.org/Build:ClobberingATinderbox">Build:ClobberingATinderbox</a>
and/or <a href="https://wiki.mozilla.org/Clobbering_the_Tree">Clobbering the Tree</a>
for more information about what this page is for, and how to use it.</p>
<form method="POST">
<table border="1" cellspacing="0" cellpadding="1">
 <thead>
  <tr><td>Branch</td><td>Builder Name</td><td>Slaves</td><td>Last clobbered</td></tr>
 </thead>
 <tbody>
<?php
  $allbuilders = $dbh->query('SELECT * FROM clobber_times ORDER BY branch ASC, builder ASC');
  if ($allbuilders) {
    $last_branch = null;
    $last_builder = null;
    // First pass: count the number of rows for each branch / builder so we can 
    // set the 'rowspan' attribute
    $rows_per_branch = array();
    $rows_per_builder = array();
    $rows = array();
    while ($r = $allbuilders->fetch(PDO::FETCH_ASSOC)) {
      $rows[] = $r;
      $builder = $r['builder'];
      $branch = $r['branch'];
      if (!array_key_exists($builder, $rows_per_builder)) {
        $rows_per_builder[$builder] = 1;
      } else {
        $rows_per_builder[$builder] += 1;
      }
      if (!array_key_exists($branch, $rows_per_branch)) {
        $rows_per_branch[$branch] = 1;
      } else {
        $rows_per_branch[$branch] += 1;
      }
    }
    // Sort the results
    function sort_func($r1, $r2) {
      $c1 = strnatcmp($r1['branch'], $r2['branch']);
      if ($c1 != 0) {
        return $c1;
      }
      $c2 = strnatcmp($r1['builder'], $r2['builder']);
      if ($c2 != 0) {
        return $c2;
      }
      return strnatcmp($r1['slave'], $r2['slave']);
    }
    usort($rows, sort_func);
    // Second pass we output the HTML
    foreach ($rows as $r) {
      print "<tr>";
      if ($last_branch != $r['branch']) {
        $branch_id = b64_encode($r['branch']);
        $rowspan = $rows_per_branch[$r['branch']];
        print "<td rowspan=\"$rowspan\">";
        print "<input type=\"checkbox\" id=\"$branch_id\" onchange=\"toggleall(this, &quot;$branch_id&quot;)\" />";
        print htmlspecialchars($r['branch']) . "</td>\n";
      }
      if ($last_builder != $r['builder']) {
        $rowspan = $rows_per_builder[$r['builder']];
        $builder_id = b64_encode($r['builder']);
        $classes = b64_encode($r['branch']);
        print "<td rowspan=\"$rowspan\"><input type=\"checkbox\" id=\"$builder_id\" class=\"$classes\" onchange=\"toggleall(this, &quot;$builder_id&quot;)\" />";
        print htmlspecialchars($r['builder']) . "</td>\n";
      }
      $classes = b64_encode($r['builder']) . " " . b64_encode($r['branch']);
      $name = "slave-" . $r['id'];
      print "<td><input type=\"checkbox\" name=\"$name\" class=\"$classes\" onchange=\"toggleall(this)\" />";
      print htmlspecialchars($r['slave']) . "</td>\n";
      if ($r['lastclobber']) {
        print "<td>" . htmlspecialchars($r['lastclobber']) . "(UTC) by " . htmlspecialchars($r['clobberer']) . "</td>\n";
      } else {
        print "<td></td>\n";
      }
      print "</tr>\n";
      $last_branch = $r['branch'];
      $last_builder = $r['builder'];
    }
  } else {
    print "<tr><td colspan=\"9\">No data</td></tr>\n";
  }
?>
 </tbody>
</table>
<input type="hidden" name="form_submitted" value="true">
<input type="submit" value="Clobber now">
</form>
</body>
</html>
<?php
  exit(0);
}

// Handle requests from slaves asking about their last clobber date
$e_builder = e($builder);
$e_slave = e($slave);
$e_branch = e($branch);
$s = $dbh->query("SELECT id, lastclobber FROM clobber_times WHERE builder = $e_builder AND slave = $e_slave AND branch = $e_branch");
$r = $s->fetch(PDO::FETCH_ASSOC);
if (!$r) {
  // If this branch/builder/slave combination doesn't yet exist in the 
  // database, then insert it
  $res = $dbh->exec("INSERT INTO clobber_times (branch, builder, slave) VALUES ($e_branch, $e_builder, $e_slave)");
  if ($res === false) {
    header("HTTP/1.x 500 Internal Server Error");
    print "Couldn't insert row<br/>\n";
    die(print_r($dbh->errorInfo(), TRUE));
  }
}
else {
  print $r['lastclobber'];
}
?>
