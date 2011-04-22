#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import json
import datetime


htmlDir   = '/var/www/tegras'
htmlIndex = 'index.html'
foopies   = ['foopy01', 'foopy02', 'foopy03', 'foopy04']
masters   = { 'production': "http://test-master01.build.mozilla.org:8012",
              'staging':    "http://bm-foopy.build.mozilla.org:8012",
            }
pdus =      { "1": ( "057", "061", "065", "069", "073", "077", "081", "085",
                     "089", "093", "058", "062", "066", "070", "074", "078",
                     "082", "086", "090",
                   ),
              "2": ( "055", "059", "063", "067", "071", "075", "079",
                     "083", "087", "091", "056", "060", "064", "068",
                     "072", "076", "080", "084", "088", "092",
                   )
            }

pageHeader = """<html>
<head>
    <title>Tegra Dashboard v0.1</title>
</head>
<body>
<div class="header">
  <h1>Tegra Dashboard</h1>
  <p><small>From %(dStart)s to %(dEnd)s</small></p>
  <table>
    <tr><th></th><th>Online</th><th>Active</th><th>Total</th></tr>
    <tr><th>Production</th><td>%(productionOnline)d</td><td>%(productionActive)d</td><td>%(productionTotal)d</td></tr>
    <tr><th>Staging</th><td>%(stagingOnline)d</td><td>%(stagingActive)d</td><td>%(stagingTotal)d</td></tr>
    <tr><th>Total</th><td>%(totalOnline)d</td><td>%(totalActive)d</td><td>%(totalTotal)d</td></tr>
  </table>
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
    <colgroup span="3" align="center"></colgroup>
    <colgroup align="left"></colgroup>
    <tr><th rowspan="2">ID</th>
        <th colspan="3">Status</th>
        <th colspan="2"></th></tr>
    <tr><th>Tegra</th>
        <th>CP</th>
        <th>BS</th>
        <th>Msg</th>
        <th>Foopy</th>
        <th>PDU</th>
        <th>Log</th></tr>
"""
productionEntry = """  <tr>
    <td><a href="%(staging)s/buildslaves/%(tegra)s">%(tegra)s</a></td>
    <td>%(sTegra)s</td>
    <td>%(sClientproxy)s</td>
    <td>%(sSlave)s</td>
    <td>%(msg)s</td>
    <td><a href="%(foopyLink)s">%(foopy)s</a></td>
    <td><a href="%(pdu)s">PDU %(pduID)s</a></td>
    <td><a href="%(tegra)s_status.log">%(tegra)s_status.log</a></tr>
"""
productionFooter = """  </table>
</div>
"""
stagingHeader = """<div class="staging">
<h2><a href="http://bm-foopy.build.mozilla.org:8012/buildslaves?no_builders=1">staging</a></h2>
<table>
  <colgroup span="3" align="center"></colgroup>
  <colgroup align="left"></colgroup>
  <tr><th rowspan="2">ID</th>
      <th colspan="3">Status</th>
      <th colspan="3"></th></tr>
  <tr><th>Tegra</th>
      <th>CP</th>
      <th>BS</th>
      <th>Msg</th>
      <th>Foopy</th>
      <th>PDU</th>
      <th>Log</th></tr>
"""
stagingEntry = """  <tr>
    <td><a href="%(production)s/buildslaves/%(tegra)s">%(tegra)s</a></td>
    <td>%(sTegra)s</td>
    <td>%(sClientproxy)s</td>
    <td>%(sSlave)s</td>
    <td>%(msg)s</td>
    <td><a href="%(foopyLink)s">%(foopy)s</a></td>
    <td><a href="%(pdu)s">PDU %(pduID)s</a></td>
    <td><a href="%(tegra)s_status.log">%(tegra)s_status.log</a></tr>
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

dStart = None
dEnd   = None

nProduction = { 'total':  0,
                'online': 0,
                'active': 0,
              }
nStaging =    { 'total':  0,
                'online': 0,
                'active': 0,
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

        if tegra['master'] == 'p':
            oProduction += productionEntry % tegra
            nProduction['total'] += 1
            if tegra['sTegra'].lower() == 'online':
                nProduction['online'] += 1
            if tegra['sSlave'].lower() == 'active':
                nProduction['active'] += 1
        else:
            oStaging += stagingEntry % tegra
            nStaging['total'] += 1
            if tegra['sTegra'].lower() == 'online':
                nStaging['online'] += 1
            if tegra['sSlave'].lower() == 'active':
                nStaging['active'] += 1

d = { 'dStart':           dStart,
      'dEnd':             dEnd,
      'productionOnline': nProduction['online'],
      'productionActive': nProduction['active'],
      'productionTotal':  nProduction['total'],
      'stagingOnline':    nStaging['online'],
      'stagingActive':    nStaging['active'],
      'stagingTotal':     nStaging['total'],
      'totalOnline':      nProduction['online'] + nStaging['online'],
      'totalActive':      nProduction['active'] + nStaging['active'],
      'totalTotal':       nProduction['total']  + nStaging['total'],
      'production':       masters['production'],
      'staging':          masters['staging'],
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

