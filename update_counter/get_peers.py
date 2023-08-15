#! /usr/bin/env python3

import os
import sys
import requests
import json
import time

def help():
    print('USAGE: get_peers.py FILESET IXPID')
    print('Get the IP, ASN and name of the peers contained in a fileset generated for graph.py.')
    print('')
    print('FILESET      Path to file containing the filenames of the set of pcaps which should be analyzed.')
    print('IXPID        specifies which IXP should be investigated. The ID can be fetched from the PeeringDB-URL after opening the IXP.')
    print('             For example for DE-CIX Frankfurt the URL is https://www.peeringdb.com/ix/31 and the IXPID is 31.')

if len(sys.argv) < 3:
    help()
    sys.exit(1)

ixpid = sys.argv[2]
headers = {'Accept': 'application/json'}

if 'API_KEY' in os.environ and os.environ['API_KEY'] is not None:
    headers['Authorization'] = "Api-Key "+os.environ['API_KEY']

peerset = set()

datafile_num = 0
with open(sys.argv[1], 'r') as fileset:
    files = []
    for loadfile in fileset:
        files.append(loadfile.rstrip("\n"))
    for loadfile in files:
        print(f"[file {datafile_num}/{len(files)}]", end="\r")
        with open(loadfile, 'r') as datafile:
            for line in datafile:
                # TIME;SRC;ANNOUNCE_LIST;WITHDRAW_LIST
                data = line.rstrip("\n").split(';')
                try:
                    src = data[1]
                except Exception as e:
                    print('ABORT!')
                    print('Was not able to parse this line:')
                    print(line)
                    print('')
                    print(e)
                    sys.exit(1)

                peerset.add(src)

            del line
            del data
            del src
        datafile_num += 1
print("")


# Fetch Networks with IP from IXP
ixp_networks = {} # IPv4/IPv6 → PerringDB NetId
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
            ixp_networks[netixlan['ipaddr4']] = netixlan['net_id']
            ixp_networks[netixlan['ipaddr6']] = netixlan['net_id']

for peer in peerset:
    pdb_net = ixp_networks[peer]

    if os.path.isfile(f".cache/{pdb_net}.net"):
        # found data in cache
        with open(f".cache/{pdb_net}.net", 'r') as f:
            net = f.read()
    else:
        # cache miss
        while True:
            net = requests.get(f"https://peeringdb.com/api/net/{pdb_net}", headers=headers).text
            if "message" in json.loads(net).keys():
                time.sleep(5)
            else:
                break
        with open(f".cache/{pdb_net}.net", 'w') as f:
            f.write(net)
    net = json.loads(net)
    try:
        net_asn = net['data'][0]['asn']
        net_name = net['data'][0]['name']
    except Exception as e:
        net_asn = '?'
        net_name = '?'

    print(f"{peer};{net_asn};{net_name}")
