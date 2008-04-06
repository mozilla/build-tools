_dialogHooks = {};
if (navigator.platform.substr(0,3) != 'Mac') {
  _dialogHooks[['prefs','paneContent']] = ['chooseLanguage',
                                           'colors',
                                           'advancedFonts',
                                           'advancedJSButton',
                                           'popupPolicyButton'];
} else {
  _dialogHooks[['prefs','paneContent']] = ['popupPolicyButton'];
}

function dialogHook(aElem, ids) {
  if (ids in _dialogHooks) {
    Components.utils.reportError('found dialog for ' + ids);
    for (i in _dialogHooks[ids]) {
      var id = _dialogHooks[ids][i];
      var elem = aElem.getElementsByAttribute('id', id)[0];
      if (!elem) continue;
      Stack.push(new DialogShot(elem, ids.concat([id])));
      Components.utils.reportError('adding ' + id);
    }
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
    // Stack.push(new Screenshot(ids.join('_')));
    WM.addListener(this);
    elem.doCommand();
    Components.utils.reportError("I'd open " +  ids);
  },
  // nsIWindowMediatorListener
  onWindowTitleChange: function(aWindow, newTitle){},
  onOpenWindow: function(aWindow) {
    WM.removeListener(this);
    // ensure the timer runs in the modal window, too
    //Stack._timer.initWithCallback({notify:function (aTimer) {Stack.pop();}},
    //                              Stack._time, 1);
    aWindow.docShell.QueryInterface(Ci.nsIInterfaceRequestor);
    var DOMwin = aWindow.docShell.getInterface(Ci.nsIDOMWindow);
    // close action
    var closer = {
    args: null,
    method: function _close() {
        DOMwin.close();
      }
    };
    Stack.push(closer);
    Stack.push(new Screenshot(this.args[1].join('_'), DOMwin));
    Stack.continue();
  },
  onCloseWindow: function(aWindow){}
};

    
