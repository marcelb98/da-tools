This tool is used to calculate and plot statistics about the received UPDATE messages at a route server.

# How to
1. Capture pcap at network interface of route server
2. Get BGP UPDATE information (neighbors, announced and withdrawn prefixes) using tshark: `tshark -r dump.pcap -T fields -e _ws.col.Time -e ip.src -e bgp.nlri_prefix -e bgp.withdrawn_prefix -E separator=";" bgp.type==2 > parsed/bgp_updates.csv`
3. Filter out all UPDATEs which originated from the route server: `grep -v "RS1-IP-ADDRESS" parsed/bgp_updates.csv | grep -v "RS2-IP-ADDRESS" > parsed_filtered/bgp_updates.csv`
4. Add the CSV to the dataset file: `echo "parsed_filtered/bgp_updates.csv\n" >> paresd_filtered/dataset.txt`
5. Generate the graph: `./graph.py parsed_filtered/dataset.txt 60`

If you have recorded multiple pcaps (one file = one hour), tshark and route server filtering can be done for each pcap.
Just add all the filtered CSV to the dataset (step 4). It is important that the several files are listed in correct time order in the dataset, as the total time will be calculated based on this.

*Notice:* You may want to add an extra line in the last CSV, which time is in the next parsed interval, so that the graph.py script is triggered to calculate and plot the last real interval.

# Validation
To test the tooling, we captured a pcap with an ExaBGP running, that is announcing a well known set of UPDATES.
Those UPDATES are generated with the script `exa_test_generator.py`, serving as the source for the exabgp API.
