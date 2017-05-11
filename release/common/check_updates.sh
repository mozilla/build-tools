check_updates () {
  # called with 6 args - platform, source package, target package, update package, old updater boolean, updates-settings.ini values
  update_platform=$1
  source_package=$2
  target_package=$3
  locale=$4
  use_old_updater=$5
  mar_channel_IDs=$6

  # cleanup
  rm -rf source/*
  rm -rf target/*

  unpack_build $update_platform source "$source_package" $locale '' $mar_channel_IDs
  if [ "$?" != "0" ]; then
    echo "FAILED: cannot unpack_build $update_platform source $source_package"
    return 1
  fi
  unpack_build $update_platform target "$target_package" $locale 
  if [ "$?" != "0" ]; then
    echo "FAILED: cannot unpack_build $update_platform target $target_package"
    return 1
  fi
  
  case $update_platform in
      Darwin_ppc-gcc | Darwin_Universal-gcc3 | Darwin_x86_64-gcc3 | Darwin_x86-gcc3-u-ppc-i386 | Darwin_x86-gcc3-u-i386-x86_64 | Darwin_x86_64-gcc3-u-i386-x86_64) 
          platform_dirname="*.app"
          updaters="Contents/MacOS/updater.app/Contents/MacOS/updater Contents/MacOS/updater.app/Contents/MacOS/org.mozilla.updater"
          binary_file_pattern='^Binary files'
          is_windows=0
          ;;
      WINNT*) 
          platform_dirname="bin"
          updaters="updater.exe"
          binary_file_pattern='^Files.*and.*differ$'
          is_windows=1
          ;;
      Linux_x86-gcc | Linux_x86-gcc3 | Linux_x86_64-gcc3) 
          platform_dirname=`echo $product | tr '[A-Z]' '[a-z]'`
          updaters="updater"
          binary_file_pattern='^Binary files'
          # Bug 1209376. Linux updater linked against other libraries in the installation directory
          export LD_LIBRARY_PATH=$PWD/source/$platform_dirname
          is_windows=0
          ;;
  esac

  if [ -f update/update.status ]; then rm update/update.status; fi
  if [ -f update/update.log ]; then rm update/update.log; fi

  if [ -d source/$platform_dirname ]; then
    # abspaths, with backslashes for windows, to address the changes in
    # https://hg.mozilla.org/mozilla-central/rev/702bca2e601f#l9.79
    if [ $is_windows -ne 0 ]; then
      cwd=$(echo $PWD/source/$platform_dirname | sed -e 's,/,\\\\,g')
      update_abspath=$(echo $PWD/update | sed -e 's,/,\\\\,g')
      updater_abspath="$update_abspath\\$updater_bin"
    else
      cwd="$PWD/source/$platform_dirname"
      update_abspath="$PWD/update"
      updater_abspath="$update_abspath/$updater_bin"
    fi
    cd source/$platform_dirname;
    updater_bin="updater"
    for updater in $updaters; do
        if [ -e "$updater" ]; then
            echo "Found updater at $updater"
            cp $updater ../../update
            updater_bin=$(basename $updater)
            break
        fi
    done
    if [ "$use_old_updater" = "1" ]; then
        "$updater_abspath" "$update_abspath" "$cwd" 0
    else
        "$updater_abspath" "$update_abspath" "$cwd" "$cwd" 0
    fi
    cd ../..
  else
    echo "FAIL: no dir in source/$platform_dirname"
    return 1
  fi

  cat update/update.log
  update_status=`cat update/update.status`

  if [ "$update_status" != "succeeded" ]
  then
    echo "FAIL: update status was not successful: $update_status"
    return 1
  fi

  diff -r source/$platform_dirname target/$platform_dirname  > results.diff
  diffErr=$?
  cat results.diff
  grep ^Only results.diff | sed 's/^Only in \(.*\): \(.*\)/\1\/\2/' | \
  while read to_test; do
    if [ -d "$to_test" ]; then 
      echo Contents of $to_test dir only in source or target
      find "$to_test" -ls | grep -v "${to_test}$"
    fi
  done
  grep "$binary_file_pattern" results.diff > /dev/null
  grepErr=$?
  if [ $grepErr == 0 ]
  then
    echo "FAIL: binary files found in diff"
    return 1
  elif [ $grepErr == 1 ]
  then
    if [ -s results.diff ]
    then
      echo "WARN: non-binary files found in diff"
      return 2
    fi
  else
    echo "FAIL: unknown error from grep: $grepErr"
    return 3
  fi
  if [ $diffErr != 0 ]
  then
    echo "FAIL: unknown error from diff: $diffErr"
    return 3
  fi
}
