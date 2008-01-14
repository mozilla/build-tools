<%def name="span(value, title)"><span title="${title}">${value}</span></%def>
<%def name="format(json, base='')">
<div class="json-child">
% if 'children' in json:
  % for label, child in json['children']:
    % if 'value' in child and ('missingFile' in child['value'] or 'obsoleteFile' in child['value']):
<div class="${child['value'].keys()[0]}">${span(label, base + label)}</div>
    % else:
<div class="filepath">${span(label, base + label)}</div>
      % if 'value' in child:
<%
v = child['value']
errors = ('error' in v and v['error']) or []
missings = ('missingEntity' in v and v['missingEntity']) or []
obsoletes = ('obsoleteEntity' in v and v ['obsoleteEntity']) or []
entities = missings + obsoletes
entities.sort()
cls = ['obsolete','missing']
out = [('error', e) for e in errors] + [(cls[e in missings], e) for e in entities]
%>
        % if len(out):
<div class="diff">
          % for cls, entity in out:
  <div class="${cls}">${entity}</div>
          % endfor
</div>
        % endif
      % endif
      % if 'children' in child:
${format(child, base + label + '/')}
      % endif
    % endif
  % endfor
% endif
</div>
</%def>
<html>
<head>
<title>Comparison</title>
<style type="text/css">
.json-child {
  padding-left:1em;
}
.diff {
  padding-left:.5em;
  margin-left:1em;
  border:solid black 1px;
}
.obsoleteFile {
  text-decoration: line-through;
  color: grey;
}
.error {
  color: red;
  font-weight: bolder;
}
.obsolete {
  text-decoration: line-through;
  color: grey;
}
#stats {
  background-color: white;
  cell-padding:0px;
  border-spacing:0px;
  padding: 3px;
}
.status {
  height: 2ex;
  margin:0px;
  padding:0px;
  border:0px
}
.changed {background-color: green;}
.unchanged {background-color: grey;}
.missingkeys {background-color: red;}

</style>
</head>
<body>
<h1>Comparison</h1>
<p id="stats">
<%
total = sum(summary[k] for k in ['changed','unchanged','missing','missingInFiles'] if k in summary)
width = 300
%>
${summary['completion']}% changed, ignoring ${summary['keys']} keys
<table class="stats">
<tr>
<td title="changed" class="status changed" width="${width*summary['changed']/total}px">
<td title="missing" class="status missingkeys" width="${width*summary['missing']/total}px">
<td title="missing in new files" class="status missingkeys" width="${width*summary['missingInFiles']/total}px">
<td title="unchanged" class="status unchanged" width="${width*summary['unchanged']/total}px">
</tr>
</table>
</p>
<p id="blurb">
Below you see the files and localizable strings missing and obsolete. The obsolete ones are striked through and grey. The data is organized hierarchically, the full path for a file is available as an tooltip.
</p>
<p id="output">
${format(result)}
</p>
</body>
</html>
