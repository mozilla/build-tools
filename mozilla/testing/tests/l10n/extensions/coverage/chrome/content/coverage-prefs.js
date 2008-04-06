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

var isMac = navigator.platform.substr(0,3) == "Mac";
function waitForMac() {
  if (!isMac) return;
  Stack.suspend();
  window.setTimeout(function(){Stack.continue();}, 1000);
}

function WaitForMac(period) {
  this.args = [period];
};
WaitForMac.prototype = {
 args: null,
 method: function _waitForMac(period) {
    if (!isMac) return;
    Stack.suspend()
    window.setTimeout(function() {Stack.continue()}, period);
  }
};

/**
 * Item to show the next pane in a prefs window
 */
function ShowPaneObj(aPane, aLoader) {
  this.args = [aPane, aLoader];
}
ShowPaneObj.prototype = {
  args: null,
  method: function _openMenu(aPane, aLoader) {
    Stack.suspend();
    Stack.push(aLoader);
    Stack.push(new Screenshot(aPane.getAttribute('id')));
    aPane.parentNode.showPane(aPane);
    if (isMac) {
      Stack.push(new WaitForMac(1000));
    }
  }
};

/**
 * Item to close the preferences window once the tests are done
 */
function ClosePreferences() {
  this.args = [];
};
ClosePreferences.prototype = {
  args: [],
  method: function() {
    var pWin = WM.getMostRecentWindow("Browser:Preferences");
    if (pWin) {
      pWin.close();
    }
    else {
      Components.utils.reportError("prefwindow not found, trying again");
    }
  }
};

/**
 * Item to wait for a preference pane to load
 */
function PrefPaneLoader() {
};
PrefPaneLoader.prototype = {
  _currentPane: null,
  args: [],
  method: function() {
    // the pane is loaded, kick off the load of the next one, if available
    pane = this._currentPane.nextSibling;
    this._currentPane = null;
    while (pane) {
      if (pane.nodeName == 'prefpane') {
        Stack.push(new ShowPaneObj(pane, this));
        return;
      }
      pane = pane.nextSibling;
    }
  },
  // nsIDOMEventListener
  handleEvent: function _hv(aEvent) {
    this._currentPane = aEvent.target;
    Stack.continue();
  }
};

/**
 * Item to start the preference dialog tests
 *
 * This item expects to have 'paneMain' as the ID of the first pane.
 * That may be an over-simplification, but it guarantees to load
 * the panes from left to right, and that all are not loaded yet.
 * WFM.
 */
function RootPreference(aWindow, startPane) {
  this.args = [aWindow, startPane];
};
RootPreference.prototype = {
  args: [],
  method: function(aWindow, startPane) {
    WM.addListener(this);
    aWindow.openPreferences(startPane);
  },
  // nsIWindowMediatorListener
  onWindowTitleChange: function(aWindow, newTitle){},
  onOpenWindow: function(aWindow) {
    WM.removeListener(this);
    // ensure the timer runs in the modal window, too
    Stack._timer.initWithCallback({notify:function (aTimer) {Stack.pop();}},
                                  Stack._time, 1);
    Stack.push(new ClosePreferences());
    var ppl = new PrefPaneLoader();
    aWindow.docShell.QueryInterface(Ci.nsIInterfaceRequestor);
    var DOMwin = aWindow.docShell.getInterface(Ci.nsIDOMWindow);
    DOMwin.addEventListener('paneload', ppl, false);
    Stack.suspend();
    Stack.push(ppl);
    Stack.push(new Screenshot(this.args[1]));
    if (isMac) {
      Stack.push(new WaitForMac(1000));
    }
  },
  onCloseWindow: function(aWindow){}
};

toRun.push(new TestDone('PREFERENCES'));
toRun.push(new RootPreference(wins[0], 'paneMain'));
toRun.push(new TestStart('PREFERENCES'));
