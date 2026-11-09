import os

from pox.core import core
from pox.lib.addresses import IPAddr
from pox.lib.recoco import Timer
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

SERVICE_PORTS = {5000: "REGISTRY", 5001: "SERVER-PRIMARY", 5002: "SERVER-BACKUP"}
EVENT_FILE = "/tmp/registry_events.log"
DROP_PRIORITY = 300

connections = {}   # dpid -> connection
blocked = set()    # (ip string, port int) of servers that expired
state = {"offset": 0}


def drop_match(ip, port):
    return of.ofp_match(dl_type=0x0800, nw_proto=17,
                        nw_dst=IPAddr(ip), tp_dst=int(port))


def block_server(ip, port):
    blocked.add((ip, int(port)))
    for conn in connections.values():
        for field in ("nw_dst", "nw_src"):
            msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
            msg.match = of.ofp_match(dl_type=0x0800, **{field: IPAddr(ip)})
            conn.send(msg)
        drop = of.ofp_flow_mod()
        drop.match = drop_match(ip, port)
        drop.priority = DROP_PRIORITY
        conn.send(drop)
    log.info("SDN REACTION: server %s:%s EXPIRED -> deleted its flows, "
             "installed DROP rule", ip, port)


def unblock_server(ip, port):
    blocked.discard((ip, int(port)))
    for conn in connections.values():
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE_STRICT)
        msg.match = drop_match(ip, port)
        msg.priority = DROP_PRIORITY
        conn.send(msg)
    log.info("SDN REACTION: server %s:%s is BACK -> removed DROP rule",
             ip, port)


def handle_event(line):
    parts = line.split("|")
    if len(parts) != 4:
        return
    kind, name, ip, port = parts
    log.info("REGISTRY EVENT: %s", line)
    if kind == "EXPIRED":
        block_server(ip, port)
    elif kind == "REGISTERED" and (ip, int(port)) in blocked:
        unblock_server(ip, port)


def check_events():
    try:
        size = os.path.getsize(EVENT_FILE)
    except OSError:
        return True
    if size < state["offset"]:
        state["offset"] = 0
    if size == state["offset"]:
        return True
    with open(EVENT_FILE) as f:
        f.seek(state["offset"])
        lines = f.read().splitlines()
        state["offset"] = f.tell()
    for line in lines:
        line = line.strip()
        if line:
            handle_event(line)
    return True


class ServiceSwitch(object):
    def __init__(self, connection):
        self.connection = connection
        self.mac_to_port = {}
        connections[connection.dpid] = connection
        connection.addListeners(self)

    def _handle_PacketIn(self, event):
        try:
            packet = event.parsed
        except Exception:
            return
        if packet is None or not packet.parsed:
            return
        in_port = event.port
        self.mac_to_port[packet.src] = in_port

        ip_pkt = packet.find("ipv4")
        udp_pkt = packet.find("udp")

        if (ip_pkt is not None and udp_pkt is not None and
                (str(ip_pkt.dstip), udp_pkt.dstport) in blocked):
            log.info("DROPPED packet to blocked server %s:%s",
                     ip_pkt.dstip, udp_pkt.dstport)
            return

        is_service = (ip_pkt is not None and udp_pkt is not None and
                      (udp_pkt.dstport in SERVICE_PORTS or
                       udp_pkt.srcport in SERVICE_PORTS))

        if is_service:
            role = (SERVICE_PORTS.get(udp_pkt.dstport) or
                    SERVICE_PORTS.get(udp_pkt.srcport))
            try:
                text = bytes(udp_pkt.payload).decode(errors="replace").strip()
            except Exception:
                text = "?"
            log.info("SERVICE-TRAFFIC [%s] %s:%s -> %s:%s | %s",
                     role, ip_pkt.srcip, udp_pkt.srcport,
                     ip_pkt.dstip, udp_pkt.dstport, text)

        if packet.dst in self.mac_to_port:
            out_port = self.mac_to_port[packet.dst]
            msg = of.ofp_flow_mod()
            if is_service:
                msg.match = of.ofp_match.from_packet(packet, in_port)
                msg.priority = 200
                msg.idle_timeout = 60
            else:
                msg.match = of.ofp_match(dl_src=packet.src, dl_dst=packet.dst)
                msg.priority = 10
                msg.idle_timeout = 60
            msg.actions.append(of.ofp_action_output(port=out_port))
            msg.data = event.ofp
            self.connection.send(msg)
        else:
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.in_port = in_port
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            self.connection.send(msg)


def launch():
    def start():
        def up(event):
            log.info("Switch %s connected - dynamic service controller active",
                     event.dpid)
            ServiceSwitch(event.connection)
        core.openflow.addListenerByName("ConnectionUp", up)
        Timer(1, check_events, recurring=True)
    core.call_when_ready(start, "openflow")
