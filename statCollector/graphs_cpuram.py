#! /usr/bin/env python3

# GRAPH 1: System status: load, used mem, used swap
# GRAPH 2: Bird status: ps_cpu, ps_mem, established_sessions, received_pfx, received_withdraw

import sys
import matplotlib.pyplot as plt
from statistics import mean

def help():
    print('USAGE: graphs.py STATSFILE')
    print('Plot graphs for gathered statistics by statsCollector.')
    print('')
    print('STATSFILE      Path to file containing the collected statistics.')

if len(sys.argv) < 2:
    help()
    sys.exit(1)

# get metadata and payload data from file
metadata_raw = []
statsdata_raw = []
with open(sys.argv[1], "r") as f:
    statsfile = f.readlines()
for idx, line in enumerate(statsfile):
    line = line.rstrip('\n')
    if line == '===DATA===':
        statsdata_raw = statsfile[idx+1:]
        break
    else:
        metadata_raw.append(line)

# parse metadata
metadata = {}
for d in metadata_raw:
    d = d.split(":")
    if len(d) == 2:
        metadata[d[0].lower()] = d[1]

if 'columns' in metadata.keys():
    metadata['columns'] = metadata['columns'].split(',')

# parse payload data
statsdata = []
for d in statsdata_raw:
    datapoint = {}
    d = d.rstrip('\n').split(',')
    for i, e in enumerate(d):
        datapoint[ metadata['columns'][i] ] = e
    statsdata.append(datapoint)

#import pprint
#pprint.pprint(statsdata)

# PREPARE SYSTEM STAT GRAPH
x = []
sysstat_y_load = []
sysstat_y_mem = []
sysstat_y_swap = []

birdstat_y_cpu = []
birdstat_y_mem = []
birdstat_y_established = []
birdstat_y_pfx = []
birdstat_y_withdrawn = []

firstTime = None
for datapoint in statsdata:
    if firstTime is None:
        firstTime = int(datapoint['time'])
        x.append(0)
    else:
        x.append( int(datapoint['time']) - firstTime )
    if 'sys_load' in datapoint.keys():
        sysstat_y_load.append( float(datapoint['sys_load']) )
    else:
        sysstat_y_load.append(None)
    if 'sys_mem' in datapoint.keys():
        sysstat_y_mem.append( float(datapoint['sys_mem'])/1024 )
    else:
        sysstat_y_mem.append(None)
    if 'sys_swap' in datapoint.keys():
        sysstat_y_swap.append( float(datapoint['sys_swap'])/1024 )
    else:
        sysstat_y_swap.append(None)
    if 'ps_cpu' in datapoint.keys():
        birdstat_y_cpu.append( [None if e == '_' or e == '' else float(e) for e in datapoint['ps_cpu'].split('|') ])
    else:
        birdstat_y_cpu.append([None,None])
    if 'ps_vsz' in datapoint.keys():
        birdstat_y_mem.append( [None if e == '_' or e == '' else float(e)/1024 for e in datapoint['ps_vsz'].split('|') ]) # KiB → MiB
    else:
        birdstat_y_mem.append([None,None])
    if 'bird_established' in datapoint.keys():
        birdstat_y_established.append( [None if e == '_' or e == '' else int(e) for e in datapoint['bird_established'].split('|') ])
    else:
        birdstat_y_established.append([None,None])
    if 'bird_received_pfx' in datapoint.keys():
        birdstat_y_pfx.append( [None if e == '_' or e == '' else int(e) for e in datapoint['bird_received_pfx'].split('|') ])
    else:
        birdstat_y_pfx.append([None,None])
    if 'bird_received_withdrawn' in datapoint.keys():
        birdstat_y_withdrawn.append( [None if e == '_' or e == '' else int(e) for e in datapoint['bird_withdrawn'].split('|') ])
    else:
        birdstat_y_withdrawn.append([None,None])

# SHOW GRAPHS
cm = 1/2.54

min_ = None
max_ = None
if len(sys.argv) > 3:
    min_ = int(sys.argv[2])
    max_ = int(sys.argv[3])
if min_ is None:
    min_ = 0
if max_ is None:
    max_ = 100

print('GRAPH2: BIRD status')
color1, color2, color3, color4, color5 = plt.cm.Set1([.05, .15, .25, .35, .45])
for proto in range(0,2):
    print('   IPv4') if proto == 0 else print('   IPv6')
    print('      avg: {}, min={}, max={}'.format(mean([e[proto] for e in birdstat_y_cpu]), min([e[proto] for e in birdstat_y_cpu]), max([e[proto] for e in birdstat_y_cpu])))
    print('      avg: {}, min={}, max={} (ohne >{} und <{})'.format(mean([e[proto] for e in birdstat_y_cpu if e[proto] > min_ and e[proto] < max_]), min([e[proto] for e in birdstat_y_cpu if e[proto] > min_]), max([e[proto] for e in birdstat_y_cpu if e[proto] < max_]), min_, max_))

    fig, host = plt.subplots(figsize=(25*cm, 10*cm), layout='constrained') # Host = CPU usage
    ax2 = host.twinx() # ax2 = RAM
    host.set_xlabel("Time [s]")
    host.set_ylabel("CPU usage [%]")
    ax2.set_ylabel("RAM [MiB]")
    p1 = host.plot(x, [e[proto] for e in birdstat_y_cpu], ".", color=color1, label=f"CPU usage")
    host.set_ylim(0, 100)
    p2 = ax2.plot(x, [e[proto] for e in birdstat_y_mem], "-", color=color2, label=f"used RAM")
    if False and 'total_ram' in metadata.keys(): # false added to deactivate
        ax2.axhline(y = int(metadata['total_ram'])/1024, color = color2, linestyle = '--')
        ax2.set_ylim(0, int(metadata['total_ram'])/1024*1.1)

    plt.legend(handles=p1+p2, loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
    plt.tight_layout()
    plt.show()
