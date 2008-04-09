//Draw canvas
const Ci = Components.interfaces;
const Cc = Components.classes;
var prefs = Cc["@mozilla.org/preferences-service;1"].
  getService(Ci.nsIPrefService).
  getBranch('l10n.coverage.');
var outdirpref = prefs.getCharPref('outdir');
// convert string filepath to an nsIFile
var outdir = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
outdir.initWithPath(outdirpref);

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
  canvas.style.width = actor.innerWidth + "px";
  canvas.style.height = actor.innerHeight + "px";
  canvas.width = actor.innerWidth;
  canvas.height = actor.innerHeight;

  var ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0,
		actor.innerWidth,
		actor.innerHeight);
  ctx.save();
  ctx.drawWindow(actor,
		 0, 0,
		 actor.innerWidth, actor.innerHeight,
		 "rgb(0,0,0)");
  ctx.restore();
  saveURL(canvas.toDataURL("image/png", ""),
          leafname + platformSuffix + '.png');
  var line = leafname + ',' + actor.document.location + "\n";
  var listfile = outdir.clone();
  listfile.append('list.txt');
  var fstream = Cc["@mozilla.org/network/file-output-stream;1"].
    createInstance(Ci.nsIFileOutputStream);
  // PR_WRONLY | PR_CREATE_FILE | PR_APPEND
  fstream.init(listfile, 0x02 | 0x08 | 0x10  , 420, 0);
  fstream.write(line, line.length);
  fstream.close();
  window.close();
};

function saveURL(aURL, filename) {
  var file = outdir.clone();
  file.append(filename);

  // create a data url from the canvas and then create URIs of the source and targets  
  var io = Components.classes["@mozilla.org/network/io-service;1"]
                     .getService(Components.interfaces.nsIIOService);
  var source = io.newURI(aURL, "UTF8", null);
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
}
