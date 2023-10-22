#! /usr/bin/env python3

import sys
import re
import matplotlib.pyplot as plt
from statistics import mean

if len(sys.argv) < 2:
    print("Path to file with loopcycle log is required as argument!")
    sys.exit(0)

loop_cycles = []

with open(sys.argv[1], "r") as f:
    for line in f.readlines():
        result = re.search(r".*I/O loop cycle took (\d*.\d*) (.{1,2}) for (\d*) events.*", line)
        time = float(result.group(1))
        time_unit = result.group(2)
        events = int(result.group(3))

        if time_unit == 's':
            time = time * 1000
            time_unit = 'ms'
        elif time_unit == 'us':
            time = time / 1000
            time_unit = 'ms'

        loop_cycles.append( (time, events) )

# statistics
print('loopcycle    avg: {}, min={}, max={}'.format(mean([e[0] for e in loop_cycles]), min([e[0] for e in loop_cycles]), max([e[0] for e in loop_cycles])))
print('events       avg: {}, min={}, max={}'.format(mean([e[1] for e in loop_cycles]), min([e[1] for e in loop_cycles]), max([e[1] for e in loop_cycles])))

# plot graph
cm = 1/2.54
color1, color2, color3, color4, color5 = plt.cm.Set1([.05, .15, .25, .35, .45])
x = range(0, len(loop_cycles))

fig, host = plt.subplots(figsize=(25*cm, 10*cm), layout='constrained') # Host = loop cycle time
ax2 = host.twinx() # ax2 = number of events in loop cycle
#host.set_xlabel("Time [s]")
host.set_ylabel("cycle time [ms]")
ax2.set_ylabel("events [#]")
p1 = host.plot(x, [i[0] for i in loop_cycles], "o", color=color2, label=f"cycle time")
#host.set_ylim(0, 100)
p2 = ax2.plot(x, [i[1] for i in loop_cycles], "x", color=color1, label=f"events")

plt.legend(handles=p1+p2, loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.tight_layout()
plt.show()
