#! /usr/bin/env python3

import sys
import matplotlib.pyplot as plt
import statistics

def help():
    print('USAGE: peer_prefixes.py FILESET')
    print('Plots for each peer the number of prefixes which were anounced at least once by the UPDATE messages.')
    print('')
    print('FILESET      Path to file containing the filenames of the set of pcaps which should be analyzed.')
    print('             Use for example tshark to parse the pcap:')
    print('             $ tshark -r trafficdump.pcap -M 1 -T fields -e _ws.col.Time -e ip.src -e bgp.nlri_prefix -e bgp.withdrawn_prefix -E separator=";" bgp.type==2 > parsed.csv')

if len(sys.argv) < 2:
    help()
    sys.exit(1)

DATA = {}
# DATA = {
#    neighbor: [prefix1, prefix2, …],
#    '192.168.0.1': ['192.168.1.0/24', '192.168.2.0/24'],
# }
datafile_num = 0
with open(sys.argv[1], 'r') as fileset:
    files = []
    for loadfile in fileset:
        files.append(loadfile.rstrip("\n"))
    for loadfile in files:
        with open(loadfile, 'r') as datafile:
            print(f"[file {datafile_num+1}/{len(files)}]", end="\r")
            for line in datafile:
                # TIME;SRC;ANNOUNCE_LIST;WITHDRAW_LIST
                data = line.rstrip("\n").split(';')
                try:
                    src = data[1]
                    announced_pfx = [] if data[2] == '' else data[2].split(",")
                except Exception as e:
                    print('ABORT!')
                    print('Was not able to parse this line:')
                    print(line)
                    print('')
                    print(e)
                    sys.exit(1)

                if src not in DATA.keys():
                        DATA[src] = []
                for pfx in announced_pfx:
                    if pfx not in DATA[src]:
                        DATA[src].append(pfx)
                del src
                del announced_pfx
                del data
        datafile_num += 1
print("")

# prepare data
peers = []
amounts = []
for i, p in enumerate(DATA):
    peers.append(i)
    amounts.append(len(DATA[p]))
max_pfx = max(amounts)
avg_pfx = statistics.mean(amounts)
median_pfx = statistics.median(amounts)

# now plot the data
cm = 1/2.54


fig = plt.figure(figsize=(20*cm, 7*cm))
plt.bar(peers, amounts)
plt.axhline(y=max_pfx, color='k', linestyle=':', label=f"max={max_pfx}")
plt.axhline(y=avg_pfx, color='r', linestyle=':', label=f"avg={avg_pfx:.2f}")
plt.axhline(y=median_pfx, color='g', linestyle=':', label=f"median={median_pfx}")
plt.ylabel('Announced prefixes [#]')
plt.xlabel('Peer [ID]')
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.tight_layout()
plt.show()

import sys
sys.exit(0)

for i, data in enumerate(interval_data):
    plt.plot(data[0], data[1], markers[i%6], label=f"{interval_lengths[i]}s intervals") # x:plt_times y:plt_total_msg
plt.ylabel('Total number\nof UPDATEs [#]')
plt.xlabel(f"Time [s]")
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.ylim(datarange)
plt.tight_layout()
plt.show()
