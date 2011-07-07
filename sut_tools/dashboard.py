#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import json
import datetime


def calculateLastActive(d, t, dt):
    h = dt.seconds / 3600
    if dt.days == 0:
        s = '%0.2f hours' % h
    else:
        s = '%d days, %0.2f hours' % (dt.days, h)
    s += ' (%s %s)' % (d, t)
    return s

htmlDir   = '/var/www/tegras'
htmlIndex = 'index.html'
foopies   = [ 'foopy05', 'foopy06', 'foopy07', 'foopy08',
              'foopy09', 'foopy10', 'foopy11',
            ]
masters   = { 'production': "http://test-master01.build.mozilla.org:8012",
              'staging':    "http://bm-foopy.build.mozilla.org:8012",
            }
pdus =      { "1": ( "033", "034", "037", "038", "041", "042", "045", 
                     "046", "049", "050", "053", "054", "057", "058", 
                     "061", "062", "065", "066", "069", "070", "073", 
                     "074", "077", "078", "081", "082", "085", "086", 
                     "089", "090", "093", 
                   ),
              "2": ( "035", "036", "039", "040", "043", "044", "047",
                     "048", "051", "052", "055", "056", "059", "060",
                     "063", "064", "067", "068", "071", "072", "075",
                     "076", "079", "080", "083", "084", "087", "088",
                     "091", "092", 
                   ),
              "3": ( "001", "002", "003", "004", "005", "006", "007",
                     "008", "009", "010", "011", "012", "013", "014",
                     "015", "016", "017", "018", "019", "020", "021",
                     "022", "023", "024", "025", "026", "027", "028",
                     "029", "030", "031", "032", 
                   ),
            }

pageHeader = """<html>
<head>
    <title>Tegra Dashboard v0.1</title>
    <style type="text/css">
        html {
          margin: 10px;
        }
        body {
          font-family: sans-serif;
          font-size: 0.8em;
        }
        h1, h2, h3{
            font-family: Cambria, serif;
            font-size: 2.0em;
            font-style: normal;
            font-weight: normal;
            text-transform: normal;
            letter-spacing: normal;
            line-height: 1.3em;
        }
        #production {
            margin-left: 5%%;
        }
        table {
          border: 1px #c4c4c4 solid;
        }
        th {
          background-color: #ccc;
        }
        tr:nth-child(2n-1) {
          background-color: #ccc;
        }
        td {
          padding: 5px;
        }
        a {
          text-decoration: none;
        }
    </style>
</head>
<body>
<div class="header">
  <h1>Tegra Dashboard</h1>
  <p><small>From %(dStart)s to %(dEnd)s</small></p>
  <h3>PHB Notes</h3>
  <table>
    <tr><th></th><th>Production</th><th>Staging</th></tr>
    <tr><th>Tegra and buildslave online</th><td>%(productionActive)d</td><td>%(stagingActive)d</td></tr>
    <tr><th>Tegra online but buildslave is not</th><td>%(productionIdle)d</td><td>%(stagingIdle)d</td></tr>
    <tr><th>Both Tegra and buildslave are offline</th><td>%(productionOffline)d</td><td>%(stagingOffline)d</td></tr>
    <tr><th>Total</th><td>%(productionTotal)d</td><td>%(stagingTotal)d</td></tr>
  </table>
  <p><small>Total # of tegras being tracked: %(totalTotal)d</small></p>
</div>
"""
pageFooter = """<div class="footer">
  <p><small>The above information is updated by cronjobs running every 15 minutes on each foopy and then gathered into this file by a super-basic python script that is run on the server every 5 minutes</small></p>
</div>
</body>
</html>
"""
productionHeader = """<div class="production">
  <h2><a href="http://test-master01.build.mozilla.org:8012/buildslaves?no_builders=1">Production</a></h2>
  <p><small>
  <table>
    <tr><th></th>
        <th colspan="3">Status</th>
        <th></th>
        <th colspan="2">%% (%(percDays)d days)</th>
        <th colspan="3"></th>
    </tr>
    <tr><th>ID</th>
        <th>Tegra</th>
        <th>CP</th>
        <th>BS</th>
        <th>Msg</th>
        <th>Online</th>
        <th>Active</th>
        <th>Foopy</th>
        <th>PDU</th>
        <th>active bar</th>
    </tr>
"""
productionEntry = """  <tr>
    <td><a href="%(production)s/buildslaves/%(tegra)s">%(tegra)s</a></td>
    <td align="center">%(sTegra)s</td>
    <td align="center">%(sClientproxy)s</td>
    <td align="center">%(sSlave)s</td>
    <td>%(msg)s</td>
    <td align="right"><a href="%(tegra)s_status.log" title="%(percOnlineHover)s">%(percOnline)s</a></td>
    <td align="right"><a href="%(tegra)s_status.log" title="%(percActiveHover)s">%(percActive)s</a></td>
    <td><a href="%(foopyLink)s">%(foopy)s</a></td>
    <td><a href="%(pdu)s">%(pduID)s</a></td>
    <td><a href="%(tegra)s_status.log" title="%(lastActive)s">%(activeBar)s</a></td>
  </tr>
"""
productionFooter = """  </table>
</div>
"""
stagingHeader = """<div class="staging">
  <h2><a href="http://bm-foopy.build.mozilla.org:8012/buildslaves?no_builders=1">Staging</a></h2>
  <table>
    <tr><th></th>
        <th colspan="3">Status</th>
        <th></th>
        <th colspan="2">%% (%(percDays)d days)</th>
        <th colspan="3"></th>
    </tr>
    <tr><th>ID</th>
        <th>Tegra</th>
        <th>CP</th>
        <th>BS</th>
        <th>Msg</th>
        <th>Online</th>
        <th>Active</th>
        <th>Foopy</th>
        <th>PDU</th>
        <th>active bar</th>
    </tr>
"""
stagingEntry = """  <tr>
    <td><a href="%(staging)s/buildslaves/%(tegra)s">%(tegra)s</a></td>
    <td align="center">%(sTegra)s</td>
    <td align="center">%(sClientproxy)s</td>
    <td align="center">%(sSlave)s</td>
    <td>%(msg)s</td>
    <td align="right"><a href="%(tegra)s_status.log" title="%(percOnlineHover)s">%(percOnline)s</a></td>
    <td align="right"><a href="%(tegra)s_status.log" title="%(percActiveHover)s">%(percActive)s</a></td>
    <td><a href="%(foopyLink)s">%(foopy)s</a></td>
    <td><a href="%(pdu)s">PDU %(pduID)s</a></td>
    <td><a href="%(tegra)s_status.log" title="%(lastActive)s">%(activeBar)s</a></td>
  </tr>
"""
stagingFooter = """</table>
</div>
"""

def pduLookup(tegraID):
    tegra = tegraID.split('-')[1]
    for pdu in pdus:
        if tegra in pdus[pdu]:
            return pdu
    return "0"


oProduction = ''
oStaging    = ''

dStart   = None
dEnd     = None
dToday   = datetime.datetime.today()
percDays = 7

nProduction = { 'total':   0,
                'online':  0,
                'offline': 0,
                'active':  0,
              }
nStaging =    { 'total':   0,
                'online':  0,
                'offline': 0,
                'active':  0,
              }

for foopy in foopies:
    tegras = json.load(open(os.path.join(htmlDir, 'tegra_status-%s.txt' % foopy)))

    for tegra in tegras:
        # {
        #     "msg": "error.flg [Remote Device Error: devRoot from devicemanager [None] is not correct] ",
        #     "master": "s",
        #     "sClientproxy": "active",
        #     "tegra": "tegra-031",
        #     "time": "18:30:02",
        #     "date": "2011-04-21",
        #     "sTegra": "online",
        #     "sSlave": "OFFLINE"
        # },
        nOnline    = 0
        nActive    = 0
        nTotal     = 0.0
        n          = 0
        active     = []
        lastActive = ''

        for line in open(os.path.join(htmlDir, '%s_status.log' % tegra['tegra'])).readlines():
            #2011-04-21 11:33:41 tegra-090 p  OFFLINE   active  OFFLINE :: error.flg [Remote Device Error: updateApp() call failed - exiting] 
            n += 1
            l  = line.split()
            d  = datetime.datetime.strptime('%s %s' % (l[0], l[1]), '%Y-%m-%d %H:%M:%S')
            dt = dToday - d
            if dt.days < percDays:
                nTotal += 1
                if l[4] == 'online':
                    nOnline += 1
                if l[6] == 'active':
                    nActive += 1
                    active.append('A')
                else:
                    active.append('_')
            if l[6] == 'active':
                lastActive = calculateLastActive(l[0], l[1], dt)

        dItem = datetime.datetime.strptime('%s%s' % (tegra['date'], tegra['time']), '%Y-%m-%d%H:%M:%S')

        if dStart is None or dItem < dStart:
            dStart = dItem
        if dEnd is None or dItem > dEnd:
            dEnd = dItem

        tegra['production'] = masters['production']
        tegra['staging']    = masters['staging']
        tegra['pduID']      = pduLookup(tegra['tegra'])
        tegra['pdu']        = 'http://pdu%s.build.mozilla.org/' % tegra['pduID']
        tegra['foopy']      = tegra['hostname'].split('.')[0]
        tegra['foopyLink']  = '%s:/builds/%s' % (tegra['hostname'], tegra['tegra'])
        tegra['activeBar']  = ''.join(active[-12:])
        tegra['lastActive'] = lastActive

        if nTotal > 0:
            tegra['percOnline']      = '%2.1f' % ((nOnline / nTotal) * 100)
            tegra['percOnlineHover'] = '%d Online for %d items' % (nOnline, nTotal)
            tegra['percActive']      = '%2.1f' % ((nActive / nTotal) * 100)
            tegra['percActiveHover'] = '%d Active for %d items' % (nActive, nTotal)
        else:
            tegra['percOnline']      = 'n/a',
            tegra['percOnlineHover'] = 'no data',
            tegra['percActive']      = 'n/a',
            tegra['percActiveHover'] = 'no data',

        if tegra['master'] == 'p':
            oProduction += productionEntry % tegra
            nProduction['total'] += 1
            if tegra['sTegra'].lower() == 'online':
                nProduction['online'] += 1
                if tegra['sSlave'].lower() == 'active':
                    nProduction['active'] += 1
            else:
                nProduction['offline'] += 1
        else:
            oStaging += stagingEntry % tegra
            nStaging['total'] += 1
            if tegra['sTegra'].lower() == 'online':
                nStaging['online'] += 1
                if tegra['sSlave'].lower() == 'active':
                    nStaging['active'] += 1
            else:
                nStaging['offline'] += 1

d = { 'dStart':            dStart,
      'dEnd':              dEnd,
      'percDays':          percDays,
      'productionOnline':  nProduction['online'],
      'productionOffline': nProduction['offline'],
      'productionActive':  nProduction['active'],
      'productionIdle':    nProduction['online'] - nProduction['active'],
      'productionTotal':   nProduction['total'],
      'stagingOnline':     nStaging['online'],
      'stagingOffline':    nStaging['offline'],
      'stagingActive':     nStaging['active'],
      'stagingIdle':       nStaging['online'] - nStaging['active'],
      'stagingTotal':      nStaging['total'],
      'totalOnline':       nProduction['online']  + nStaging['online'],
      'totalOffline':      nProduction['offline'] + nStaging['offline'],
      'totalActive':       nProduction['active']  + nStaging['active'],
      'totalTotal':        nProduction['total']   + nStaging['total'],
      'production':        masters['production'],
      'staging':           masters['staging'],
    }

h = open(os.path.join(htmlDir, htmlIndex), 'w+')
h.write(pageHeader % d)
h.write(productionHeader % d)
h.write(oProduction)
h.write(productionFooter % d)
h.write(stagingHeader % d)
h.write(oStaging)
h.write(stagingFooter % d)
h.write(pageFooter)
h.close()

