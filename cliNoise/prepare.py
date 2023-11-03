#! /usr/bin/env python3

import sys
import re
from datetime import datetime

commands = []
lastTime = None

with open(sys.argv[1], "r") as f:
    for line in f.readlines():
        if "show" not in line:
            continue
        result = re.search(r"([a-zA-Z]+ \d\d \d\d:\d\d:\d\d) ([a-z0-9\.-]+) ([a-z0-9-@\[\]]+): CLI: (.+)", line)
        if result is None:
            continue
        date = result.group(1)
        host = result.group(2)
        service = result.group(3)
        cmd = result.group(4)

        date = datetime.strptime(date, "%b %d %H:%M:%S")

        if lastTime is not None:
            wait = date - lastTime
            commands.append( ('WAIT', wait.total_seconds()) )

        commands.append( ('CMD', cmd) )
        lastTime = date

for c in commands:
    print(c[0] + "\t" + str(c[1]))
