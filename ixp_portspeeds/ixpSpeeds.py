#! /usr/bin/env python3

import sys
import os
import requests
import json
from pathlib import Path
import matplotlib.pyplot as plt

Path(".cache").mkdir(exist_ok=True)

def help():
    print('USAGE: ixpSpeeds.py IXPID')
    print('')
    print('Fetches the port speeds of all ports at the IXP from PeeringDB.')
    print('Result is printed as CSV to stdout.')
    print('')
    print('IXPID specifies which IXP should be investigated. The ID can be fetched from the PeeringDB-URL after opening the IXP.')
    print('  For example for DE-CIX Frankfurt the URL is https://www.peeringdb.com/ix/31 and the IXPID is 31.')
    print('')
    print('peeringdb.com might throttle your API requests without authentication.')
    print('Store your API-Key in the environment variable API_KEY to authenticate for the API requests.')
    print('The tool is also caching the retreived API results. Delete the .cache directory to clear the cache.')

if len(sys.argv) < 2:
    help()
    sys.exit(1)

ixpid = sys.argv[1]
headers = {'Accept': 'application/json'}

if 'API_KEY' in os.environ.keys():
    headers['Authorization'] = "Api-Key "+os.environ['API_KEY']

speeds = {} # speed: counter, …

if os.path.isfile(f".cache/{ixpid}.ix"):
    # found data in cache
    with open(f".cache/{ixpid}.ix", 'r') as f:
        ixps = f.read()
else:
    # cache miss
    ixps = requests.get(f"https://peeringdb.com/api/ix/{ixpid}", headers=headers).text
    with open(f".cache/{ixpid}.ix", 'w') as f:
        f.write(ixps)
ixps = json.loads(ixps)

more_than_10g = 0
more_than_20g = 0
more_than_30g = 0
nbr_count = 0
if 'data' not in ixps.keys():
    print(ixps)
    sys.exit(1)
for ixp in ixps['data']:
    for ixlan in ixp['ixlan_set']:
        ixlanid = ixlan['id']

        if os.path.isfile(f".cache/{ixlanid}.netixlan"):
            # found data in cache
            with open(f".cache/{ixlanid}.netixlan", 'r') as f:
                netixlans_data = f.read()

        else:
            # cache miss
            netixlans_data = requests.get(f"https://peeringdb.com/api/netixlan?ixlan={ixlanid}", headers=headers).text
            with open(f".cache/{ixlanid}.netixlan", 'w') as f:
                f.write(netixlans_data)

        netixlans = json.loads(netixlans_data)

        for netixlan in netixlans['data']:
            speed = netixlan['speed']
            if speed < 10000:
                # we will group all speeds <10G
                speed = 9000

            if speed not in speeds:
                speeds[speed] = 1
            else:
                speeds[speed] += 1

            if speed >= 10000:
                more_than_10g += 1
            if speed >= 20000:
                more_than_20g += 1
            if speed >= 30000:
                more_than_30g += 1
            nbr_count += 1

# sort and print speeds
print(f"Neighbors with >=10G capacity: {(more_than_10g/nbr_count)*100}%")
print(f"Neighbors with >=20G capacity: {(more_than_20g/nbr_count)*100}%")
print(f"Neighbors with >=30G capacity: {(more_than_30g/nbr_count)*100}%")

keys = list(speeds.keys())
keys.sort()
sorted_speeds = {i: speeds[i] for i in keys}

labels = []
sizes = []
for speed in sorted_speeds:
    sizes.append(sorted_speeds[speed])
    if speed == 9000:
        labels.append("<10G")
    else:
        labels.append(f"{speed/1000}G")

cm = 1/2.54
fig, ax = plt.subplots(figsize=(17*cm, 15*cm))
ax.pie(sizes, labels=labels)
plt.legend(loc='center left', bbox_to_anchor=(-0.25,0.5))
plt.show()

