#! /usr/bin/env python3

import sys
import time
import subprocess

commands = []
lastTime = None

print("replaying birdc commands...")
with open(sys.argv[1], "r") as f:
    for line in f.readlines():
        line = line.split("\t")

        if line[0] == 'WAIT':
            time.sleep(float(line[1]))
        elif line[0] == 'CMD':
            subprocess.Popen(["birdc", "-s", "/run/bird-globepeer-ipv4.ctl"] + line[1].split(" "))
print("DONE")
