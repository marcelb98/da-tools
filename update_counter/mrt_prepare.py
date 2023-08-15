#! /usr/bin/env python3

import sys
import time
import datetime
import mrtparse

def help():
    print('mrt_prepare.py MRT_FILE IPV')
    print('This script will extract the announced and withdrawn prefixes from all BGP UPDATE messages recorded in the given MRT_FILE.')
    print('')
    print('Data will be returned with one BGP UPDATE message per line. Time, peer, announced and withdrawn routes are separated by ;. Example:')
    print('42;192.168.0.1;192.168.1/0,192.168.2.0/24;192.168.3.0/24')
    print('At second 42 the peer with IP 192.168.0.1 announced two prefixes and withdrew one prefix.')
    print('')
    print('MRT_FILE     Path to the MRT file which should be inspected.')
    print('IPV          IP versions to include. 4 for IPv4 only, 6 for IPv6 only, 46 for both IP versions.')

if len(sys.argv) < 3:
    help()
    sys.exit(1)

file = sys.argv[1]
ipv = sys.argv[2]

if ipv not in ['4', '6', '46']:
    help()
    sys.exit(1)

base_date = None
for entry in mrtparse.Reader(file):
    if entry.data['type'] != {16: 'BGP4MP'} or (entry.data['subtype'] != {4: 'BGP4MP_MESSAGE_AS4'} and entry.data['subtype'] != {1: 'BGP4MP_MESSAGE'}):
        # does not contain a BGP message
        continue

    if 'bgp_message' not in entry.data:
        continue

    bgp_msg = entry.data['bgp_message']
    if bgp_msg['type'] == {2: 'UPDATE'}:
        time = next(iter(entry.data['timestamp']))
        if base_date is None:
            base_date = time
        time = time - base_date
        peer = entry.data['peer_ip']

        if ipv == '4' and ':' in peer:
            continue
        elif ipv == '6' and '.' in peer:
            continue

        # get IPv4 NLRI
        announced = []
        withdrawn = []
        if 'nlri' in bgp_msg:
            for p in bgp_msg['nlri']:
                announced.append("{}/{}".format(p['prefix'], p['length']))

        # get IPv4 withdrawn
        if 'withdrawn_routes' in bgp_msg:
            for p in bgp_msg['withdrawn_routes']:
                withdrawn.append("{}/{}".format(p['prefix'], p['length']))

        # search attributes for MP_UNREACH/MP_REACH
        for attr in bgp_msg['path_attributes']:
            if attr['type'] == {14: 'MP_REACH_NLRI'}:
                for p in attr['value']['nlri']:
                    announced.append("{}/{}".format(p['prefix'], p['length']))

            elif attr['type'] == {15: 'MP_UNREACH_NLRI'}:
                for p in attr['value']['withdrawn_routes']:
                    withdrawn.append("{}/{}".format(p['prefix'], p['length']))

        # print data
        print(f"{time};{peer};{','.join(announced)};{','.join(withdrawn)}")
