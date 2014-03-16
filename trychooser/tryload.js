var TRY_BUILD_LOAD_URL =  "http://builddata.pub.build.mozilla.org/reports/pending/pending_compile_try.txt";
var TRY_TEST_LOAD_URL =  "http://builddata.pub.build.mozilla.org/reports/pending/pending_test_try.txt";
var NONTRY_TEST_LOAD_URL =  "http://builddata.pub.build.mozilla.org/reports/pending/pending_test_nontry.txt";

/* Initialize the things which appear in the right-hand side of assignments in getTryLoads with the names
   used in the URLs above. */
function initLoad() {
  return {
    "linux": 0,
    "linux64": 0,
    "linux-hp": 0,
    "ubuntu32-vm": 0,
    "ubuntu64-vm": 0,
    "macosx64": 0,
    "mac10.6-rev4": 0,
    "mac10.8": 0,
    "macosx64": 0,
    "win32": 0,
    "winxp-ix": 0,
    "win7-ix": 0,
    "win8": 0,
    "win64": 0,
    "win2012x64": 0,
    "tegra": 0,
    "panda": 0,
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
        totalBuildLoad["linux64"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64-asan"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64-st-an"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64-valgrind"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64-br-haz"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64-sh-haz"] = totalBuildLoad["linux"];
        totalBuildLoad["macosx64"] = load_try_build["macosx64"];
        totalBuildLoad["win32"] = load_try_build["win32"] + load_try_build["win64"];
        totalBuildLoad["win64"] = load_try_build["win64"];
        totalBuildLoad["android"] = totalBuildLoad["linux"];
        totalBuildLoad["android-armv6"] = totalBuildLoad["linux"];
        totalBuildLoad["android-x86"] = totalBuildLoad["linux64"];
        totalBuildLoad["emulator"] = totalBuildLoad["linux"];
        totalBuildLoad["emulator-jb"] = totalBuildLoad["linux"];
        totalBuildLoad["emulator-kk"] = totalBuildLoad["linux"];
        totalBuildLoad["linux32_gecko"] = totalBuildLoad["linux"];
        totalBuildLoad["linux64_gecko"] = totalBuildLoad["linux"];
        totalBuildLoad["macosx64_gecko"] = totalBuildLoad["macosx64"];
        totalBuildLoad["win32_gecko"] = totalBuildLoad["win32"];

        var totalTestLoad = {};
        totalTestLoad["linux"] = load_try_test["linux"] + load_nontry_test["linux"] +
                                 load_try_test["ubuntu32-vm"] + load_nontry_test["ubuntu32-vm"];
        totalTestLoad["linux64"] = load_try_test["linux64"] + load_nontry_test["linux64"] +
                                   load_try_test["ubuntu64-vm"] + load_nontry_test["ubuntu64-vm"];
        totalTestLoad["linux64-asan"] = totalTestLoad["linux64"];
        // linux64-st-an: N/A
        totalTestLoad["macosx64"] = Math.max(
                                      load_try_test["mac10.6-rev4"] + load_nontry_test["mac10.6-rev4"],
                                      load_try_test["mac10.8"] + load_nontry_test["mac10.8"]);
        totalTestLoad["win32"] = Math.max(
                                   load_try_test["winxp-ix"] + load_nontry_test["winxp-ix"],
                                   load_try_test["win7-ix"] + load_nontry_test["win7-ix"],
                                   load_try_test["win8"] + load_nontry_test["win8"]);
        totalTestLoad["win64"] = load_try_test["win2012x64"] + load_nontry_test["win2012x64"];
        totalTestLoad["android"] = Math.max(
                                     load_try_test["tegra"] + load_nontry_test["tegra"],
                                     load_try_test["panda"] + load_nontry_test["panda"]);
        totalTestLoad["android-armv6"] = load_try_test["tegra"] + load_nontry_test["tegra"];
        totalTestLoad["emulator"] = totalTestLoad["linux64"];
        // emulator-jb: N/A
        // emulator-kk: N/A
        totalTestLoad["linux32_gecko"] = totalTestLoad["linux"];
        totalTestLoad["linux64_gecko"] = totalTestLoad["linux64"];
        totalTestLoad["macosx64_gecko"] = totalTestLoad["macosx64"];
        // win32_gecko: N/A
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
