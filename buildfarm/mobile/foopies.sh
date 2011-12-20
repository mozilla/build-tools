#!/bin/bash

if [ "$1" == "ssh" ]; then
  echo "setting up initial ssh config for foopy$2"
  ssh cltbld@foopy$2 'mkdir /Users/cltbld/.ssh ; chmod 0700 /Users/cltbld/.ssh ; touch /Users/cltbld/.ssh/authorized_keys ; chmod 0644 /Users/cltbld/.ssh/authorized_keys'
  scp foopy-authorized_keys cltbld@foopy$2:.ssh/authorized_keys
  scp id_rsa id_rsa.pub cltbld@foopy$2:/Users/cltbld/.ssh/
  exit
fi

if [ -z $1 ] ; then
  FOOPIES="12"
else
  FOOPIES=$*
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
    * )
      FOOPY=""
      TEGRAS=""
      echo "You must specify a foopy ID"
      exit
  esac

  echo "Setting up ${FOOPY} ${FOOPYIP}"

  scp setup_foopy.sh cltbld@${FOOPY}:.
  ssh cltbld@${FOOPY} 'chmod +x /Users/cltbld/setup_foopy.sh ; /Users/cltbld/setup_foopy.sh'

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

  ssh cltbld@${FOOPY} 'chmod +x /builds/update_tegra_ini.sh ; /builds/update_tegra_ini.sh'

  rm -f create_dirs.sh create_dirs.sh.sed
  rm -f tegra_stats.sh tegra_stats.sh.sed
  rm -f watcher.ini watcher.ini.sed
  rm -f SUTAgent.ini SUTAgent.ini.sed
done

