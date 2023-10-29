#! /usr/bin/env python3

import sys
from datetime import datetime
from functools import total_ordering

if len(sys.argv) != 2:
    print('Call this script with the path to the collected log file as an argument!')
    sys.exit(1)

parsingErrors = 0

collect_data = False
data = {}
# data = {
#    ASN: {
#       net: {
#           function: [
#               [start, end, duration], [start, end, duration], …
#            ]
#        }
#    }

simpledata = {}
# simpledata = {
#   function: {
#       data: [start, end, duration], …
#       min: x,
#       max: y
#   }
# }

with open(sys.argv[1], "r") as f:
    for line in f.readlines():
        # 2023-10-27T12:03:09.472957+0000 victim bird@globepeer-ipv4[618]: TIMELOG;asn;cidr_net;2_nexthop_check;START
        line = line.lstrip(" ").rstrip("\n")
        time = line.split(" ")[0]
        line = line.split(": ")[1]
        if not line.startswith("TIMELOG;"):
            continue

        try:
            line = line.rstrip("\n").split(";")
            peerasn = line[1]
            net = line[2]
            fnct = line[3]
            start = (line[4] == 'START')
        except:
            parsingErrors += 1
            continue

        if collect_data:
            if peerasn not in data.keys():
                data[peerasn] = {}
            if net not in data[peerasn].keys():
                data[peerasn][net] = {}
            if fnct not in data[peerasn][net].keys():
                data[peerasn][net][fnct] = []

        if fnct not in simpledata.keys():
            simpledata[fnct] = {'data':[], 'min': None, 'max': None}

        if start:
            if collect_data:
                data[peerasn][net][fnct].append( [time,None,None] )
            simpledata[fnct]['data'].append( [time,None,None] )
        else:
            try:
                if collect_data:
                    element = data[peerasn][net][fnct][ len(data[peerasn][net][fnct])-1 ]
                    element[1] = time
                    start = datetime.strptime(element[0], '%Y-%m-%dT%H:%M:%S.%f%z')
                    diff = (datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%f%z') - start).total_seconds()*1000*1000
                    element[2] = diff
                    data[peerasn][net][fnct][ len(data[peerasn][net][fnct])-1 ] = element

                element = simpledata[fnct]['data'][ len(simpledata[fnct]['data'])-1 ]
                element[1] = time
                start = datetime.strptime(element[0], '%Y-%m-%dT%H:%M:%S.%f%z')
                diff = (datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%f%z') - start).total_seconds()*1000*1000
                element[2] = diff
                simpledata[fnct]['data'][ len(simpledata[fnct]['data'])-1] = element

                if simpledata[fnct]['min'] is None or diff < simpledata[fnct]['min']:
                    simpledata[fnct]['min'] = diff
                if simpledata[fnct]['max'] is None or diff > simpledata[fnct]['max']:
                    simpledata[fnct]['max'] = diff

            except IndexError as e:
                parsingErrors += 1

## PREPARE DATA FOR PLOT
## get for each function: min, avg, max
## sort functions based on avg, grouped by import and export
@total_ordering
class Element:
    lower = None
    avg = None
    upper = None
    name = None

    def __init__(self, name, lower, avg, upper):
        self.name = name
        self.lower = lower
        self.avg = avg
        self.upper = upper

    def __repr__(self):
        return f"({self.lower} - {self.avg} - {self.upper})"

    def __eq__(self, obj):
        return (self.avg == obj.avg)

    def __lt__(self, obj):
        return (self.avg < obj.avg)

imports = []
exports = []
for fnct in simpledata.keys():
    lower = simpledata[fnct]['min']
    upper = simpledata[fnct]['min']
    avg = 0
    avg_count = 0
    for entry in simpledata[fnct]['data']:
        if entry[2] is None:
            continue
        avg += entry[2]
        avg_count += 1

    if avg_count > 0:
        avg = avg / avg_count

        element = Element(fnct, lower, avg, upper)
        if fnct[0] == 'i':
            imports.append(element)
        else:
            exports.append(element)
    else:
        print("Could not calculate avg for function "+fnct)

imports = sorted(imports)
exports = sorted(exports)

## PLOT DATA
import matplotlib.pyplot as plt
import numpy as np

# example data
x = [7, 12, 5]
y = ["f1", "f2", "f3"]
xerror = [[0.1, 1.5, 0.5], [0.6, 0.2, 3]]

# get data, prepare for plot
x = []
y = []
xerror = [[], []]
for e in imports:
    y.append(e.name)
    x.append(e.avg)
    xerror[0].append(e.lower)
    xerror[1].append(e.upper)

x1 = []
y1 = []
x1error = [[], []]
for e in exports:
    y1.append(e.name)
    x1.append(e.avg)
    x1error[0].append(e.lower)
    x1error[1].append(e.upper)



# show imports plot
cm = 1/2.54
fig = plt.figure(figsize=(20*cm, 7*cm))
plt.errorbar(x, y, xerr=xerror, fmt='.')
plt.xlabel('evaluation time [us]')
plt.tight_layout()
plt.show()

# show exports plot
fig = plt.figure(figsize=(20*cm, 7*cm))
plt.errorbar(x1, y1, xerr=x1error, fmt='.')
#plt.xscale('log')
plt.xlabel('evaluation time [us]')
plt.tight_layout()
plt.show()


## FINAL OUTPUT OF POTENTIAL ERRORS FOR DATA VALIDATION
if parsingErrors > 0:
    print(f"FOUND {parsingErrors} ERRORS WHILE PARSING LOG.")


