<html>
<head>
<title>Statistics</title>
<script src="http://static.simile.mit.edu/exhibit/api-2.0/exhibit-api.js?autoCreate=false" 
             type="text/javascript"></script>
<script type="text/javascript">
<%
from buildbotcustom.status.l10ndb import session, Active
actives = session.query(Active)
items = []
for a in actives:
  d = a.dict()
  d['type'] = 'Active'
  d['id'] = '/'.join(a.tuple())
  d['label'] = '%s, %s, %s' % (a.locale, a.app, a.tree)
  items.append(d)
import simplejson
%>

var data = ${simplejson.dumps(dict(items=items), sort_keys=True, indent=2)};

$(document).ready(function() {
  window.database = Exhibit.Database.create();
  window.database.loadData(data);
  window.exhibit = Exhibit.create();
  window.exhibit.configureFromDOM();
});
</script>
<style type="text/css">
.activelens {
  padding: 5px;
}
</style>
</head>
<body>
<h1>Statistics</h1>
<p>Specify the buildername, tree, app, and locale to get a plot, or follow one of the links below.</p>
<table id="picker" width="100%">
<tr valign="top">
<td><div ex:role="view" ex:viewClass="Thumbnail" ex:showAll="true"></div></td>
<td width="25%">
<div ex:role="facet" ex:expression=".app" ex:facetLabel="Application" ex:height="5em"></div>
<div ex:role="facet" ex:expression=".locale" ex:facetLabel="Locale"></div>
<div ex:role="facet" ex:expression=".tree" ex:facetLabel="Tree" ex:height="5em"></div>
<div ex:role="facet" ex:expression=".buildername" ex:facetLabel="Builder" ex:height="3em"></div>
</td>
</tr>
</table>
<div ex:role="lens">
<div class="activelens">
<a ex:href-subcontent="?buildername={{.buildername}}&tree={{.tree}}&app={{.app}}&locale={{.locale}}"
   ex:content=".label"></a>
</div>
</div>
</body>
</html>
