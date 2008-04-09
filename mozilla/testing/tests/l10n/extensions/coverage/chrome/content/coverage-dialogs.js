_dialogHooks = {};
_dialogHooks[['prefs','paneContent']] = ['popupPolicyButton'];
_dialogHooks[['prefs','panePrivacy']] = ['showCookiesButton',
                                         'cookieExceptions'];
_dialogHooks[['prefs','paneSecurity']] = ['showPasswords',
                                          'passwordExceptions',
                                          'addonExceptions'];
_dialogHooks[['prefs',
              'paneAdvanced',
              'networkPanel']] = ['offlineNotifyExceptions'];
_dialogHooks[['prefs',
              'paneAdvanced',
              'encryptionPanel']] = ['viewSecurityDevicesButton',
                                     'viewCRLButton',
                                     'viewCertificatesButton'];

function dialogHook(aElem, ids) {
  if (ids in _dialogHooks) {
    Components.utils.reportError('found dialog for ' + ids);
    for (i in _dialogHooks[ids]) {
      var id = _dialogHooks[ids][i];
      var elem = aElem.getElementsByAttribute('id', id)[0];
      if (!elem) {
        debug('dropping ' + id + ', beneath a ' + aElem.nodeName);
        continue;
      }
      Stack.push(new DialogShot(elem, ids.concat([id])));
      Components.utils.reportError('adding ' + id);
    }
  }
};

function DialogLoadHandler(ids) {
  this.ids = ids;
};
DialogLoadHandler.prototype = {
  handleEvent: function _dlh(aEvent) {
    var targetDoc = aEvent.target;
    var ids = this.ids;
    var advanceTabs = 0;
    var tabbox;
    if (targetDoc.getElementsByTagName('tabbox').length) {
      tabbox = targetDoc.getElementsByTagName('tabbox')[0];
      tabbox.selectedIndex = 0;
      advanceTabs = tabbox.tabs.itemCount - 1;
      ids.push(tabbox.selectedPanel.getAttribute('id'));
    }
    debug("dialog " + ids[ids.length-1] + " has " + (advanceTabs+1) + " shots")
    for (var i = 0; i < advanceTabs ; ++i) {
      Stack.push(new TabAdvancer(tabbox, ids, targetDoc.window));
    }
    // dialog hook again?
    Stack.push(new Screenshot(ids.join('_'), targetDoc.window));
    Stack.continue();    
  }
};

function DialogShot(elem, ids) {
  this.args = [elem, ids];
}
DialogShot.prototype = {
 args: null,
 method: function _ds(elem, ids) {
    Stack.suspend();
    // the following two actions are set in onOpenWindow, we have the 
    // window then:
    // Stack.push(close)
    // if tabbox, for all panels:
    //   Stack.push(new Screenshot(ids.join('_')));
    WM.addListener(this);
    elem.doCommand();
    Components.utils.reportError("I'd open " +  ids);
  },
  // nsIWindowMediatorListener
  onWindowTitleChange: function(aWindow, newTitle){},
  onOpenWindow: function(aWindow) {
    WM.removeListener(this);
    debug("dialog opening found");
    // ensure the timer runs in the modal window, too
    Stack._timer.initWithCallback({notify:function (aTimer) {Stack.pop();}},
                                  Stack._time, 1);
    aWindow.docShell.QueryInterface(Ci.nsIInterfaceRequestor);
    var DOMwin = aWindow.docShell.getInterface(Ci.nsIDOMWindow);
    // close action
    var closer = {
    args: null,
    method: function _close() {
        debug("dialog close called");
        DOMwin.close();
      }
    };
    Stack.push(closer);
    DOMwin.addEventListener('load',
                            new DialogLoadHandler(this.args[1]),
                            false);
  },
  onCloseWindow: function(aWindow){}
};

    
