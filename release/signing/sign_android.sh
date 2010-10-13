export PATH=$PATH:/cygdrive/c/Program\ Files/Java/jdk1.6.0_21/bin:/cygdrive/c/cygwin/home/cltsign/android/android-sdk-windows/tools
export JAVA_HOME=/cygdrive/c/Program\ Files/Java/jdk1.6.0_21

cp gecko-unsigned-unaligned.apk gecko-unaligned.apk
python mozpass.py -i --keystore c:/cygwin/home/cltsign/android-release.keystore --alias release --apk gecko-unaligned.apk
if [ $? -ne 0 ] ; then
  echo "ERROR: deal with the above before proceeding!"
  exit -1
else
  echo "Created gecko-unaligned.apk"
fi
zipalign -f 4 gecko-unaligned.apk fennec.apk
if [ $? -ne 0 ] ; then
  echo "ERROR: deal with the above before proceeding!"
  exit -1
else
  echo "Created fennec.apk"
fi
