<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<title>L10n stats [${locale}, ${app}, ${tree}]</title>
<script src="http://static.simile.mit.edu/timeplot/api/1.0/timeplot-api.js" 
             type="text/javascript"></script>
<script type="text/javascript">
var timeplot, timeGeometry;

function onLoad() {
  var eventSource = new Timeplot.DefaultEventSource();
  var eventSource2 = new Timeplot.DefaultEventSource();
  timeGeometry = new Timeplot.MagnifyingTimeGeometry({
    gridColor: new Timeplot.Color("#000000"),
    axisLabelsPlacement: "top"
  });

  var valueGeometry = new Timeplot.DefaultValueGeometry({
    gridColor: "#000000",
    min: 0,
    axisLabelsPlacement: 'left'
  });
  var valueGeometry2 = new Timeplot.DefaultValueGeometry({
    gridColor: "#000000",
    min: 0
  });
  var plotInfo = [
    Timeplot.createPlotInfo({
      id: "checkins",
      timeGeometry: timeGeometry,
      eventSource: eventSource2,
      lineColor: "blue"
    }),
    Timeplot.createPlotInfo({
      id: "unchanged",
      dataSource: new Timeplot.ColumnSource(eventSource,3),
      valueGeometry: valueGeometry2,
      timeGeometry: timeGeometry,      
      lineColor: "#cccccc",
      fillColor: "#cccccc",
      showValues: true
    }),
    Timeplot.createPlotInfo({
      id: "obsolete",
      dataSource: new Timeplot.ColumnSource(eventSource,2),
      valueGeometry: valueGeometry,
      timeGeometry: timeGeometry,      
      lineColor: "#000000",
      fillColor: "#808080",
      showValues: true
    }),
    Timeplot.createPlotInfo({
      id: "missing",
      dataSource: new Timeplot.ColumnSource(eventSource,1),
      valueGeometry: valueGeometry,
      timeGeometry: timeGeometry,      
      lineColor: "#ff0000",
      fillColor: "#cc8080",
      showValues: true
    })
  ];
            
  timeplot = Timeplot.create(document.getElementById("my-timeplot"), plotInfo);
  //timeplot.loadText("nl.txt", ",", eventSource);
  eventSource.loadText($('#txtData').text(), ',', String(document.location));
  //timeplot.loadXML("nl-events.xml", eventSource2);
  eventSource2.loadXML({documentElement:$('#events').children()[0]},
                       String(document.location));
  timeplot.repaint();    
}

var resizeTimerID = null;
function onResize() {
    if (resizeTimerID == null) {
        resizeTimerID = window.setTimeout(function() {
            resizeTimerID = null;
            timeplot.repaint();
        }, 100);
    }
}</script>
</head>
<body onload="onLoad();" onresize="onResize();">
<h1>Statistics for ${locale}, ${app}, ${tree}</h1>
<div id="my-timeplot" style="height: 400px;"></div>
<div class="legend" style="float:right">
  left scale:
  red area: missing<br>
  black line: obsolete<br>
  right scale, grey area: unchanged
</div>
<div id="txtData" style="display:none">
% for r in rows:
${"%(time)s,%(missing)d,%(obsolete)d,%(unchanged)d" % r}
% endfor
</div>
<div id="events" style="display:none">
${events.documentElement.toprettyxml()}</div>
</body>
</html>
