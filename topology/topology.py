from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import SingleSwitchTopo
from mininet.cli import CLI
from mininet.log import setLogLevel


def run():
    # 1 switch (s1) and 4 hosts: h1 registry, h2 primary, h3 backup, h4 client
    net = Mininet(topo=SingleSwitchTopo(4), controller=None, switch=OVSSwitch)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)
    net.start()
    print("Hosts: h1 10.0.0.1, h2 10.0.0.2, h3 10.0.0.3, h4 10.0.0.4")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
