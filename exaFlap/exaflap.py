#! /usr/bin/env python3

peers4 = 1
peers6 = 1
routes = 1
wait_between_peers = 0 # seconds
wait_between_flaps = 1 # seconds
conf_dir = '/home/labadm/tenants/mb-victim/'

import time
import glob
import os
import subprocess

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
        r = l.lstrip().split(" ")
        peers[neighbor][0].append(f"announce route {' '.join(r[1:])}") # data for announcement
        peers[neighbor][1].append(f"withdraw route {r[1]} next-hop {r[3]}") # data for withdraw

        i += 1
        if i == routes:
            break

mode = 0
while True:
    if mode == 0:
        print("currently ANNOUNCING routes    ", end="\r")
    else:
        print("currently NOT ANNOUNCING routes", end="\r")
    for peer in peers:
        r = subprocess.run(['env', f'exabgp.api.pipename={peer}', '/home/labadm/exabgp/bin/exabgpcli'] + peers[peer][mode], stdout=subprocess.PIPE)
        if r.returncode != 0:
            print(f"ERROR: sending mode {mode} to peer {peer}.")
        time.sleep(wait_between_peers)

    mode = (mode + 1) % 2
    time.sleep(wait_between_flaps)
