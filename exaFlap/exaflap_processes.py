#! /usr/bin/env python3

import time
import glob
import os
import subprocess
from threading import Thread
import argparse
from pathlib import Path
import shutil
import signal

# argparse
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--conf", type=str, default='/home/labadm/tenants/mb-victim/', help="Path to configuration of RS-Feeder")
parser.add_argument("-4", "--peers4", type=int, default=975, help="Number of IPv4 peers with flapping routes")
parser.add_argument("-6", "--peers6", type=int, default=0, help="Number of IPv6 peers with flapping routes")
parser.add_argument("-r", "--routes", type=int, default=1, help="Number of flapping routes for each peer")
parser.add_argument("-w", "--wait", type=float, default=0.2, help="Time to wait between start of peers")
parser.add_argument("-i", "--interval", type=int, default=36000, help="Interval (milliseconds) of flapping")
parser.add_argument("-R", "--reverse", action="store_true", help="Get peers from RS-Feeder config in reverse order")
args = parser.parse_args()

# fill out vars from argparse
peers4 = args.peers4
peers6 = args.peers6
routes = args.routes
wait_between_peers = args.wait # seconds
wait_between_flaps = args.interval / 1000 # seconds
conf_dir = args.conf

# run
peers = {
    # ip: [ [announce, ...], [withdraw, ...]],
    # ...
}

# get peer IPs
v4configs = list(glob.glob(conf_dir+'ipv4/config/*.conf'))
v6configs = list(glob.glob(conf_dir+'ipv6/config/*.conf'))
if args.reverse:
    v4configs.reverse()
    v6configs.reverse()
neighbors = []
i = 0
for n in v4configs:
    if i == peers4:
        break
    neighbors.append(n)
    i += 1

i = 0
for n in v6configs:
    if i == peers6:
        break
    neighbors.append(n)
    i += 1

# generate script for exabgp api
def gen_script(ip, routes, flapping, delay_start=0, delay_flap=0, interval_flap=0):
    # routes: all routes (initially announced)
    # flap: subset of routes, they are flapping. each entry is tuple (announce, withdraw) of exabgp commands
    script = '''#! /usr/bin/env python3
import sys
import time

def announce_all():
'''
    for r in routes:
        script = script + "  sys.stdout.write('"+r+"\\n')\n"
    script = script + '''  sys.stdout.flush()

def announce():
'''
    for r in flapping:
        script = script + "  sys.stdout.write('"+r[0]+"\\n')\n"
    script = script + '''  sys.stdout.flush()

def withdraw():
'''
    for r in flapping:
        script = script + "  sys.stdout.write('"+r[1]+"\\n')\n"
    script = script + '''  sys.stdout.flush()

'''
    if delay_start > 0:
        script = script + f"time.sleep({delay_start})\n"

    script = script + "announce_all()\n"

    if delay_flap > 0:
        script = script + f"time.sleep({delay_flap})\n"

    script = script + '''
# now we start to flap
state = False # True → flapping will be announced, flappingB withdrawn; False → contrary
while True:
    if state:
        announce()
    else:
        withdraw()

    state = not state
    time.sleep('''+str(interval_flap)+''')
'''
    return script

class ExaBGP:
    t = None
    pid = None
    ip = None

    def __init__(self, ip):
        self.ip = ip

    def stop(self):
        subprocess.run(['env', f'exabgp.api.pipename={self.ip}', 'exabgp.api.ack=false', 'exabgp.cache.attributes=false', '/home/labadm/exabgp/bin/exabgpcli', 'shutdown'] , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if self.pid is not None:
            time.sleep(1)
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)

    def start(self):
        self.t = Thread(target=self.run)
        self.t.daemon = True
        self.t.start()

    def run(self):
        r = subprocess.run(['env', f'exabgp.api.pipename={self.ip}', 'exabgp.api.ack=false', 'exabgp.cache.attributes=false', '/home/labadm/exabgp/sbin/exabgp', '/tmp/exaflap_processes/'+self.ip+'.conf'] , stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)

# prepare filesystem structure
Path("/tmp/exaflap_processes").mkdir(exist_ok=True)

# Copy exabgp config files and add API call, write flap script
neighbors2 = [] # store list of neighbors with new config file paths
subprocesses = []
for n in neighbors:
    # create new exabgp config
    print("Creating new exabgp configs...")
    ip = os.path.basename(n).rstrip('.conf')
    shutil.copy(n, "/tmp/exaflap_processes/"+ip+".conf")
    neighbors2.append("/tmp/exaflap_processes/"+ip+".conf")
    with open("/tmp/exaflap_processes/"+ip+".conf", "r") as f:
        config = f.read()
    config = "process announce-routes {\n  run \"/tmp/exaflap_processes/"+ip+".py\";\n  encoder text;\n}\n\n" + config
    config = config.replace("  inherit routeservers;\n", "  inherit routeservers;\n  group-updates true;\n  api {\n    processes [announce-routes];\n  }\n")
    with open("/tmp/exaflap_processes/"+ip+".conf", "w") as f:
        f.write(config)

    # get routes from peer
    peer_routes = []
    peer_flap = []
    i = 0
    for l in config.split("\n"):
        if not l.lstrip().startswith("unicast"):
            continue
        r = l.lstrip().rstrip(";").split(" ")
        peer_routes.append(f"announce route {' '.join(r[1:])}")
        if i < routes:
            peer_flap.append((f"announce route {' '.join(r[1:])}", f"withdraw route {r[1]} next-hop {r[3]}"))

    # build script
    script = gen_script(ip, peer_routes, peer_flap, delay_start=0, delay_flap=2, interval_flap=wait_between_flaps)
    with open(f"/tmp/exaflap_processes/{ip}.py", "w") as f:
        f.write(script)
    os.chmod(f"/tmp/exaflap_processes/{ip}.py", 0o744) # set executable

    # stop exabgp process started by feeder
    print("Stopping exabgp processes started by feeder...")
    r = subprocess.run(['env', f'exabgp.api.pipename={ip}', '/home/labadm/exabgp/bin/exabgpcli', 'shutdown'] , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print(f"  ERROR: could not stop feeder exabgp for {ip}.")

    # prepare subprocess
    t = ExaBGP(ip)
    subprocesses.append(t)

# start flapping peers
print("Starting flapping peers...")
for t in subprocesses:
    print(f"  {t.ip}")
    t.start()

# block main thread and wait for Ctrl+C
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        print("STOPPING ALL THREADS...")
        for t in subprocesses:
            print(f"Stopping {t.ip}...")
            t.stop()
        break
