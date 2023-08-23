#! /usr/bin/env python3

import sys
import matplotlib.pyplot as plt

def help():
    print('USAGE: graph.py FILESET INTERVALS [DATA_LEN]')
    print('Plot graphs with the number of received UPDATEs, UPDATEs per peer and the announced/withdrawn prefixes per peer.')
    print('')
    print('FILESET      Path to file containing the filenames of the set of pcaps which should be analyzed. Each of this files has to contain packets of 1 hour. They have to be listed in the dataset in correct timeorder.')
    print('             Use for example tshark to parse the pcap:')
    print('             $ tshark -r trafficdump.pcap -M 1 -T fields -e _ws.col.Time -e ip.src -e bgp.nlri_prefix -e bgp.withdrawn_prefix -E separator=";" bgp.type==2 > parsed.csv')
    print('INTERVALS    Interval (in seconds) for which received UPDATE messages should be grouped together for plotting in the graph. Comma separated list to plot multiple intervals.')
    print('DATA_LEN     Time in seconds every single file in the dataset represents. Default: 3600')

def avg(data):
    if len(data) == 0:
        return 0
    else:
        return sum(data) / len(data)

def calc(interval_length, dataset_len):
    cur_interval_start = 0
    cur_interval = 1
    cur_interval_data = {
        # "neighbor": {'msg': 0, 'announced': 0, 'withdrawn': 0},
    }

    plt_intervals = []
    plt_total_msg = []
    plt_avg_msg_per_peer = []
    plt_avg_announced_per_peer = []
    plt_avg_withdrawn_per_peer = []
    max_announced = 0
    max_withdrawn = 0

    peerset = set()

    datafile_num = 0
    with open(sys.argv[1], 'r') as fileset:
        files = []
        for loadfile in fileset:
            files.append(loadfile.rstrip("\n"))
        for loadfile in files:
            with open(loadfile, 'r') as datafile:
                for line in datafile:
                    # TIME;SRC;ANNOUNCE_LIST;WITHDRAW_LIST
                    data = line.rstrip("\n").split(';')
                    try:
                        time = float(data[0]) + datafile_num * dataset_len
                        src = data[1]
                        announced_pfx = [] if data[2] == '' else data[2].split(",")
                        withdrawn_pfx = [] if data[3] == '' else data[3].split(",")
                    except Exception as e:
                        print('ABORT!')
                        print('Was not able to parse this line:')
                        print(line)
                        print('')
                        print(e)
                        sys.exit(1)

                    if time > cur_interval_start + interval_length:
                        # packet is in new interval. calculate current interval…
                        msg_count = 0
                        avg_msg = []
                        avg_announced = []
                        avg_withdrawn = []
                        for neigh in cur_interval_data:
                            peerset.add(neigh)
                            d = cur_interval_data[neigh]
                            msg_count += d['msg']
                            avg_msg.append(d['msg'])
                            avg_announced.append(d['announced'])
                            avg_withdrawn.append(d['withdrawn'])
                            max_announced = max(max_announced, d['announced'])
                            max_withdrawn = max(max_withdrawn, d['withdrawn'])

                        plt_intervals.append(cur_interval)
                        plt_total_msg.append(msg_count)
                        plt_avg_msg_per_peer.append(avg(avg_msg))
                        plt_avg_announced_per_peer.append(avg(avg_announced))
                        plt_avg_withdrawn_per_peer.append(avg(avg_withdrawn))

                        # …and start next interval
                        print(f"[file {datafile_num+1}/{len(files)}] parsed interval {cur_interval} (processed {cur_interval*interval_length} seconds)", end="\r")
                        cur_interval_start += interval_length
                        cur_interval += 1
                        cur_interval_data = {}

                    # add data to interval
                    if src not in cur_interval_data.keys():
                        cur_interval_data[src] = {'msg': 0, 'announced': 0, 'withdrawn': 0}
                    cur_interval_data[src]['msg'] += 1
                    cur_interval_data[src]['announced'] += len(announced_pfx)
                    cur_interval_data[src]['withdrawn'] += len(withdrawn_pfx)

                del line
                del data
                del time
                del src
                del announced_pfx
                del withdrawn_pfx
            datafile_num += 1
    print("")
    print("creating graphs...")

    # get data ranges for withdraw/announce/msg
    plt_times = [i*interval_length for i in plt_intervals]

    print(f"number of peers: {len(peerset)}")
    print(f"max announced/peer/interval: {max_announced}")
    print(f"max withdrawn/peer/interval: {max_withdrawn}")

    return (plt_times, plt_total_msg, plt_avg_msg_per_peer, plt_avg_announced_per_peer, plt_avg_withdrawn_per_peer)

if len(sys.argv) < 2:
    help()
    sys.exit(1)

if len(sys.argv) >= 4:
    dataset_len = int(sys.argv[3])
else:
    dataset_len = 3600

interval_data = []
interval_lengths = sys.argv[2].split(",")

plt_min = float('inf')
plt_max = 0
for i in interval_lengths:
    subdata = calc(int(i), dataset_len)
    interval_data.append(subdata)
    subplt_min = min([*subdata[1], *subdata[2], *subdata[3], *subdata[4]])
    subplt_max = max([*subdata[1], *subdata[2], *subdata[3], *subdata[4]])
    plt_min = min(plt_min, subplt_min)
    plt_max = max(plt_max, subplt_max)

datarange = [plt_min-100, plt_max+100]
if datarange[0] < 1:
    datarange[0] = 1

# now plot the data
cm = 1/2.54
#fig = plt.figure(figsize=(17*cm, 29*cm))
#plt.subplots_adjust(hspace=0.5)

markers = ["b.", "gx", "rs", "k*", "b2", "gp"]

#plt.subplot(411)
print("Showing: total_msg")
fig = plt.figure(figsize=(20*cm, 7*cm))
for i, data in enumerate(interval_data):
    plt.plot(data[0], data[1], markers[i%6], label=f"{interval_lengths[i]}s intervals") # x:plt_times y:plt_total_msg
plt.ylabel('Total number\nof UPDATEs [#]')
plt.xlabel(f"Time [s]")
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.ylim(datarange)
plt.tight_layout()
plt.show()

#plt.subplot(412)
print("Showing: avg_msg_per_peer")
fig = plt.figure(figsize=(20*cm, 7*cm))
for i, data in enumerate(interval_data):
    plt.plot(data[0], data[2], markers[i%6], label=f"{interval_lengths[i]}s intervals") # x:plt_times y:plt_avg_msg_per_peer
plt.ylabel('Average UPDATEs\nper peer [#]')
plt.xlabel(f"Time [s]")
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.ylim(datarange)
plt.tight_layout()
plt.show()

#plt.subplot(413)
print("Showing: avg_announced_per_peer")
fig = plt.figure(figsize=(20*cm, 7*cm))
for i, data in enumerate(interval_data):
    plt.plot(data[0], data[3], markers[i%6], label=f"{interval_lengths[i]}s intervals") # x:plt_times y:plt_avg_announced_per_peer
plt.ylabel('Average announced\nprefixes/peer [#]')
plt.xlabel(f"Time [s]")
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.ylim(datarange)
plt.tight_layout()
plt.show()

#plt.subplot(414)
print("Showing: avg_withdrawn_per_peer")
fig = plt.figure(figsize=(20*cm, 7*cm))
for i, data in enumerate(interval_data):
    plt.plot(data[0], data[4], markers[i%6], label=f"{interval_lengths[i]}s intervals") # x:plt_times y:plt_avg_withdrawn_per_peer
plt.ylabel('Average withdrawn\nprefixes/peer [#]')
plt.xlabel(f"Time [s]")
plt.yscale("log")
plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
plt.ylim(datarange)
plt.tight_layout()
plt.show()
