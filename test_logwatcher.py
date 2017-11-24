import logwatcher
import glob


# fn = "./Logs/17-11-18/Status_17-11-18.log"

# p = logwatcher.StatusParser(fn, fields=logwatcher._default_status_fields)

# with open(fn, "r") as f:
# for line in f.readlines():
# p.parse_line(line)
# p.pretty_print_status(only_updates=False)


# fns = glob.glob("./Logs/**/maxigauge*.log")

# for fn in fns[:1]:

# p = logwatcher.FieldsParser(fn,
# fields=logwatcher._default_pressure_fields)

# with open(fn, "r") as f:
# for line in f.readlines():
# p.parse_line(line)
# p.pretty_print_status(only_updates=False)


fns = glob.glob("./Logs/**/Flow*.log")
fields = logwatcher._default_flowmeter_fields


fns = glob.glob("./Logs/**/heaters*24*.log")
fields = logwatcher._default_heater_fields

for fn in fns:

    p = logwatcher.StatusParser(fn, fields=fields)

    with open(fn, "r") as f:
        for line in f.readlines():
            p.parse_line(line)
            p.pretty_print_status(only_updates=False)
