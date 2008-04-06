/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is mozilla.org l10n testing.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Foundation.
 * Portions created by the Initial Developer are Copyright (C) 2066
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *  Axel Hecht <l10n@mozilla.com>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

/**
 * Basic architecture for UI exposure tests
 *
 * Details on http://wiki.mozilla.org/SoftwareTesting:Tools:L10n:Coverage
 */

var Ci = Components.interfaces;
var Cc = Components.classes;
var Cr = Components.results;

const NS_DIRECTORY_SERVICE_CONTRACTID = "@mozilla.org/file/directory_service;1";

var ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
var ds = Cc[NS_DIRECTORY_SERVICE_CONTRACTID].getService(Ci.nsIProperties);
const WM = Cc["@mozilla.org/appshell/window-mediator;1"]
  .getService(Ci.nsIWindowMediator);
const WW = Cc["@mozilla.org/embedcomp/window-watcher;1"]
  .getService(Ci.nsIWindowWatcher);


/**
 * Global Stack object
 *
 * This object keeps the tests running with some time for visual inspection.
 */
var Stack = {
  _stack: [],
  _time: 250,
  _waiting: 0,
  _timer: Cc["@mozilla.org/timer;1"].createInstance(Ci.nsITimer),
  notify: function _notify(aTimer) {
    this.pop();
  },
  push: function _push(aItem) {
    this._stack.push(aItem);
    if (this._stack.length == 1) {
      this._timer.initWithCallback({notify:function (aTimer) {Stack.pop();}},
                                   this._time, 1);
    }
  },
  pop: function _pop() {
    if (this._waiting) {
      return;
    }
    var obj = this._stack.pop();
    try {
      obj.method.apply(obj, obj.args);
    } catch (e) {
      Components.utils.reportError(e);
    }
    if (!this._stack.length) {
      this._timer.cancel();
    }
  },
  suspend: function _suspend() {
    this._waiting += 1;
  },
  continue: function _continue() {
    this._waiting -= 1;
    if (this._waiting < 0) Components.utils.reportError("non-matched continue");
  }
};
/**
 * Add your test set to toRun.
 * The onload handler will add them to the Stack and kick off the
 * testing.
 */
var toRun = [];

/**
 * Utility to get array of xpcom objects from a nsISimpleEnumerator
 * Requires JS1.7
 */
function SimpleGenerator(enumr, interface) {
  while (enumr.hasMoreElements()) {
    yield enumr.getNext().QueryInterface(interface);
  }
}

var wins = [w for (w in SimpleGenerator(WM.getEnumerator(null), Ci.nsIDOMWindow))];

/**
 * Helper items to log start and end of testing to the Error Console
 */
function MsgBase() {
}
MsgBase.prototype = {
  args: [],
  method: function() {
    Components.utils.reportError(this._msg);
  }
};
function TestStart(aCat) {
  this._msg = 'TESTING:START:COVERAGE:' + aCat;
}
TestStart.prototype = new MsgBase;
function TestDone(aCat) {
  this._msg = 'TESTING:DONE:COVERAGE:' + aCat;
}
TestDone.prototype = new MsgBase;

/**
 * onload handler for the entry page.
 * Copy the toRun items over to the stack and kick things off.
 */
function onLoad() {
  for each (var obj in toRun) {
    Stack.push(obj);
  }
}

/**
 * Screenshot helper
 */
function doScreenShot(name) {
  var _base = null;
  var actor = WM.getMostRecentWindow(null).QueryInterface(Ci.nsIDOMWindow);
  var params = Cc["@mozilla.org/array;1"].createInstance(Ci.nsIMutableArray);
  params.appendElement(actor, false);
  var _name = Cc["@mozilla.org/supports-string;1"].
    createInstance(Ci.nsISupportsString);
  _name.data = name;
  params.appendElement(_name, false);
  var foo = WW.openWindow(null,
			  "chrome://coverage/content/screen-helper.html",
			  null, null, params);
  return foo;
}

function Screenshot(name) {
  this.args = [name];
};
Screenshot.prototype = {
 args: null,
 method: function _doScreenshot(name) {
    Stack.suspend();
    var w = doScreenShot(name);
    var obs = {
      // nsIWindowMediatorListener
    onWindowTitleChange: function(aWindow, newTitle){},
    onOpenWindow: function(aWindow) {},
    onCloseWindow: function(aWindow){
	if (!(aWindow.docShell instanceof Ci.nsIInterfaceRequestor)) {
	  Components.utils.reportError("my docshell is bad");
	}
	var aDOMWin = aWindow.docShell.getInterface(Ci.nsIDOMWindow);
	try {
	  aDOMWin.QueryInterface(Ci.nsIDOMWindowInternal);
	} catch (e) {
	  Components.utils.reportError("aDOMWin is not nsIDOMWindow")
	}
	if (aDOMWin.location != w.location) {
	  var msg = "screenshot saw unknown window dying: ";
	  var details = w.location + ", " + aWindow.location;
	  Components.utils.reportError(msg + details);
	  return;
	}
	Stack.continue();
	WM.removeListener(this);
      }
    };
    WM.addListener(obs);
  }
};
