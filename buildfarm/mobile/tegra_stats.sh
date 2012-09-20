#!/bin/bash
cd /builds
FOOPY=`facter hostname 2>/dev/null`
if [ -z "$FOOPY" ] ; then
    echo "ERROR: Unable to get the foopy name via hostname";
fi
python sut_tools/check.py -e
rsync -azv -e ssh /builds/tegra_status.txt briarpatch@mobile-dashboard1.build.mtv1.mozilla.com:/var/www/tegras/tegra_status-$FOOPY.txt
rsync -azv -e ssh /builds/tegra_events.log briarpatch@mobile-dashboard1.build.mtv1.mozilla.com:/var/www/tegras/tegra_events-$FOOPY.log
for i in tegra-*; do
  rsync -azv -e ssh /builds/${i}/${i}_status.log briarpatch@mobile-dashboard1.build.mtv1.mozilla.com:/var/www/tegras/
done

