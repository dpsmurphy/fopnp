#!/usr/bin/python

import argparse
import os
import sys
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet, makeTerms
from mininet.node import OVSController
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

this_dir = os.path.dirname(os.path.abspath(__file__))

class RoutedTopo(Topo):
    def __init__(self, **opts):
        Topo.__init__(self, **opts)

        backbone = self.addHost('backbone', ip='10.1.1.1/32')

        # The ISP and its customers.

        isp = self.addHost('isp', ip='10.25.1.1/32')
        self.addLink(isp, backbone)

        modemA = self.addHost('modemA', ip='10.25.1.65/24')
        modemB = self.addHost('modemB', ip='10.25.1.66/24')

        h1 = self.addHost('h1', ip='192.168.1.11/24')
        h2 = self.addHost('h2', ip='192.168.1.12/24')
        h3 = self.addHost('h3', ip='192.168.1.13/24')

        h4 = self.addHost('h4', ip='192.168.1.11/24')

        self.addLink(modemA, isp)
        self.addLink(modemB, isp)

        sA = self.addSwitch('s1')
        sB = self.addSwitch('s2')

        self.addLink(modemA, sA)
        self.addLink(h1, sA)
        self.addLink(h2, sA)
        self.addLink(h3, sA)

        self.addLink(modemB, sB)
        self.addLink(h4, sB)

        # The example.com corporation.

        example = self.addHost('example', ip='10.130.1.1/32')
        self.addLink(backbone, example)

        ftp = self.addHost('ftp', ip='10.130.1.2/24')
        mail = self.addHost('mail', ip='10.130.1.3/24')
        www = self.addHost('www', ip='10.130.1.4/24')

        s3 = self.addSwitch('s3')

        self.addLink(example, s3)
        self.addLink(ftp, s3)
        self.addLink(mail, s3)
        self.addLink(www, s3)

def configure_network(net):
    hosts = 'h1', 'h2', 'h3', 'h4'
    modems = 'modemA', 'modemB'
    gateways = 'isp', 'backbone', 'example'
    servers = 'ftp', 'mail', 'www'

    for host in hosts:
        net[host].cmd('ip route add default via 192.168.1.1')

    for modem in modems:
        net[modem].cmd('ip addr add 192.168.1.1/24 dev %s-eth1' % modem)
        net[modem].cmd('ip route add default via 10.25.1.1')
        net[modem].cmd('iptables --table nat --append POSTROUTING'
                       ' --out-interface %s-eth0 -j MASQUERADE' % modem)

    net['isp'].cmd('ip addr add 10.25.1.1/32 dev isp-eth1')
    net['isp'].cmd('ip addr add 10.25.1.1/32 dev isp-eth2')

    net['isp'].cmd('ip route add 10.1.1.1/32 dev isp-eth0')
    net['isp'].cmd('ip route add 10.25.1.65/32 dev isp-eth1')
    net['isp'].cmd('ip route add 10.25.1.66/32 dev isp-eth2')
    net['isp'].cmd('ip route add default via 10.1.1.1')

    net['backbone'].cmd('ip addr add 10.1.1.1/32 dev backbone-eth1')

    net['backbone'].cmd('ip route add 10.25.1.1/32 dev backbone-eth0')
    net['backbone'].cmd('ip route add 10.25.0.0/16 via 10.25.1.1')

    net['backbone'].cmd('ip route add 10.130.1.1/32 dev backbone-eth1')
    net['backbone'].cmd('ip route add 10.130.1.0/24 via 10.130.1.1')

    net['example'].cmd('ip addr add 10.130.1.1/24 dev example-eth1')

    net['example'].cmd('ip route add 10.1.1.1/32 dev example-eth0')
    net['example'].cmd('ip route add default via 10.1.1.1')

    for server in servers:
        net[server].cmd('ip route add default via 10.130.1.1')

    for gateway in gateways + modems:
        net[gateway].cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')

def start_dns(net):
    """Start dnsmasq on every server.

    Since all network programs share the parent host's /etc/resolv.conf
    which, per Ubuntu practice, points at localhost, we simply provide
    each host with its own loopback-bound copy of dnsmasq that is hard
    coded to serve up IPs from our custom hosts file.  Works great.

    """
    for host in net.hosts:
        host.cmd('dnsmasq --interface=lo --no-dhcp-interface=lo'
                 ' --no-daemon --no-resolv --no-hosts'
                 ' --addn-hosts=/home/brandon/fopnp/playground/services/hosts &')
        host.cleanup_commands.append('kill %dnsmasq')

def start_httpd(net):
    net['www'].cmd('cd %s' % this_dir)
    net['www'].cmd('cd ../py3')
    net['www'].cmd('python ../playground/services/httpd.py'
                   ' ../playground/certs/www.pem &')
    net['www'].cleanup_commands.append('kill %python')

def start_services(net):
    for host in net.hosts:
        host.cleanup_commands = []
    start_dns(net)
    start_httpd(net)

def main(do_interactive):
    topo = RoutedTopo()
    net = Mininet(topo, controller=OVSController)
    net.start()
    try:
        configure_network(net)
        print "Host connections:"
        dumpNodeConnections(net.hosts)
        if do_interactive:
            start_services(net)
            hosts = [net['h1'], net['h4']]
            net.terms += makeTerms(hosts, 'host')  # net.hosts
            CLI(net)
        else:
            net.pingAll()
    finally:
        for host in net.hosts:
            for command in getattr(host, 'cleanup_commands'):
                try:
                    host.cmd(command)
                except:
                    print >>sys.stderr, 'Error on %s: %r' % (host.name, command)
        net.stop()

    #net['isp'].cmd('ip
    #net['h2'].cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A simple Mininet with a router')
    parser.add_argument('-i', action='store_true',
                        help='run interactively with xterms and a cli')
    args = parser.parse_args()
    setLogLevel('info')
    main(args.i)