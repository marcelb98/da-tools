#! /usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from threading import Thread
from queue import Queue
import time
import subprocess
import re
import os
import stat

class Server(BaseHTTPRequestHandler):

    controller = None

    def do_GET(self):
        req = urlparse(self.path)
        querystring = parse_qs(req.query)

        comment = None
        if 'comment' in querystring.keys():
            comment = querystring['comment'][0]

        if req.path.rstrip("/") == "/start":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            if self.controller.running:
                self.wfile.write(bytes("ALREADY RUNNING.", "utf-8"))
            else:
                self.controller.start(comment)
                self.wfile.write(bytes("STARTED.", "utf-8"))

        elif req.path.rstrip("/") == "/stop":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            if self.controller.running:
                self.controller.stop()
                self.wfile.write(bytes("STOPPED.", "utf-8"))
            else:
                self.wfile.write(bytes("NOT RUNNING.", "utf-8"))

        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(bytes("Request not implemented.", "utf-8"))

class Controller:
    running = False
    start = None
    queue = Queue()

    num_cpu = None
    total_ram = None
    total_swap = None

    comment = "n/A"
    data = {}
    # data = {id: {'time': secSinceStart,
    #              'sys_load': int, 'sys_mem': int, 'sys_swap': int, 'sys_net_rx': int, 'sys_net_tx': int,
    #              'ps_oom': integer, 'ps_cpu': integer, 'ps_mem': integer, 'ps_vsz': integer, 'ps_rss': integer, 'ps_pri' integer,
    #              'bird_established': integer, 'bird_mem_tables': int, 'bird_mem_attr': int, 'bird_mem_total': int, 'bird_received_pfx': integer, 'bird_accepted_pfx': integer, 'bird_received_withdraw': int, 'bird_accepted_withdraw': int,
    # }}

    def __init__(self):
        # get number of CPUs
        r = subprocess.run(['nproc'], stdout=subprocess.PIPE)
        self.num_cpu = int(r.stdout.decode('utf-8').split("\n")[0])

        # get available mem/swap
        with open('/proc/meminfo', 'r') as f:
            for l in f.readlines():
                if l.startswith('MemTotal'):
                    self.total_ram = int(l.split(":")[1].lstrip().split(" ")[0]) # KiB
                elif l.startswith('SwapTotal'):
                    self.total_swap = int(l.split(":")[1].lstrip().split(" ")[0]) # KiB

    def start(self, comment):
        def start():
            i = 1
            while self.running:
                # This loop is running as long as we want to collect statistics.
                # We trigger to collect each of our requested statistics once a second.
                t = int(time.time()) - self.start
                self.data[i] = {'time': t, 'sys_load': 0, 'sys_mem': 0, 'sys_swap': 0, 'sys_net_rx': 0, 'sys_net_tx': 0, 'ps_cpu': 0, 'ps_mem': 0, 'ps_vsz': 0, 'ps_rss': 0, 'ps_pri': 0,
                                'bird_established': 0, 'bird_mem_tables': 0, 'bird_mem_attr': 0, 'bird_mem_total': 0, 'bird_received_pfx': 0, 'bird_accepted_pfx': 0, 'bird_received_withdraw': 0, 'bird_accepted_withdraw': 0}
                ps = PsCollector(self.queue, i)
                ps.start()
                bird = BirdCollector(self.queue, i)
                bird.start()
                sys = SystemCollector(self.queue, i)
                sys.start()

                i += 1
                time.sleep(1)

        def read():
            # fetch statistics from queue and write them to data
            while True:
                new = self.queue.get()
                d = self.data[new['id']]
                if new['who'] == 'BirdCollector':
                    d['bird_established'] = new['data']['established']
                    d['bird_mem_tables'] = new['data']['mem_tables']
                    d['bird_mem_attr'] = new['data']['mem_attr']
                    d['bird_mem_total'] = new['data']['mem_total']
                    d['bird_received_pfx'] = new['data']['received_pfx']
                    d['bird_accepted_pfx'] = new['data']['accepted_pfx']
                    d['bird_received_withdraw'] = new['data']['received_withdraw']
                    d['bird_accepted_withdraw'] = new['data']['accepted_withdraw']
                elif new['who'] == 'PsCollector':
                    d['ps_cpu'] = new['data']['cpu']
                    d['ps_mem'] = new['data']['mem']
                    d['ps_vsz'] = new['data']['vsz']
                    d['ps_rss'] = new['data']['rss']
                    d['ps_pri'] = new['data']['pri']
                elif new['who'] == 'SystemCollector':
                    d['sys_load'] = new['data']['load']
                    d['sys_mem'] = new['data']['mem']
                    d['sys_swap'] = new['data']['swap']
                    d['sys_net_rx'] = new['data']['net_rx']
                    d['sys_net_tx'] = new['data']['net_tx']

                self.data[new['id']] = d

        self.running = True
        self.comment = comment
        self.start = int(time.time())

        # trigger data gathering
        t = Thread(target=start)
        t.daemon = True
        t.start()

        # collect results
        t2 = Thread(target=read)
        t2.daemon = True
        t2.start()

    def stop(self):
        self.running = False

        # wait for empty queue
        while not self.queue.empty():
            time.sleep(0.5)

        # write data to file
        with open(f"stats_{self.start}", "w") as f:
            f.write(f"START:{self.start}\n")
            f.write(f"COMMENT:{self.comment}\n")
            f.write(f"NUM_CPU:{self.num_cpu}\n")
            f.write(f"TOTAL_RAM:{self.total_ram}\n")
            f.write(f"TOTAL_SWAP:{self.total_swap}\n")
            f.write("COLUMNS:idx,time,sys_load,sys_mem,sys_swap,sys_net_rx,sys_net_tx,ps_cpu,ps_mem,ps_vsz,ps_rss,ps_pri,bird_established,bird_mem_tables,bird_mem_attr,bird_mem_total,bird_received_pfx,bird_accepted_pfx,bird_received_withdraw,bird_accepted_withdraw\n")
            f.write("===DATA===\n")
            for i, row in self.data.items():
                f.write(f"{i},{row['time']},{row['sys_load']},{row['sys_mem']},{row['sys_swap']},{row['sys_net_rx']},{row['sys_net_tx']},{row['ps_cpu']},{row['ps_mem']},{row['ps_vsz']},{row['ps_rss']},{row['ps_pri']},{row['bird_established']},{row['bird_mem_tables']},{row['bird_mem_attr']},{row['bird_mem_total']},{row['bird_received_pfx']},{row['bird_accepted_pfx']},{row['bird_received_withdraw']},{row['bird_accepted_withdraw']}\n")

class Collector:
    t = None
    queue = None
    i = None

    def __init__(self, q, i):
        self.queue = q
        self.i = i

    def run(self):
        raise NotImplementedError

    def start(self):
        self.t = Thread(target=self.run)
        self.t.daemon = True
        self.t.start()

class PsCollector(Collector):

    t = None
    queue = None
    i = None
    pid = None

    def __init__(self, q, i):
        super().__init__(q, i)
        self.pid = subprocess.check_output(["pidof","bird"]).decode('utf-8').split("\n")[0]

    def run(self):
        try:
            sep = re.compile('[\s]+')
            r = subprocess.run(['ps','-p',self.pid,'-o','%cpu,%mem,vsz,rss,pri'], stdout=subprocess.PIPE)
            ps = sep.split(r.stdout.decode('utf-8').split('\n')[1])

            data = {'cpu': ps[1], 'mem': ps[2], 'vsz': ps[3], 'rss': ps[4], 'pri': ps[5]}

            self.queue.put({'id': self.i, 'who': 'PsCollector', 'data': data})
        except IndexError:
            pass

class SystemCollector(Collector):
    def run(self):
        r = subprocess.run(['top', '-b', '-n', '1'], stdout=subprocess.PIPE)
        top = r.stdout.decode('utf-8').split("\n")
        load = float(top[0].split("load average: ")[1].split(", ")[0].replace(",","."))
        mem = None
        swap = None
        for l in top:
            if mem is not None and swap is not None:
                break # no need to parse more lines, got everything we want
            if l.startswith('MiB Mem'):
                mem = float(l.split(':')[1].split('free,')[1].split('used,')[0].strip().replace(",",".")) * 1024 # KiB
            elif l.startswith('MiB Swap'):
                swap = float(l.split(':')[1].split('free,')[1].split('used.')[0].strip().replace(",",".")) * 1024 # KiB

        rx = 0
        tx = 0
        net_if = os.environ.get('NET_IF')
        if net_if is not None:
            with open(f"/sys/class/net/{net_if}/statistics/rx_bytes", "r") as f:
                rx1 = int(f.readline())
            with open(f"/sys/class/net/{net_if}/statistics/tx_bytes", "r") as f:
                tx1 = int(f.readline())
            time.sleep(1)
            with open(f"/sys/class/net/{net_if}/statistics/rx_bytes", "r") as f:
                rx = int(f.readline()) - rx1
            with open(f"/sys/class/net/{net_if}/statistics/tx_bytes", "r") as f:
                tx = int(f.readline()) - tx1
            rx = rx / 1024 # KiB/s
            tx = tx / 1024 # KiB/s

        # send data to queue
        data = {'load': load, 'mem': mem, 'swap': swap, 'net_rx': rx, 'net_tx': tx}
        self.queue.put({'id': self.i, 'who': 'SystemCollector', 'data': data})

class BirdCollector (Collector):

    def run(self):
        protocols = {} # name: established
        num_established = 0
        received_pfx = 0
        accepted_pfx = 0
        received_withdraw = 0
        accepted_withdraw = 0

        sep = re.compile('[\s]+')

        sockets = []
        if os.environ.get('BIRD_SOCKETS') is not None:
            for s in os.environ.get('BIRD_SOCKETS').split(','):
                if stat.S_ISSOCK(os.stat(s).st_mode):
                    sockets.append(s)
        if len(sockets) == 0:
            sockets.append('/var/run/bird.ctl')

        for socket in sockets:
            # get list of BGP protocols
            r = subprocess.run(['birdc','-s',socket,"show protocols"], stdout=subprocess.PIPE)
            for p in r.stdout.decode('utf-8').split("\n"):
                p = sep.split(p)
                if len(p) >= 2 and p[1] == 'BGP':
                    protocols[p[0]] = p[5] == 'Established'
                    if p[5] == 'Established':
                        num_established += 1

            # sum up prefixes received in protocols
            for protocol in protocols.keys():
                r = subprocess.run(['birdc','-s',socket,f'show protocols all {protocol}'], stdout=subprocess.PIPE)
                r = r.stdout.decode('utf-8')
                if 'Import updates:' in r:
                    for l in r.split("\n"):
                        if 'Import updates:' in l:
                            l = sep.split(l)
                            received_pfx += int(l[3])
                            accepted_pfx += int(l[7])
                        elif 'Import withdraws:' in l:
                            l = sep.split(l)
                            received_withdraw += int(l[3])
                            accepted_withdraw += int(l[7])

        # get memory usage (all in kB)
        mem_tables = 0
        mem_attr = 0
        mem_total = 0
        for socket in sockets:
            r = subprocess.run(['birdc','-s',socket,f'show memory'], stdout=subprocess.PIPE)
            for l in r.stdout.decode('utf-8').split("\n"):
                if 'Routing tables:' in l:
                    l = sep.split(l)
                    mem_tables += self._memCalc(l[2], l[3])
                elif 'Route attributes:' in l:
                    l = sep.split(l)
                    mem_attr += self._memCalc(l[2], l[3])
                elif 'Total:' in l:
                    l = sep.split(l)
                    mem_total += self._memCalc(l[1], l[2])

        # send data to queue
        data = {'established': num_established, 'mem_tables': mem_tables, 'mem_attr': mem_attr, 'mem_total': mem_total, 'received_pfx': received_pfx, 'accepted_pfx': accepted_pfx, 'received_withdraw': received_withdraw, 'accepted_withdraw': accepted_withdraw}
        self.queue.put({'id': self.i, 'who': 'BirdCollector', 'data': data})

    def _memCalc(self, number, unit):
        # calculates memory to kB from given unit (B, kB, mB, gB)
        unit = unit.lower()
        number = float(number)

        if unit == 'kb':
            return number
        elif unit == 'b':
            return number / 1024
        elif unit == 'mb':
            return number * 1024
        elif unit == 'gb':
            return number * 1024 * 1024
        else:
            return False


if __name__ == "__main__":
    controller = Controller()

    hostname = '0.0.0.0'
    port = 8080
    Server.controller = controller
    server = HTTPServer((hostname, port), Server)
    if os.environ.get('NET_IF') is None:
        print("Set NET_IF environment variable to interface name if you want to monitor network traffic.\n")
    else:
        print("Network traffic is monitored at interface "+os.environ.get('NET_IF'))
    if os.environ.get('BIRD_SOCKETS') is None:
        print("Set BIRD_SOCKETS environment variable to a comma separated list of socket files for BIRD daemons to collect statistics from. Default: /var/run/bird.ctl\n")
    else:
        print("Monitored BIRD sockets "+os.environ.get('BIRD_SOCKETS'))
    print(f"Listening on http://{hostname}:{port} for commands:")
    print(f"   http://{hostname}:{port}/start?comment=foo   Start new measurement, write `foo` as comment to result file")
    print(f"   http://{hostname}:{port}/stop                Stop measurement")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("Not longer listening.")
