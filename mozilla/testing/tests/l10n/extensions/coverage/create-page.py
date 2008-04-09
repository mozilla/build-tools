import sys

listtxt = sys.argv[1]

head = '''<html>
<head>
 <style type="text/css">
 .cell {
   float: left;
   padding: 10px;
   marging: 0px;
 }
 </style>
</head>
<body>
 <div>Screenshots</div>
 <div id="shots">
 '''
tmpl = '''  <div class="cell"><img src="%(src)s" alt="%(chrome)s" title="%(chrome)s" class="shot"></div>
'''

footer = ''' </div>
</body>
</html>
'''

sys.stdout.write(head)

for line in open(listtxt).read().split():
  ids, chrome = line.split(',')
  sys.stdout.write(tmpl % dict(src = ids + '_win.png', chrome = chrome))

sys.stdout.write(footer)
