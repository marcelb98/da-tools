#! /usr/bin/env python3

from datetime import datetime, timedelta
import matplotlib.pyplot as plt

prevTime = None
_min = None
_max = None
_list = []
with open('logdump.txt', 'r') as f:
    for line in f.readlines():
        time = line.split(" ")[2]
        
        time = datetime.strptime(time, "%H:%M:%S.%f")

        if prevTime is None:
            prevTime = time
            continue

        diff = time - prevTime
        prevTime = time
        _list.append(diff)
        if _min is None or diff < _min:
            _min = diff
        if _max is None or diff > _max:
            _max = diff

_avg = sum(_list, timedelta(0)) / len(_list) 
print(f"MIN: {_min}")
print(f"AVG: {_avg}")
print(f"MAX: {_max}")


x = []
y = []
avg = _avg.total_seconds()*1000000
for i, e in enumerate(_list):
    x.append(i)
    y.append(e.total_seconds()*1000000)

variance = sum([(t-avg)**2 for t in y]) / len(y)
print(f"VAR: {variance}")

cm = 1/2.54
fig = plt.figure(figsize=(20*cm, 7*cm))
plt.plot(x, y, '.')
plt.hlines(avg, x[0], x[len(x)-1], colors='r', linestyles='dotted', label=f"avg={avg:.2f}")
plt.hlines(avg+variance, x[0], x[len(x)-1], colors='r', label=f"variance={variance:.2f}")
plt.hlines(avg-variance, x[0], x[len(x)-1], colors='r')
plt.ylabel('Time since previous log entry [us]')
plt.xlabel('Log entry [ID]')
plt.legend(loc="upper center", ncol=2)
plt.yscale('log')
plt.tight_layout()
plt.show()
