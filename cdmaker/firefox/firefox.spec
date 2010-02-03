
$ARCHIVE_DIR = "../archive";
$APP_AND_VOLUME_ID = "Firefox 3.6";
$ISO_FILE = "firefox-3.6.iso";

$RELEASES = [
  {
    archive_path => "firefox/releases",
    version => "3.6",
    ####  Put the local you want to be the default (eg: en-US) last in the array
    locales => ["de", "fr", "es-ES", "ru", "en-GB", "pt-BR", "pl", "it", "ja","en-US"],
    builds => [
      { from => "%version%/win32/%locale%/Firefox Setup %version%.exe",
          to => "Windows/FirefoxSetup%version%.exe" },
      { from => "%version%/mac/%locale%/Firefox %version%.dmg",
          to => "Mac OS X/Firefox %version%.dmg" },
      { from => "%version%/linux-i686/%locale%/firefox-%version%.tar.bz2",
          to => "Linux/firefox-%version%.tar.bz2" },
      { from => "%version%/win32/%locale%/Firefox Setup %version%.exe",
          to => "Windows/%locale%/FirefoxSetup%version%.exe" },
      { from => "%version%/mac/%locale%/Firefox %version%.dmg",
          to => "Mac OS X/%locale%/Firefox %version%.dmg" },
      { from => "%version%/linux-i686/%locale%/firefox-%version%.tar.bz2",
          to => "Linux/%locale%/firefox-%version%.tar.bz2" },
    ],
    others => [
      { from => "MPL-1.1.txt",
          to => "MPL-1.1.txt" },
      { from => "README.txt",
          to => "README.txt" },
      { from => "autorun/autorun.inf",
          to => "autorun.inf" },
      { from => "autorun/autorun.ico",
          to => "icon/Firefox.ico" },
    ],
  },
];

1;
