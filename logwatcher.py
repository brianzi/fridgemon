#!/usr/bin/env python

"""
R,eal time log files watcher supporting log rotation.

Author: Giampaolo Rodola' <g.rodola [AT] gmail [DOT] com>
License: MIT
"""

import os
import time
import errno
import stat
import collections
import datetime
import json
import requests


class LogWatcher(object):
    """Looks for changes in all files of a directory.
    This is useful for watching log file changes in real-time.
    It also supports files rotation.

    Example:

    >>> def callback(filename, lines):
    ...     print filename, lines
    ...
    >>> l = LogWatcher("/var/log/", callback)
    >>> l.loop()
    """

    def __init__(self, folder, callback, extensions=["log"], tail_lines=0):
        """Arguments:

        (str) @folder:
            the folder to watch

        (callable) @callback:
            a function which is called every time a new line in a
            file being watched is found;
            this is called with "filename" and "lines" arguments.

        (list) @extensions:
            only watch files with these extensions

        (int) @tail_lines:
            read last N lines from files being watched before starting
        """
        self.files_map = {}
        self.callback = callback
        self.folder = os.path.realpath(folder)
        self.extensions = extensions
        assert os.path.isdir(self.folder), "%s does not exists" \
            % self.folder
        assert isinstance(callback, collections.Callable)
        self.update_files()
        # The first time we run the script we move all file markers at EOF.
        # In case of files created afterwards we don't do this.
        for id, file in self.files_map.items():
            file.seek(os.path.getsize(file.name))  # EOF
            if tail_lines:
                lines = self.tail(file.name, tail_lines)
                if lines:
                    self.callback(file.name, lines)

    def __del__(self):
        self.close()

    def loop(self, interval=0.1, async=False):
        """Start the loop.
        If async is True make one loop then return.
        """
        while True:
            self.update_files()
            for fid, file in list(self.files_map.items()):
                self.readfile(file)
            if async:
                return
            time.sleep(interval)

    def log(self, line):
        """Log when a file is un/watched"""
        print(line)

    def listdir(self):
        """List directory and filter files by extension.
        You may want to override this to add extra logic or
        globbling support.
        """
        ls = os.listdir(self.folder)
        import glob

        ls = glob.glob(self.folder + "/**/*")
        if self.extensions:
            return [x for x in ls if os.path.splitext(x)[1][1:]
                    in self.extensions]
        else:
            return ls

    @staticmethod
    def tail(fname, window):
        """Read last N lines from file fname."""
        try:
            f = open(fname, 'r')
        except IOError as err:
            if err.errno == errno.ENOENT:
                return []
            else:
                raise
        else:
            BUFSIZ = 1024
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            block = -1
            data = ""
            exit = False
            while not exit:
                step = (block * BUFSIZ)
                if abs(step) >= fsize:
                    f.seek(0)
                    exit = True
                else:
                    f.seek(fsize + step, 0)
                data = f.read().strip()
                if data.count('\n') > window:
                    break
                else:
                    block -= 1
            return data.splitlines()[-window:]

    def update_files(self):
        ls = []
        for name in self.listdir():
            absname = os.path.realpath(os.path.join(self.folder, name))
            try:
                st = os.stat(absname)
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
            else:
                if not stat.S_ISREG(st.st_mode):
                    continue
                fid = self.get_file_id(st)
                ls.append((fid, absname))

        # check existent files
        for fid, file in list(self.files_map.items()):
            try:
                st = os.stat(file.name)
            except EnvironmentError as err:
                if err.errno == errno.ENOENT:
                    self.unwatch(file, fid)
                else:
                    raise
            else:
                if fid != self.get_file_id(st):
                    # same name but different file (rotation); reload it.
                    self.unwatch(file, fid)
                    self.watch(file.name)

        # add new ones
        for fid, fname in ls:
            if fid not in self.files_map:
                self.watch(fname)

    def readfile(self, file):
        lines = file.readlines()
        if lines:
            self.callback(file.name, lines)

    def watch(self, fname):
        try:
            file = open(fname, "r")
            fid = self.get_file_id(os.stat(fname))
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            self.log("watching logfile %s" % fname)
            self.files_map[fid] = file

    def unwatch(self, file, fid):
        # file no longer exists; if it has been renamed
        # try to read it for the last time in case the
        # log rotator has written something in it.
        lines = self.readfile(file)
        self.log("un-watching logfile %s" % file.name)
        del self.files_map[fid]
        if lines:
            self.callback(file.name, lines)

    @staticmethod
    def get_file_id(st):
        return "%xg%x" % (st.st_dev, st.st_ino)

    def close(self):
        for id, file in self.files_map.items():
            file.close()
        self.files_map.clear()


class LogLineParserBase:

    def __init__(self, prefix="", fields=None):
        self.prefix = prefix
        self.last_values = {}

        if fields is None:
            self.fields = {}
        else:
            self.fields = fields

        self._values = {}
        self.updates = {}

    def parse_line(self, line):
        date, time, *items = [i.strip() for i in line.split(",")]
        dt = datetime.datetime.strptime(
            date + " " + time, "%d-%m-%y %H:%M:%S")

        self._values['time'] = dt

        self.parse_items(items)

        # compare last values and new values

        self.updates = {}

        for k in self._values:
            if (k not in self.last_values or
                    self._values[k] != self.last_values[k]):
                self.updates[k] = self._values[k]

        self.last_values = self._values.copy()

        return self.updates

    def parse_field(self, name, raw_value):
        if name in self.fields:
            parser = self.fields[name][3]
            pp_unit = self.fields[name][2]
            pp_name = self.fields[name][1]
            value = parser(raw_value)
            if self.fields[name][0] is not None:
                name = self.fields[name][0]
        else:
            value = raw_value
            pp_unit = ""
            pp_name = name

        self._values[self.prefix + name] = (pp_name, pp_unit, value)

    def pretty_print_status(self, only_updates=True):
        if only_updates:
            to_print = self.updates
        else:
            to_print = self.last_values

        for k, v in sorted(to_print.items(), key=str):
            if k == 'time':
                continue
            pp_name, pp_unit, value = v

            time = self.last_values['time']
            print("{}: [{}] {} = {} {}".format(
                time, k, pp_name, value, pp_unit))

    def parse_items(self, items):
        """
        parse the rest of the items and populate _values
        accordingly.
        """
        raise NotImplementedError


# nodename, human readeable name, unit, parser

_default_temp_fields_CH1 = {
    0: ("t1_50k", "Temperature 50K Flange", "K", float),
}

_default_temp_fields_CH2 = {
    0: ("t2_4k", "Temperature 4K Flange", "K", float),
}

_default_temp_fields_CH5 = {
    0: ("t5_still", "Temperature Still", "K", float),
}

_default_temp_fields_CH6 = {
    0: ("t6_mc", "Temperature MC", "K", float),
}

_default_heater_fields = {
    "a1_r_htr": (None, "Resistance warm-up heater", "Ohm", float),
    "a1_r_lead": (None, "Resistance warm-up heater leads", "Ohm", float),
    "a1_u": (None, "Voltage warm-up heater", "V", float),
    "a2_r_htr": (None, "Resistance still heater", "Ohm", float),
    "a2_r_lead": (None, "Resistance still heater leads", "Ohm", float),
    "a2_u": (None, "Voltage still heater", "V", float),
    # heater range meaning
    # 0 = off, 1 = 31.6 μA, 2 = 100 μA, 3 = 316 μA,
    # 4 = 1.00 mA, 5 = 3.16 mA, 6 = 10.0 mA, 7 = 31.6 mA, 8 = 100 mA
    "htr": (None, "Sample heater current fraction", "", float),
    "htr_range": (None, "Sample heater current range", "", int),
}

_default_flowmeter_fields = {
    0: ("flow", "Flow", "mmol/s", float)
}

_default_pressure_fields = {
    3: ("p1", "Pressure VC (P1)", "mbar", float),
    9: ("p2", "Pressure Still (P2)", "mbar", float),
    15: ("p3", "Pressure Circulation scroll (P3)", "mbar", float),
    21: ("p4", "Pressure Injection (P4)", "mbar", float),
    27: ("p5", "Pressure Mixture Dump (P5)", "mbar", float),
    33: ("p6", "Pressure Aux Manifold (P6)", "mbar", float),
}

_default_status_fields = {
    'cpacurrent': (None, "Compressor 1 current", "A", float),
    'cpacurrent_2': (None, "Compressor 2 current", "A", float),
    'cpadp': (None, "Compressor 1 dp", "bar", float),
    'cpadp_2': (None, "Compressor 2 dp", "bar", float),
    'cpaerr': (None, "Compressor 1 Error", None, int),
    'cpaerr_2': (None, "Compressor 2 Error", None, int),
    'cpahours': (None, "Compressor 1 Runtime", "h", float),
    'cpahours_2': (None, "Compressor 2 Runtime", "h", float),
    'cpahp': (None, "Compressor 1 high pressure", "bar", float),
    'cpahp_2': (None, "Compressor 2 high pressure", "psi", float),
    'cpahpa': (None, "Compressor 1 avg. high pressure", "bar", float),
    'cpahpa_2': (None, "Compressor 2 avg. high pressure", "psi", float),
    'cpalp': (None, "Compressor 1 high pressure", "bar", float),
    'cpalp_2': (None, "Compressor 2 high pressure", "psi", float),
    'cpalpa': (None, "Compressor 1 avg. high pressure", "bar", float),
    'cpalpa_2': (None, "Compressor 2 avg. high pressure", "bar", float),
    'cpamodel': (None, "Compressor 1 model", None, int),
    'cpamodel_2': (None, "Compressor 2 model", None, int),
    'cpapscale': (None, "Compressor 1 scale", None, int),
    'cpapscale_2': (None, "Compressor 2 scale", None, int),
    'cparun': (None, "Compressor 1 running", None, bool),
    'cparun_2': (None, "Compressor 2 running", None, bool),
    'cpasn': (None, "Compressor 1 serial number", None, int),
    'cpasn_2': (None, "Compressor 2 serial number", None, int),
    'cpastate': (None, "Compressor 1 state", None, int),
    'cpastate_2': (None, "Compressor 2 state", None, int),
    'cpatemph': (None, "Compressor 1 helium temperature", "C", float),
    'cpatemph_2': (None, "Compressor 2 helium temperature", "C", int),
    'cpatempo': (None, "Compressor 1 oil temperature", "C", float),
    'cpatempo_2': (None, "Compressor 2 oil temperature", "C", float),
    'cpatempwi': (None, "Compressor 1 cooling water in temperature", "C", float),
    'cpatempwi_2': (None, "Compressor 2 cooling water in temperature", "C", float),
    'cpatempwo': (None, "Compressor 1 cooling water out temperature", "C", float),
    'cpatempwo_2': (None, "Compressor 2 cooling water out temperature", "C", float),
    'cpatscale': (None, "Compressor 1 temperature scale", None, int),
    'cpatscale_2': (None, "Compressor 2 temperature scale", None, int),
    'cpawarn': (None, "Compressor 1 warning", None, int),
    'cpawarn_2': (None, "Compressor 2 warning", None, int),
    'ctrl_pres': (None, "Cabinet pressure check", None, bool),
    'tc400commerr': (None, "Turbo 1 communication error", None, bool),
    'tc400commerr_2': (None, "Turbo 2 communication error", None, bool),
    'tc400errorcode': (None, "Turbo 1 error code", None, int),
    'tc400errorcode_2': (None, "Turbo 2 error code", None, int),
    'tc400ovtempelec': (None, "Turbo 1 electronics hot", None, bool),
    'tc400ovtempelec_2': (None, "Turbo 2 electronics hot", None, bool),
    'tc400ovtemppump': (None, "Turbo 1 pump hot", None, bool),
    'tc400ovtemppump_2': (None, "Turbo 2 pump hot", None, bool),
    'tc400pumpaccel': (None, "Turbo 1 accelerating", None, bool),
    'tc400pumpaccel_2': (None, "Turbo 2 accelerating", None, bool),
    'tc400setspdatt': (None, "Turbo 1 speed attained", None, bool),
    'tc400setspdatt_2': (None, "Turbo 2 speed attained", None, bool),
}


class StatusParser(LogLineParserBase):
    def parse_items(self, items):
        while items:
            k, v, *items = items
            self.parse_field(k, float(v))


class FieldsParser(LogLineParserBase):
    def parse_items(self, items):
        for k in self.fields:
            if isinstance(k, int):
                self.parse_field(k, float(items[k]))


if __name__ == '__main__':
    # import zlib
    # import base64
    # import time
    parsers = [
        ("CH1 T", FieldsParser("bluefors/", _default_temp_fields_CH1)),
        ("CH2 T", FieldsParser("bluefors/", _default_temp_fields_CH2)),
        ("CH5 T", FieldsParser("bluefors/", _default_temp_fields_CH5)),
        ("CH6 T", FieldsParser("bluefors/", _default_temp_fields_CH6)),
        ("maxigauge", FieldsParser("bluefors/", _default_pressure_fields)),
        ("Flowmeter", FieldsParser("bluefors/", _default_flowmeter_fields)),
        ("heaters", StatusParser("bluefors/", _default_heater_fields)),
        ("Status", StatusParser("bluefors/", _default_status_fields)),
    ]

    def callback(filename, lines):
        for n, p in parsers:
            if n in filename:
                for l in lines:
                    p.parse_line(l)
                    p.pretty_print_status()

        # publish the update
        all_updates = {}
        for n, p in parsers:
            all_updates.update(p.updates)

        r = requests.post(
            "http://localhost:5000/update",
            data=json.dumps(all_updates, default=str))
        print(r.status_code)
        print(r.json())

    l = LogWatcher("./Logs/", callback, tail_lines=5)
    l.loop()
