var TRY_BUILD_LOAD_URL =  "http://build.mozilla.org/builds/pending/pending_compile_try.txt";
var TRY_TEST_LOAD_URL =  "http://build.mozilla.org/builds/pending/pending_test_try.txt";
var NONTRY_TEST_LOAD_URL =  "http://build.mozilla.org/builds/pending/pending_test_nontry.txt";

function initLoad() {
  return {
    "linux": 0,
    "linux64": 0,
    "linux-hp": 0,
    "macosx64": 0,
    "mac10.6-rev4": 0,
    "mac10.7": 0,
    "mac10.8": 0,
    "macosx64": 0,
    "win32": 0,
    "winxp": 0,
    "winxp-ix": 0,
    "win7": 0,
    "win7-ix": 0,
    "win64": 0,
    "android": 0,
    "ics_armv7a_gecko": 0,
    "android-armv6": 0,
    "android-noion": 0,
    "android-x86": 0,
    "tegra": 0,
    "panda": 0,
    "otoro": 0,
    "unagi": 0,
  };
}

function getTryLoad(url, callback) {
  var oXHR = new XMLHttpRequest();
  oXHR.onreadystatechange = function (e) {
    if (oXHR.readyState === 4 && (oXHR.status === 200 || oXHR.status === 0)) {
      var loadText = oXHR.responseText;
      var loadLines = loadText.split("\n");
      var load = initLoad();
      for (var i in loadLines) {
        var line = loadLines[i];
        var words = loadLines[i].split(" ");
        if (words.length == 2 && words[1].charAt(0) == "(" && words[1].charAt(words[1].length-1) == ")") {
          load[words[0]] = parseInt(words[1].substring(1, words[1].length - 1)); 
        }
      }
      callback(load);
    }
  }
  oXHR.open("GET", url, true);
  oXHR.responseType = "text";
  oXHR.send(null);
}

function getTryLoads(callback) {
  getTryLoad(TRY_BUILD_LOAD_URL, function(load_try_build) {
    getTryLoad(TRY_TEST_LOAD_URL, function(load_try_test) {
      getTryLoad(NONTRY_TEST_LOAD_URL, function(load_nontry_test) {
        var totalBuildLoad = {};
        totalBuildLoad["linux"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["linux64"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["macosx64"] = load_try_build["macosx64"];
        totalBuildLoad["win32"] = load_try_build["win32"] + load_try_build["win64"];
        totalBuildLoad["android"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["android-armv6"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["android-noion"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["android-x86"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["ics_armv7a_gecko"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["panda"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["otoro"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];
        totalBuildLoad["unagi"] = load_try_build["linux"] + load_try_build["linux64"] + load_try_build["linux-hp"];

        var totalTestLoad = {};
        totalTestLoad["linux"] = load_try_test["linux"] + load_nontry_test["linux"];
        totalTestLoad["linux64"] = load_try_test["linux64"] + load_nontry_test["linux64"];
        totalTestLoad["macosx64"] = Math.max(
                                     Math.max(
                                      load_try_test["mac10.6-rev4"] + load_nontry_test["mac10.6-rev4"],
                                      load_try_test["mac10.7"] + load_nontry_test["mac10.7"])
                                    , load_try_test["mac10.8"] + load_nontry_test["mac10.8"]);
        totalTestLoad["win32"] = Math.max(
                                   load_try_test["winxp"] + load_nontry_test["winxp"],
                                   load_try_test["winxp-ix"] + load_nontry_test["winxp-ix"],
                                   load_try_test["win7"] + load_nontry_test["win7"],
                                   load_try_test["win7-ix"] + load_nontry_test["win7-ix"]);
        totalTestLoad["android"] = Math.max(
                                     load_try_test["tegra"] + load_nontry_test["tegra"],
                                     load_try_test["panda"] + load_nontry_test["panda"]);
        totalTestLoad["android-armv6"] = load_try_test["tegra"] + load_nontry_test["tegra"];
        totalTestLoad["android-noion"] = load_try_test["tegra"] + load_nontry_test["tegra"];
        totalTestLoad["ics_armv7a_gecko"] = load_try_test["linux"] + load_nontry_test["linux"];
        totalTestLoad["panda"] = load_try_test["panda"] + load_nontry_test["panda"];
        // otoro / unagi: N/A
        callback(totalBuildLoad, totalTestLoad);
      });
    });
  });
}

function showTryLoads() {
  getTryLoads(function showLoads(totalBuildLoad, totalTestLoad) {
    for (var platform in totalBuildLoad) {
      var load = totalBuildLoad[platform]
      console.log("build load for: " + platform);
      if (load == undefined) {
        console.log("Load for platform '" + platform + "' not defined. Skipping.");
        continue;
      }

      var elemId = "build_" + platform;
      var elem = document.getElementById(elemId);
      if (!elem) {
        console.log("Element '" + elemId + "' not found. Skipping.");
        continue;
      }

      console.log("build load for: " + platform + ", " + load);
      elem.textContent = load;
      elem.style.color = "rgb(" + Math.min(Math.round((load/500.0) * 255), 255) + ",0,0)";
    }
    for (var platform in totalTestLoad) {
      var load = totalTestLoad[platform]
      if (load == undefined) {
        console.log("Load for platform '" + platform + "' not defined. Skipping.");
        continue;
      }

      var elemId = "test_" + platform;
      var elem = document.getElementById(elemId);
      if (!elem) {
        console.log("Element '" + elemId + "' not found. Skipping.");
        continue;
      }

      elem.textContent = load;
      elem.style.color = "rgb(" + Math.min(Math.round((load/500.0) * 255), 255) + ",0,0)";
    }
  });
}

window.addEventListener('load', function() {
  showTryLoads();
}, false);
