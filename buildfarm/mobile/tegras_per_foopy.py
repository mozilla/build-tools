import json
f = open('tegras.json', 'r')
j = json.load(f)
foopies = {}
for key in j:
   foopy = j[key]["foopy"]
   if foopies.has_key(foopy):
       foopies[foopy].append(key)
   else:
       foopies[foopy] = [key] 

prod_tegras = 0
prod_foopies = 0
for foopy in sorted(foopies.keys()):
   # exclude staging foopies
   if not foopy in ("foopy05", "foopy06"):
       print "%s contains %s tegras" % (foopy, len(foopies[foopy]))
       prod_tegras += len(foopies[foopy])
       prod_foopies += 1

print "We have %s tegras in %s foopies which means a ratio of %s tegras per foopy" % \
      (prod_tegras, prod_foopies, prod_tegras/prod_foopies)
