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
parser.add_argument("-p", "--protocol", type=str, default='ipv4', help="Protocol of peer to flap (ipv4 or ipv6)")
parser.add_argument("-n", "--neighbor", type=str, required=True, help="Name of the neighbor to use for flapping")
parser.add_argument("-i", "--interval", type=int, default=1000, help="Interval (milliseconds) of flapping")
parser.add_argument("-r", "--routes", type=int, default=1, help="Number of flapping routes")
args = parser.parse_args()

# fill out vars from argparse
wait_between_flaps = args.interval / 1000 # seconds
conf_dir = args.conf

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


# check if cfg has to be created
if not (os.path.isfile("/tmp/exaflap_processes/"+args.neighbor+".conf") and os.path.isfile("/tmp/exaflap_processes/"+args.neighbor+".py")):
    # copy exabgp config file and add API call, write flap script
    c = args.conf + '/' + args.protocol + '/config/' + args.neighbor + '.conf'
    shutil.copy(c, "/tmp/exaflap_processes/"+args.neighbor+".conf")
    with open("/tmp/exaflap_processes/"+args.neighbor+".conf", "r") as f:
        config = f.read()
    config = "process announce-routes {\n  run \"/tmp/exaflap_processes/"+args.neighbor+".py\";\n  encoder text;\n}\n\n" + config
    config = config.replace("  inherit routeservers;\n", "  inherit routeservers;\n  group-updates true;\n  api {\n    processes [announce-routes];\n  }\n")
    with open("/tmp/exaflap_processes/"+args.neighbor+".conf", "w") as f:
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
        if i < args.routes:
            peer_flap.append((f"announce route {' '.join(r[1:])}", f"withdraw route {r[1]} next-hop {r[3]}"))
        i += 1

    # build script
    script = gen_script(args.neighbor, peer_routes, peer_flap, delay_start=0, delay_flap=2, interval_flap=wait_between_flaps)
    with open(f"/tmp/exaflap_processes/{args.neighbor}.py", "w") as f:
        f.write(script)
    os.chmod(f"/tmp/exaflap_processes/{args.neighbor}.py", 0o744) # set executable

    print(f"We will be flapping {len(peer_flap)} of {len(peer_routes)} routes.")
else:
    print("Using existing config.")

# stop exabgp process started by feeder
print("Stopping exabgp processes started by feeder...")
r = subprocess.run(['env', f'exabgp.api.pipename={args.neighbor}', '/home/labadm/exabgp/bin/exabgpcli', 'shutdown'] , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if r.returncode != 0:
    print(f"  ERROR: could not stop feeder exabgp for {args.neighbor}.")

# prepare + start subprocess
t = ExaBGP(args.neighbor)
print(f"Start flapping for {args.neighbor}...")
t.start()

while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        print("STOPPING ALL THREADS...")
        print(f"Stopping {t.ip}...")
        t.stop()
        break
