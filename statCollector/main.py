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
    starttime = None
    queue = Queue()
    running_childs_count = 0

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
                # we use  _  as a representation for None in our CSV output
                t = int(time.time()) - self.starttime
                self.data[i] = {'time': t, 'sys_load': 0, 'sys_mem': 0, 'sys_swap': 0, 'sys_net_rx': 0, 'sys_net_tx': 0, 'ps_cpu': 0, 'ps_mem': 0, 'ps_vsz': 0, 'ps_rss': 0, 'ps_pri': 0,
                                'bird_established': '_', 'bird_mem_tables': '_', 'bird_mem_attr': '_', 'bird_mem_total': '_', 'bird_received_pfx': '_', 'bird_accepted_pfx': '_', 'bird_received_withdraw': '_', 'bird_accepted_withdraw': '_'}

                # collect system statistics
                sys = SystemCollector(self.queue, i, self.running_childs_count)
                sys.start()

                # collect bird process statistics
                ps = PsCollector(self.queue, i, self.running_childs_count)
                ps.start()

                # collect bird statistics (only every 10s, as it is quite expensive)
                if i % 10 == 1:
                    bird = BirdCollector(self.queue, i, self.running_childs_count)
                    bird.start()

                i += 1
                time.sleep(1)

        def read():
            # fetch statistics from queue and write them to data
            while True:
                new = self.queue.get()
                try:
                    d = self.data[new['id']]
                except KeyError:
                    continue
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
        self.starttime = int(time.time())

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

        print("Waiting for childs to finish...")
        while self.running_childs_count > 0:
            print(f"Running childs: {self.running_childs_count}", end="\r")
            time.sleep(0.5)
        print("")

        # wait for empty queue
        print("Waiting to empty queue...")
        time.sleep(1)
        while not self.queue.empty():
            time.sleep(0.5)
        print("Queue is empty now. Writing to file...")

        # write data to file
        with open(f"stats_{self.starttime}", "w") as f:
            f.write(f"START:{self.starttime}\n")
            f.write(f"COMMENT:{self.comment}\n")
            f.write(f"NUM_CPU:{self.num_cpu}\n")
            f.write(f"TOTAL_RAM:{self.total_ram}\n")
            f.write(f"TOTAL_SWAP:{self.total_swap}\n")
            f.write("COLUMNS:idx,time,sys_load,sys_mem,sys_swap,sys_net_rx,sys_net_tx,ps_cpu,ps_mem,ps_vsz,ps_rss,ps_pri,bird_established,bird_mem_tables,bird_mem_attr,bird_mem_total,bird_received_pfx,bird_accepted_pfx,bird_received_withdraw,bird_accepted_withdraw\n")
            f.write("===DATA===\n")
            for i, row in self.data.items():
                f.write(f"{i},{row['time']},{row['sys_load']},{row['sys_mem']},{row['sys_swap']},{row['sys_net_rx']},{row['sys_net_tx']},{row['ps_cpu']},{row['ps_mem']},{row['ps_vsz']},{row['ps_rss']},{row['ps_pri']},{row['bird_established']},{row['bird_mem_tables']},{row['bird_mem_attr']},{row['bird_mem_total']},{row['bird_received_pfx']},{row['bird_accepted_pfx']},{row['bird_received_withdraw']},{row['bird_accepted_withdraw']}\n")
        self.data = {}

class Collector:
    t = None
    queue = None
    i = None
    running_childs_count = None

    def __init__(self, q, i, running_childs_count):
        self.queue = q
        self.i = i
        self.running_childs_count = running_childs_count

    def run(self):
        raise NotImplementedError

    def start(self):
        self.t = Thread(target=self.run)
        self.t.daemon = True
        self.t.start()
        self.running_childs_count += 1

class PsCollector(Collector):

    t = None
    queue = None
    i = None
    pids = [] # IPv4, IPv6

    def __init__(self, q, i, running_childs_count):
        super().__init__(q, i, running_childs_count)
        pid_v4 = subprocess.run(["systemctl", "show", "--property", "MainPID", "--value", "bird@globepeer-ipv4"], stdout=subprocess.PIPE).stdout.decode('utf-8').split("\n")[0]
        pid_v6 = subprocess.run(["systemctl", "show", "--property", "MainPID", "--value", "bird@globepeer-ipv6"], stdout=subprocess.PIPE).stdout.decode('utf-8').split("\n")[0]

        self.pids = [pid_v4, pid_v6]

    def run(self):
        data = {'cpu': '', 'mem': '', 'vsz': '', 'rss': '', 'pri': ''}
        for pid in self.pids:
            try:
                sep = re.compile('[\s]+')
                r = subprocess.run(['ps','-p',pid,'-o','%cpu,%mem,vsz,rss,pri'], stdout=subprocess.PIPE)
                ps = sep.split(r.stdout.decode('utf-8').split('\n')[1].lstrip())

                # data['cpu'] = data['cpu'] + '|' + ps[0] # this data is not momentary, but for total process runtime
                data['mem'] = data['mem'] + '|' + ps[1]
                data['vsz'] = data['vsz'] + '|' + ps[2]
                data['rss'] = data['rss'] + '|' + ps[3]
                data['pri'] = data['pri'] + '|' + ps[4]

                r = subprocess.run(['top', '-b', '-n', '1', '-p', pid], stdout=subprocess.PIPE)
                r = r.stdout.decode('utf-8').split("\n")
                top = sep.split(r[len(r)-2].lstrip())
                data['cpu'] = data['cpu'] + '|' + top[8].replace(',','.')


            except IndexError:
                pass

        data['cpu'] = data['cpu'][1:]
        data['mem'] = data['mem'][1:]
        data['vsz'] = data['vsz'][1:]
        data['rss'] = data['rss'][1:]
        data['pri'] = data['pri'][1:]

        self.queue.put({'id': self.i, 'who': 'PsCollector', 'data': data})
        self.running_childs_count -= 1

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
        self.running_childs_count -= 1

class BirdCollector (Collector):

    def run(self):
        protocols = {} # name: established

        sep = re.compile('[\s]+')

        sockets = []
        socket_v4 = subprocess.run(["systemctl", "show", "--property", "ExecStart", "--value", "bird@globepeer-ipv4"], stdout=subprocess.PIPE).stdout.decode('utf-8').split("\n")[0].split(" ")
        for e in socket_v4:
            if e.endswith(".ctl"):
                socket_v4 = e
                break
        socket_v6 = subprocess.run(["systemctl", "show", "--property", "ExecStart", "--value", "bird@globepeer-ipv6"], stdout=subprocess.PIPE).stdout.decode('utf-8').split("\n")[0].split(" ")
        for e in socket_v6:
            if e.endswith(".ctl"):
                socket_v6 = e
                break
        sockets = [socket_v4, socket_v6]

        established = ''
        received_pfx = ''
        accepted_pfx = ''
        received_withdraw = ''
        accepted_withdraw = ''
        mem_tables = ''
        mem_attr = ''
        mem_total = ''
        for socket in sockets:
            num_established = 0
            num_received_pfx = 0
            num_accepted_pfx = 0
            num_received_withdraw = 0
            num_accepted_withdraw = 0

            # get list of BGP protocols
            r = subprocess.run(['birdc','-s',socket,"show protocols"], stdout=subprocess.PIPE)
            for p in r.stdout.decode('utf-8').split("\n"):
                p = sep.split(p)
                if len(p) >= 2 and p[1] == 'BGP':
                    protocols[p[0]] = p[6] == 'Established'
                    if p[6] == 'Established':
                        num_established += 1

            # sum up prefixes received in protocols
            for protocol in protocols.keys():
                r = subprocess.run(['birdc','-s',socket,f'show protocols all {protocol}'], stdout=subprocess.PIPE)
                r = r.stdout.decode('utf-8')
                if 'Import updates:' in r:
                    for l in r.split("\n"):
                        if 'Import updates:' in l:
                            l = sep.split(l)
                            num_received_pfx += int(l[3])
                            num_accepted_pfx += int(l[7])
                        elif 'Import withdraws:' in l:
                            l = sep.split(l)
                            num_received_withdraw += int(l[3])
                            num_accepted_withdraw += int(l[7])

            established = established + '|' + str(num_established)
            received_pfx = received_pfx + '|' + str(num_received_pfx)
            accepted_pfx = accepted_pfx + '|' + str(num_accepted_pfx)
            received_withdraw = received_withdraw + '|' + str(num_received_withdraw)
            accepted_withdraw = accepted_withdraw + '|' + str(num_accepted_withdraw)

            # get memory usage (all in kB)
            r = subprocess.run(['birdc','-s',socket,f'show memory'], stdout=subprocess.PIPE)
            for l in r.stdout.decode('utf-8').split("\n"):
                if 'Routing tables:' in l:
                    l = sep.split(l)
                    mem_tables = f"{mem_tables}|{self._memCalc(l[2], l[3])}"
                elif 'Route attributes:' in l:
                    l = sep.split(l)
                    mem_attr = f"{mem_attr}|{self._memCalc(l[2], l[3])}"
                elif 'Total:' in l:
                    l = sep.split(l)
                    mem_total = f"{mem_total}|{self._memCalc(l[1], l[2])}"

        established = established[1:]
        received_pfx = received_pfx[1:]
        accepted_pfx = accepted_pfx[1:]
        received_withdraw = received_withdraw[1:]
        accepted_withdraw = accepted_withdraw[1:]
        mem_tables = mem_tables[1:]
        mem_attr = mem_attr[1:]
        mem_total = mem_total[1:]

        # send data to queue
        data = {'established': established, 'mem_tables': mem_tables, 'mem_attr': mem_attr, 'mem_total': mem_total, 'received_pfx': received_pfx, 'accepted_pfx': accepted_pfx, 'received_withdraw': received_withdraw, 'accepted_withdraw': accepted_withdraw}
        self.queue.put({'id': self.i, 'who': 'BirdCollector', 'data': data})
        self.running_childs_count -= 1

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
    print("Sockets and PID of BIRD will be extracted from systemd services: bird@globepeer-ipv4, bird@globepeer-ipv6")
    print("")
    print(f"Listening on http://{hostname}:{port} for commands:")
    print(f"   http://{hostname}:{port}/start?comment=foo   Start new measurement, write `foo` as comment to result file")
    print(f"   http://{hostname}:{port}/stop                Stop measurement")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("Not longer listening.")
