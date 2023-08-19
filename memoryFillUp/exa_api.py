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

    size_wire = 53 + 4 * len(as_path) + 4 * len(communities)
    size_mem = 14 + 4 * len(as_path) + 4 * len(communities)
    return (exastring+'\n', size_wire, size_mem)

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

total_sent_wire = 0
total_sent_mem = 0
addresses = iter(subnet)
i1 = 1
i2 = 1
j = 1
while total_sent_mem < amount:
    as_path = [as_number, as_number, as_number]
    communities = []
    next_wire_size = 53 + 4 * len(as_path)
    
    while next_wire_size < 4090 and next_wire_size < (amount - total_sent_mem):
        communities.append( (i1, i2) )
        next_wire_size += 4
        i2 += 1
        if i2 > 65511:
            i2 = 1
            i1 += 1
        if i1 > 65511:
            i1 = 1
    
    next_update = get_announce(next(addresses), as_path, communities)
    sys.stdout.write( next_update[0] )
    total_sent_wire += next_update[1]
    total_sent_mem += next_update[2]
    if j % 10 == 0:
        f.write(f"#sent_msg={j}   total_sent_wire={total_sent_wire}B = {total_sent_wire/1024/1024}MB    total_sent_mem={total_sent_mem}B = {total_sent_mem/1024/1024}MB")
    sys.stdout.flush()
    f.seek(0)
    j += 1

f.close()
