#! /usr/bin/env python

#    Copyright 2023 Marcel Beyer
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import sys
import time
from ipaddress import ip_network

def help():
    print('exa_api.py AMOUNT SUBNET AS')
    print('This script will create API messages for ExaBGP to send out BGP UPDATES which fill up the memory of the BGP peer with AMOUNT bytes of data.')
    print('')
    print('AMOUNT   How many Bytes should be sent to the BGP peer. Value is provided in Byte or with B,KB,MB,GB as suffix.')
    print('SUBNET   Subnet in CIDR notation from which /32 NLRIs should be generated. The script tries to use as less IP addresses as possible.')
    print('AS       The AS number which should be on the leftmost position in the AS-PATH.')

# Helper function to bring route (NLRI + attributes) in format needed by ExaBGP
def get_announce(nlri, as_path, communities):
    path = "["
    for asn in as_path:
        if path != "[":
            path = path + " "
        path = path + str(asn)
    path = path + "]"

    exastring = f'announce route {nlri} next-hop self origin incomplete med 42 as-path {path}'
    
    if len(communities) > 0:
        comm = "["
        for c in communities:
            if comm != "[":
                comm = comm + " "
            comm = comm + f"{c[0]}:{c[1]}"
        comm = comm + "]"

        exastring = exastring + f" community {comm}"

    size = 5 * 1 + 4 * len(as_path) + 4 * len(communities) + 49
    return (exastring+'\n', size)

if len(sys.argv) < 4:
    help()
    sys.exit(1)
amount = sys.argv[1]
subnet = ip_network(sys.argv[2])
as_number = int(sys.argv[3])

if amount.endswith('GB'):
    amount = int(amount.rstrip('GB')) * 1024 * 1024 * 1024
elif amount.endswith('MB'):
    amount = int(amount.rstrip('MB')) * 1024 * 1024
elif amount.endswith('KB'):
    amount = int(amount.rstrip('KB')) * 1024
elif amount.endswith('B'):
    amount = int(amount.rstrip('B'))
else:
    amount = int(amount)

f = open('/tmp/mem_usage', 'w')
time.sleep(5) # for ExaBGP startup

total_sent = 0
addresses = iter(subnet)
i = 1
while total_sent < amount:
    as_path = [as_number, as_number, as_number]
    communities = []
    payload = 5 + 4 * len(as_path) # 5 Byte NLRI + 4 Byte for each AS
    
    while payload < 4000 and payload < (amount - total_sent): #65511:
        communities.append( (as_number, i) )
        payload += 4
        i += 1
        if i > 65511:
            i = 1
    
    next_update = get_announce(next(addresses), as_path, communities)
    sys.stdout.write( next_update[0] )
    total_sent += next_update[1]
    sys.stdout.flush()
    f.write(f"total_sent={total_sent}B = {total_sent/1024}KB = {total_sent/1024/1024}MB = {total_sent/1024/1024/1024}GB")
    f.seek(0)
    time.sleep(0.01)

f.close()
