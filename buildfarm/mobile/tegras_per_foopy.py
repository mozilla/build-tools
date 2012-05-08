import json
f = open('tegras.json', 'r')
j = json.load(f)
foopies = {}
nofoopy = {}
for key in j:
   foopy = j[key]["foopy"]
   if foopy != "None":
       if foopies.has_key(foopy):
           foopies[foopy].append(key)
       else:
           foopies[foopy] = [key]
   else:
       if j[key].has_key("_comment"):
           newkey = j[key]["_comment"]
       else:
           newkey = "None"
       if nofoopy.has_key(newkey):
           nofoopy[newkey] += 1
       else:
           nofoopy[newkey] = 1

prod_tegras = 0
prod_foopies = 0
prod_text = []
stage_text = []
stage_tegras = 0
stage_foopies = 0
for foopy in sorted(foopies.keys()):
   # exclude staging foopies
   if not foopy in ("foopy05", "foopy06"):
       prod_text.append("  %s contains %s tegras" % (foopy, len(foopies[foopy])))
       prod_tegras += len(foopies[foopy])
       prod_foopies += 1
   if foopy in ("foopy05", "foopy06"):
      stage_text.append("  %s contains %s tegras" % (foopy, len(foopies[foopy])))
      stage_tegras += len(foopies[foopy])
      stage_foopies += 1

unassigned_text = []
for unassigned in sorted(nofoopy.keys()):
   if unassigned is "None":
      unassigned_text.append("%4ld (With no Comment)" % nofoopy[unassigned])
   else:
      unassigned_text.append("%4ld With Comment: %s" % (nofoopy[unassigned], unassigned))

print "PRODUCTION:"
print "\n".join(prod_text)
print "We have %s tegras in %s foopies which means a ratio of %s tegras per foopy" % \
      (prod_tegras, prod_foopies, prod_tegras/prod_foopies)
print
print "STAGING:"
print "\n".join(stage_text)
print "We have %s tegras in %s foopies which means a ratio of %s tegras per foopy" % \
      (stage_tegras, stage_foopies, stage_tegras/stage_foopies)
print
print "UNASSIGNED"
print "\n".join(unassigned_text)
