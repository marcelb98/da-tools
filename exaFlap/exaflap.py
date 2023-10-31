#! /usr/bin/env python3

import time
import glob
import os
import subprocess
from threading import Thread
import argparse

# argparse
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--conf", type=str, default='/home/labadm/tenants/mb-victim/', help="Path to configuration of RS-Feeder")
parser.add_argument("-4", "--peers4", type=int, default=975, help="Number of IPv4 peers with flapping routes")
parser.add_argument("-6", "--peers6", type=int, default=0, help="Number of IPv6 peers with flapping routes")
parser.add_argument("-r", "--routes", type=int, default=1, help="Number of flapping routes for each peer")
parser.add_argument("-w", "--wait", type=float, default=0.2, help="Time to wait between start of peers")
parser.add_argument("-i", "--interval", type=int, default=36000, help="Interval (milliseconds) of flapping")
parser.add_argument("-R", "--reverse", action="store_true", help="Get peers from RS-Feeder config in reverse order")
parser.add_argument("-N", "--notPeer", type=str, help="Do not flap this given peer (by IP)")
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
    if args.notPeer is not None and os.path.basename(n).rstrip('.conf') == args.notPeer:
        continue
    if i == peers4:
        break
    neighbors.append(n)
    i += 1

i = 0
for n in v6configs:
    if args.notPeer is not None and os.path.basename(n).rstrip('.conf') == args.notPeer:
        continue
    if i == peers6:
        break
    neighbors.append(n)
    i += 1

# get routes from peers
for peerConf in neighbors:
    neighbor = os.path.basename(peerConf).rstrip('.conf')
    config = ''
    with open(peerConf, 'r') as f:
        config = f.read()

    peers[neighbor] = [[], []]
    i = 0
    for l in config.split("\n"):
        if not l.lstrip().startswith("unicast"):
            continue
        r = l.lstrip().rstrip(";").split(" ")
        peers[neighbor][0].append(f"announce route {' '.join(r[1:])}") # data for announcement
        peers[neighbor][1].append(f"withdraw route {r[1]} next-hop {r[3]}") # data for withdraw

        i += 1
        if i == routes:
            break

# show info about what will happen
for peer in peers:
    print(f'{peer}: {len(peers[peer][0])}')
print("")

# class to run exabgpcli in thread
class ExaBGP:
    t = None
    peer = None
    wait = 1
    commandA = None
    commandB = None
    finish = False

    mode = 0

    def __init__(self, peer, wait, commandA, commandB):
        self.peer = peer
        self.wait = wait
        self.commandA = commandA
        self.commandB = commandB

    def stop(self):
        self.finish = True

    def run(self):
        while not self.finish:
            cmds = self.commandA if self.mode == 0 else self.commandB
            for cmd in cmds:
                r = subprocess.run(['env', f'exabgp.api.pipename={self.peer}', '/home/labadm/exabgp/bin/exabgpcli', cmd] , stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if r.returncode != 0:
                print(f"ERROR: sending to peer {self.peer}.")
            if r.stderr.decode('utf-8') != '':
                print(f"{self.peer}: ERROR: {r.stderr.decode('utf-8')}")

            time.sleep(self.wait)
            self.mode = (self.mode + 1) % 2

    def start(self):
        self.t = Thread(target=self.run)
        self.t.daemon = True
        self.t.start()

# prepare threads
threads = []
for peer in peers:
    t = ExaBGP(peer, wait_between_flaps, peers[peer][0], peers[peer][1])
    threads.append(t)

# start all threads
for t in threads:
    t.start()
    print(f"Started {t.peer}")

# block main thread and wait for Ctrl+C
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        print("STOPPING ALL THREADS...")
        for t in threads:
            t.stop()
        break
