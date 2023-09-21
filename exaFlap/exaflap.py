#! /usr/bin/env python3

peers4 = 5
peers6 = 0
routes = 1
wait_between_peers = 0 # seconds
wait_between_flaps = 1 # seconds
conf_dir = '/home/labadm/tenants/mb-victim/'

import time
import glob
import os
import subprocess
from threading import Thread

peers = {
    # ip: [ [announce, ...], [withdraw, ...]],
    # ...
}

# get peer IPs
neighbors = []
i = 0
for n in glob.glob(conf_dir+'ipv4/config/*.conf'):
    if i == peers4:
        break
    neighbors.append(n)
    i += 1

i = 0
for n in glob.glob(conf_dir+'ipv6/config/*.conf'):
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
