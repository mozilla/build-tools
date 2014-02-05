var template_base_link="https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=nobody@mozilla.org&bug_severity=normal&bug_status=NEW&component=Buildduty&form_name=enter_bug&priority=P3&product=Release%20Engineering&status_whiteboard=[buildduty][buildslaves][capacity]";

var b2008_build_re   = /b-2008-ix/;
var lion_build_re    = /lion-r5|mac64/;
var linux_build_re   = /linux-ix|centos5-32/;
var linux64_build_re = /linux64|centos6|centos5-64/;
var w32_build_re     = /mw32/;
var w64_build_re     = /w64/;

var leopard_test_re  = /leopard/;
var lion_test_re     = /lion/;
var linux_test_re    = /-fed-|linux32/;
var linux64_test_re  = /fed64/;
var mavericks_test_re  = /mavericks/;
var mtnlion_test_re  = /mtnlion/;
var snow_test_re     = /snow/;
var tegra_test_re    = /tegra/;
var panda_test_re    = /panda/;
var w7_test_re       = /-w7-|w732/;
var w764_test_re     = /w764/;
var w864_test_re     = /w864/;
var xp_test_re       = /xp/;

var known_bugs = {};
var images = new Array();

function getTemplateLinkForSlavename(slavename) {
  platform = "";
  opsys="";
  switch (true) {
    case tegra_test_re.test(slavename):
      platform = 'ARM';
      opsys = 'Android';
      break;
    case panda_test_re.test(slavename):
      platform = 'ARM';
      opsys = 'Android';
      break;
    case w7_test_re.test(slavename):
      platform = 'x86';
      opsys = 'Windows%207';
      break;
    case xp_test_re.test(slavename):
      platform = 'x86';
      opsys = 'Windows%20XP';
      break;
    case leopard_test_re.test(slavename):
    case snow_test_re.test(slavename):
      platform = 'x86';
      opsys = 'Mac%20OS%20X';
      break;
    case lion_build_re.test(slavename):
    case lion_test_re.test(slavename):
    case mtnlion_test_re.test(slavename):
    case mavericks_test_re.test(slavename):
      platform = 'x86_64';
      opsys = 'Mac%20OS%20X';
      break;
    case linux_build_re.test(slavename):
    case linux_test_re.test(slavename):
      platform = 'x86';
      opsys = 'Linux';
      break;
    case linux64_build_re.test(slavename):
    case linux64_test_re.test(slavename):
      platform = 'x86_64';
      opsys = 'Linux';
      break;
    case w32_build_re.test(slavename):
      platform = 'x86';
      opsys = 'Windows%20Server%202003';
      break;
    case w64_build_re.test(slavename):
    case b2008_build_re.test(slavename):
      platform = 'x86_64';
      opsys = 'Windows%20Server%202008';
      break;
    case w764_test_re.test(slavename):
      platform = 'x86_64';
      opsys = 'Windows%207';
      break;
    case w864_test_re.test(slavename):
      platform = 'x86_64';
      opsys = 'Windows%208';
      break;
    default:
      return "";
  }
  var template_link = template_base_link
  template_link += '&short_desc=' + slavename + '%20problem%20tracking';
  template_link += '&alias=' + slavename;
  template_link += '&rep_platform=' + platform;
  template_link += '&op_sys=' + opsys;
  return template_link;
}

function handleResponse(response,slavename) {
  var output = "";
  var json = JSON.parse(response);
  var bugs = json.bugs;

  for (var i = 0; i < bugs.length; i++) {
    output += bugs[i].id + ": " + bugs[i].summary + "\n";
  }

  var em = document.getElementById(slavename);
  bugzilla_url = "";
  bug_icon = "&nbsp;";
  if (bugs[0]) {
    bugzilla_url = 'https://bugzil.la/' + bugs[0].id;
    if (bugs[0].status == 'NEW') {
      bug_icon += '<img alt="Existing bug, status=NEW" title="Existing bug, status=NEW" src="./icons/bug.png"/>';
    } else if (bugs[0].status == 'REOPENED') {
      bug_icon += '<img alt="Existing bug, status=REOPENED" title="Existing bug, status=REOPENED" src="./icons/bug_error.png"/>';
    } else if (bugs[0].status == 'RESOLVED') {
	bug_icon += '<img alt="Existing bug, status=' + bugs[0].resolution + '" title="Existing bug, status=' + bugs[0].resolution + '" src="./icons/bug_delete.png"/>';
    }
  } else {
    bugzilla_url = getTemplateLinkForSlavename(slavename);
    bug_icon += '<img alt="File a new bug" title="File a new bug" src="./icons/bug_add.png" />';
  }
  em.innerHTML = '<a target="_buildduty_bz" href="' + bugzilla_url + '">' + slavename + bug_icon + '</a> ';
}

function progressListener() {
  if (this.readyState == 4 && this.status == 200) {
    handleResponse(this.responseText, this.slavename);
  }
}

function getBugByAlias(bugAlias) {
  var em = document.getElementById(bugAlias);
  em.innerHTML = bugAlias + '&nbsp;<img alt="Looking up bug..." title="Looking up bug..." src="./icons/loading.png" />';

  var apiURL = "https://api-dev.bugzilla.mozilla.org/latest/bug" +
               "?alias=" + bugAlias;

  var client = new XMLHttpRequest();
  client.onreadystatechange = progressListener;
  client.slavename = bugAlias;
  client.open("GET", apiURL);
  client.setRequestHeader('Accept',       'application/json');
  client.setRequestHeader('Content-Type', 'application/json');
  client.send();
}

function preload() {
  for (i = 0; i < preload.arguments.length; i++) {
    images[i] = new Image()
    images[i].src = preload.arguments[i]
  }
}

preload.apply(this, "./icons/help.png ./icons/bug.png ./icons/bug_add.png ./icons/bug_delete.png ./icons/bug_error.png ./icons/loading.png".split(" "));
