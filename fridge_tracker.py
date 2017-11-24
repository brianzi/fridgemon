import pandas
import glob
from collections import OrderedDict
from bokeh.plotting import figure, gridplot
import datetime
import bokeh

startdate = "17-11-17"

log_folder = "/home/brianzi/delft/tarja_log_html/Logs/"

folders_with_logs = [
    d for d in glob.glob(
        log_folder + "*")
    if d >= log_folder + startdate
]

temp_names_legends = {
    "CH1": "T 50K Flange",
    "CH2": "T 4K Flange",
    "CH5": "T Still",
    "CH6": "T MC"
}

temp_colors = {
    "T 50K Flange": "red",
    "T 4K Flange": "orange",
    "T Still": "green",
    "T MC": "blue"
}

pressure_names_cols = OrderedDict({
    "P VC": 5,
    "P Still": 11,
    "P Injection": 17,
    "P Circ. scroll": 23,
    "P dump": 29,
    "P aux. manifold": 35
})

pressure_colors = OrderedDict({
    "P VC": "blue",
    "P Still": "red",
    "P Injection": "orange",
    "P Circ. scroll": "yellow",
    "P dump": "black",
    "P aux. manifold": "violet"
})


flow_dfs = []
files = [glob.glob(d + "Flow*.log") for d in folders_with_logs]
for f in files:
    flow_dfs.append(pandas.read_csv(
        f, names=["date", "time", "Flow (mmol/s)"], parse_dates=[[0, 1]]))
df = pandas.concat(flow_dfs)
df = df.sort_values(by="date_time")
df = df.set_index("date_time")
flow_df = df


temps_dfs = []
for channelname, name in temp_names_legends.items():
    files = [glob.glob(d + "/{} *.log".format(channelname))
             for d in folders_with_logs]
    # files = glob.glob("**/*{} T*.log".format(channelname))
    dfs = []
    for f in files:
        dfs.append(pandas.read_csv(
            f, names=["date", "time", name], parse_dates=[[0, 1]]))
    df = pandas.concat(dfs)
    df = df.sort_values(by="date_time")
    df = df.set_index("date_time")
    temps_dfs.append(df)

whole_df_temp = pandas.concat(temps_dfs, axis=1)
whole_df_temp = pandas.concat(
    (whole_df_temp.iloc[:-200:30], whole_df_temp.iloc[-200:]))


# files = glob.glob("**/maxigauge*.log".format(channelname))
files = [glob.glob(d + "maxigauge*.log") for d in folders_with_logs]
dfs = []
for f in files:
    dfs.append(pandas.read_csv(f, header=None, parse_dates=[[0, 1]]))
df = pandas.concat(dfs)
df = df.set_index("0_1")
df.index.name = "Log Time"
df = df.sort_index()

whole_df_press = df[list(sorted(pressure_names_cols.values()))]
whole_df_press.columns = list(pressure_names_cols.keys())

whole_df_press = pandas.concat(
    (whole_df_press.iloc[:-200:30], whole_df_press.iloc[-200:]))

whole_df_press.index.name = "Log Time"
whole_df_temp.index.name = "Log Time"


# create a new plot with a title and axis labels
p1 = figure(
    title="Temperatures",
    x_axis_label='Time in Delft',
    y_axis_label='Temperature (K)',
    x_axis_type="datetime",
    y_axis_type="log")

# add a line renderer with legend and line thickness
for n in whole_df_temp:
    p1.circle(
        x=whole_df_temp.index,
        y=whole_df_temp[n],
        color=temp_colors[n],
        legend=n)

p2 = figure(
    title="Pressures",
    x_axis_label='Time in Delft',
    y_axis_label='Pressure (mbar)',
    x_axis_type="datetime",
    y_axis_type="log",
    x_range=p1.x_range)

for n in whole_df_press:
    p2.circle(
        whole_df_press.index,
        whole_df_press[n],
        legend=n,
        color=pressure_colors[n])


p = gridplot([[p1], [p2]])
script, div = bokeh.embed.components(p)

temp_table = whole_df_temp.iloc[-1:].to_html()
press_table = whole_df_press.iloc[-1:].to_html()

stylesheet = """
.dataframe table,th,td {
   border: 0px solid black;
}

.dataframe * {border-color: #c0c0c0 !important;}
.dataframe th{background: #eee;}
.dataframe td{text-align: right; min-width:5em;}
}"""

html = """
<html>
<link
    href="http://cdn.pydata.org/bokeh/release/bokeh-0.12.9.min.css"
    rel="stylesheet" type="text/css">
<link
    href="http://cdn.pydata.org/bokeh/release/bokeh-widgets-0.12.9.min.css"
    rel="stylesheet" type="text/css">
<link
    href="http://cdn.pydata.org/bokeh/release/bokeh-tables-0.12.9.min.css"
    rel="stylesheet" type="text/css">

<script src="http://cdn.pydata.org/bokeh/release/bokeh-0.12.9.min.js"></script>
<script src="http://cdn.pydata.org/bokeh/release/bokeh-widgets-0.12.9.min.js"></script>
<script src="http://cdn.pydata.org/bokeh/release/bokeh-tables-0.12.9.min.js"></script>

<style>
{stylesheet}
</style>
<title>
Bluefors Fridge Tracker
</title>
{data_script}
<body>
<h1> Bluefors Fridge Tracker </h1>
Last update: {date_now}
<h4>Last Temperatures</h4>
{temp_table}
<h4>Last Pressures</h4>
{press_table}
<h4>Last Flow</h4>
{flow_table}
<h4>Plot</h4>
{div}
</body>
</html>
""".format(data_script=script,
           stylesheet=stylesheet,
           div=div,
           temp_table=temp_table,
           flow_table=flow_df[-1:].to_html(),
           press_table=press_table,
           date_now=datetime.datetime.now())


with open("index.html", "w") as f:
    f.write(html)
