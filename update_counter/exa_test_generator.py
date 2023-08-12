#! /usr/bin/env python3

import time
import sys

routes = [
    '10.0.0.1/32',
    '10.0.0.2/32',
    '10.0.0.3/32',
    '10.0.0.4/32',
    '10.0.0.5/32',
    '10.0.0.6/32',
    '10.0.0.7/32',
    '10.0.0.8/32',
    '10.0.0.9/32',
    '10.0.0.10/32',
    '10.0.1.0/24',
    '10.0.2.0/24',
    '10.0.3.0/24',
    '10.0.4.0/24',
    '10.0.5.0/24',
    '10.0.6.0/24',
    '10.0.7.0/24',
    '10.0.8.0/24',
    '10.0.9.0/24',
    '10.0.10.0/24',
]

# Helper function to bring route (NLRI + attributes) in format needed by ExaBGP
def get_exa(nlri, withdraw=False):
    path = "[64496 64497 64498]"

    if withdraw:
        exastring = f'withdraw route {nlri}\n'
    else:
        exastring = f'announce route {nlri} next-hop self origin incomplete med 42 as-path {path}\n'

    return exastring

# t=0s: we will wait 5 sec to
time.sleep(5)

# t=5s: announce all routes
for r in routes:
    sys.stdout.write(get_exa(r))
sys.stdout.write("\n")
sys.stdout.flush()

time.sleep(65)
# t=70s: withdraw first 10 routes
for i in range(0,10):
    sys.stdout.write(get_exa(routes[i], True))
sys.stdout.write("\n")
sys.stdout.flush()

time.sleep(65)
# t=135s: announce first 5 routes + withdraw another 2 routes
for i in range(0,5):
    sys.stdout.write(get_exa(routes[i]))
for i in range(10,12):
    sys.stdout.write(get_exa(routes[i], True))
sys.stdout.write("\n")
sys.stdout.flush()

time.sleep(65)
# t=200s: withdraw all routes
for r in routes:
    sys.stdout.write(get_exa(r, True))
sys.stdout.write("\n")
sys.stdout.flush()

time.sleep(10)
# t=210s: shutdown session
sys.stdout.write('shutdown neighbor 192.168.122.44\n')
sys.stdout.flush()
