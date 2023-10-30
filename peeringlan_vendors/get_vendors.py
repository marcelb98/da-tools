#! /usr/bin/env python3

import sys
import json
from mac_vendor_lookup import MacLookup, VendorNotFoundError, InvalidMacError

def help():
    print('USAGE: get_vendors.py FORMAT FILE OUTFORMAT')
    print('')
    print('Reads the neighbor table from FILE and counts how often a device vendor is listed.')
    print('Result is printed as CSV to stdout.')
    print('')
    print('FORMAT specifies which type of data is provided:')
    print('  iproute2   Data as returned by executing:')
    print('  $ ip neigh show | grep -v fe80 | grep REACHABLE')
    print('   ixf        Data as returned by IXF API call')
    print('')
    print('OUTFORMAT specifies in which format the data should be returned.')
    print('  csv    is the default.')
    print('  latex  will format the output as a LaTeX tabular.')

if len(sys.argv) < 3:
    help()
    sys.exit(1)

format = 'csv'
if len(sys.argv) > 3 and sys.argv[3] == 'latex':
    format = 'latex'

mac = MacLookup()
mac.update_vendors()

maclist = set()

vendors = {
    '_unknown': 0,
    '_invalid': 0
}

if sys.argv[1] == 'iproute2':
    with open(sys.argv[2], 'r') as f:
        for line in f.readlines():
            address = line.split(" ")[4]
            maclist.add(address)

elif sys.argv[1] == 'ixf':
    with open(sys.argv[2], 'r') as f:
        data = json.load(f)
        for member in data['member_list']:
            for connection in member['connection_list']:
                for vlan in connection['vlan_list']:
                    if 'ipv4' in vlan:
                        for address in vlan['ipv4']['mac_addresses']:
                            maclist.add(address)

                    if 'ipv6' in vlan:
                        for address in vlan['ipv6']['mac_addresses']:
                            maclist.add(address)

else:
    help()
    sys.exit(1)

for address in maclist:
    try:
        v = mac.lookup(address)
        if v in vendors.keys():
            vendors[v] += 1
        else:
            vendors[v] = 1
    except VendorNotFoundError:
        vendors['_unknown'] += 1
    except InvalidMacError:
        vendors['_invalid'] += 1


if format == 'latex':
    print('\\begin{table}[p]')
    print('    \centering')
    print('    \\begin{tabular}{l l l}')
    print('        Vendor & Absolute occurrences & relative\\\\')
    print('        \\hline')
total = sum(count for vendor, count in vendors.items())
vendors_sorted = sorted(vendors.items(), key=lambda x:x[1], reverse=True)
for vendor in vendors_sorted:
    if format == 'latex':
        print(f"        {vendor[0]} & {vendor[1]} & {(vendor[1]/total)*100:.2f}\\%\\\\")
    else:
        print(f"{vendor[0]},{vendor[1]},{(vendor[1]/total)*100:.2f}%")
if format == 'latex':
    print('    \\end{tabular}')
    print('    \\caption{MAC vendors}')
    print('    \\label{tab:macVendors}')
    print('\\end{table}')

