#!/bin/bash

set -e # if anything goes wrong, there's manual work to be done

if [ "$1" == "ssh" ]; then
  echo "setting up initial ssh config for foopy$2"
  # do some sanity checks before we begin
  if ! [ -r foopy-authorized_keys -a -r id_rsa -a id_rsa.pub -a -r foopy-screenrc ]; then
    echo "your directory isn't set up properly, check wiki page"
    exit 1
  else
    echo "you'll be prompted for the 'cltbld' password 2 times"
    echo "(if 4 times, your ssh key isn't in the file and the next step will be very painful)"
    ssh cltbld@foopy$2 'mkdir /Users/cltbld/.ssh ; chmod 0700 /Users/cltbld/.ssh ; touch /Users/cltbld/.ssh/authorized_keys ; chmod 0644 /Users/cltbld/.ssh/authorized_keys'
    scp foopy-authorized_keys cltbld@foopy$2:.ssh/authorized_keys
    scp id_rsa id_rsa.pub cltbld@foopy$2:/Users/cltbld/.ssh/
    scp foopy-screenrc cltbld@foopy$2:.screenrc
    exit
  fi
fi

FOOPIES=$*
# if no args are passed, that's a user error
if [ -z "$FOOPIES" ] ; then
  echo "missing required foopy number"
  exit 1
fi

for f in ${FOOPIES} ; do
  case "$f" in
    "05" | "5" )
      FOOPY=foopy05
      TEGRAS="001 002 003 004 005 006 007 008 009 010 011 012 013"
    ;;
    "06" | "6" )
      FOOPY=foopy06
      TEGRAS="014 015 016 017 018 019 020 021 022 023 024 025 026 027 028 029"
      ;;
    "07" | "7" )
      FOOPY=foopy07
      foopy07="030 031 032 035 036 037 038 039 199 200"
      ;;
    "08" | "8" )
      FOOPY=foopy08
      TEGRAS="040 041 042 045 046 047 048 049 050 051 052 201 202"
      ;;
    "09" | "9" )
      FOOPY=foopy09
      TEGRAS="053 054 055 056 057 058 059 060 061 062 063 064 065"
      ;;
    "10" )
      FOOPY=foopy10
      TEGRAS="066 067 068 070 071 072 073 074 075 076 077 078 203"
      ;;
    "11" )
      FOOPY=foopy11
      TEGRAS="079 080 081 082 083 084 085 086 087 088 089 090 091"
      ;;
    "12" )
      FOOPY=foopy12
      FOOPYIP=10.250.48.212
      TEGRAS="092 093 094 095 096 097 098 099 100 101 102 103 104"
      ;;
    "13" )
      FOOPY=foopy13
      FOOPYIP=10.250.48.213
      TEGRAS="105 106 107 108 109 110 111 112 113 114 115 116 117"
      ;;
    "14" )
      FOOPY=foopy14
      FOOPYIP=10.250.48.214
      TEGRAS="118 119 120 121 122 123 148 149 150 151 154 155 157 194 195"
      ;;
    "15" )
      FOOPY=foopy15
      FOOPYIP=10.250.48.217
      TEGRAS="129 130 132 133 134 135 136 138 139 140 141 142 144 145 146"
      ;;
    "16" )
      FOOPY=foopy16
      FOOPYIP=10.250.48.218
      TEGRAS="158 159 160 161 162 163 164 165 166 167 168 169 170 171 172"
      ;;
    "17" )
      FOOPY=foopy17
      FOOPYIP=10.250.48.219
      TEGRAS="173 174 177 179 181 182 183 196 198 204 205"
      ;;
    "18" )
      FOOPY=foopy18
      FOOPYIP=10.250.48.220
      TEGRAS="206 207 208 209 210 211 212 213 214 215 216 217 218 219"
      ;;
    "19" )
       FOOPY=foopy19
       FOOPYIP=10.250.48.221
       TEGRAS="220 221 222 223 224 225 226 227 228 229 230 231 232 233"
       ;;
    "20" )
       FOOPY=foopy20
       FOOPYIP=10.250.48.224
       TEGRAS="234 235 236 237 238 239 240 241 242 243 244 245 246 247"
       ;;
    "21" )
      FOOPY=foopy21
      FOOPYIP=10.250.48.225
      echo "foopy21 is offline as of 2011-12-13 (bug 704590)"
      exit 1
      ;;
    "22" )
       FOOPY=foopy22
       FOOPYIP=10.250.48.226
       TEGRAS="248 249 250 251 252 253 254 255 256 257 258 259 260 261"
       ;;
    "23" )
       FOOPY=foopy23
       FOOPYIP=10.250.48.231
       TEGRAS="262 263 264 265 266 267 268 269 270 271 272 273 274 275"
       ;;
    "24" )
       FOOPY=foopy24
       FOOPYIP=10.250.48.232
       TEGRAS="276 277 278 279 280 281 282 283 284 285"
       ;;
    * )
      FOOPY=""
      TEGRAS=""
      echo "You must specify a valid foopy ID"
      exit 1
  esac

  echo "Setting up ${FOOPY} ${FOOPYIP}"

  scp setup_foopy.sh cltbld@${FOOPY}:.
  ssh cltbld@${FOOPY} 'chmod +x /Users/cltbld/setup_foopy.sh ; /Users/cltbld/setup_foopy.sh'

  # we can't create /builds - make sure it's there. set -e will catch
  # the exit code from the remote end and stop us.
  ssh cltbld@${FOOPY} 'test -d /builds || exit 1'

  cp create_dirs.sh.in create_dirs.sh.sed
  sed "s/sedTEGRALISTsed/${TEGRAS}/" create_dirs.sh.sed > create_dirs.sh

  scp create_dirs.sh buildbot.tac.tegras check.sh start_cp.sh stop_cp.sh crontab.foopy kill_stalled.sh clear_space.sh cltbld@${FOOPY}:/builds/
  scp pushfile.py cltbld@${FOOPY}:/builds/sut_tools/
  ssh cltbld@${FOOPY} 'chmod +x /builds/*.sh'
  ssh cltbld@${FOOPY} '/builds/create_dirs.sh'

  cp tegra_stats.sh.in tegra_stats.sh.sed
  sed "s/sedFOOPYNNsed/${FOOPY}/" tegra_stats.sh.sed > tegra_stats.sh

  cp SUTAgent.ini.in SUTAgent.ini.sed
  sed "s/sedFOOPYIPsed/${FOOPYIP}/" SUTAgent.ini.sed > SUTAgent.ini

  cp watcher.ini.in watcher.ini.sed
  sed "s/sedFOOPYIPsed/${FOOPYIP}/" watcher.ini.sed > watcher.ini

  scp tegra_stats.sh SUTAgent.ini update_tegra_ini.sh watcher.ini cltbld@${FOOPY}:/builds/

  # made sure all the scripts are executable
  ssh cltbld@${FOOPY} 'chmod +x /builds/*.sh'

  ssh cltbld@${FOOPY} '/builds/update_tegra_ini.sh'

  rm -f create_dirs.sh create_dirs.sh.sed
  rm -f tegra_stats.sh tegra_stats.sh.sed
  rm -f watcher.ini watcher.ini.sed
  rm -f SUTAgent.ini SUTAgent.ini.sed
done

