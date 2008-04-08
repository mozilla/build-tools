//Draw canvas
const Ci = Components.interfaces;

var platformSuffix;
switch (navigator.platform.substr(0,3).toLowerCase()) {
 case 'mac':
  platformSuffix = '_mac';
  break;
 case 'win':
   platformSuffix = '_win';
   break;
 case 'lin':
   platformSuffix = '_linux';
}

function doMyScreen() {
  if (window.arguments.length < 2) {
    throw "not enough arguments";
  }
  var actor = window.arguments[0].QueryInterface(Ci.nsIDOMWindowInternal);
  var leafname = window.arguments[1];
  var canvas = document.createElement("canvas");
  canvas.style.width = actor.outerWidth + "px";
  canvas.style.height = actor.outerHeight + "px";
  canvas.width = actor.outerWidth;
  canvas.height = actor.outerHeight;

  var ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0,
		actor.outerWidth,
		actor.outerHeight);
  ctx.save();
  ctx.drawWindow(actor,
		 0, 0,
		 actor.outerWidth, actor.outerHeight,
		 "rgb(0,0,0)");
  ctx.restore();
  var prefs = Components.classes["@mozilla.org/preferences-service;1"].
    getService(Components.interfaces.nsIPrefService).
    getBranch('l10n.coverage.');
  var outdir = prefs.getCharPref('outdir');
  // convert string filepath to an nsIFile
  var file = Components.classes["@mozilla.org/file/local;1"]
                       .createInstance(Components.interfaces.nsILocalFile);
  file.initWithPath(outdir);
  file.append(leafname + platformSuffix + '.png');

  // create a data url from the canvas and then create URIs of the source and targets  
  var io = Components.classes["@mozilla.org/network/io-service;1"]
                     .getService(Components.interfaces.nsIIOService);
  var source = io.newURI(canvas.toDataURL("image/png", ""), "UTF8", null);
  var target = io.newFileURI(file)

  // prepare to save the canvas data
  var persist = Components.classes["@mozilla.org/embedding/browser/nsWebBrowserPersist;1"]
                          .createInstance(Components.interfaces.nsIWebBrowserPersist);
  
  persist.persistFlags = Components.interfaces.nsIWebBrowserPersist.PERSIST_FLAGS_REPLACE_EXISTING_FILES;
  persist.persistFlags |= Components.interfaces.nsIWebBrowserPersist.PERSIST_FLAGS_AUTODETECT_APPLY_CONVERSION;
  
  // displays a download dialog (remove these 3 lines for silent download)
  //var xfer = Components.classes["@mozilla.org/transfer;1"]
  //                     .createInstance(Components.interfaces.nsITransfer);
  //xfer.init(source, target, "", null, null, null, persist);
  //persist.progressListener = xfer;
  
  // save the canvas data to the file
  persist.saveURI(source, null, null, null, null, file);
  window.close();
}
