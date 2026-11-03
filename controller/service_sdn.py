from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

# UDP ports used by our service-discovery application
SERVICE_PORTS = {5000: "REGISTRY", 5001: "VIDEO-SERVER"}


class ServiceSwitch(object):
    def __init__(self, connection):
        self.connection = connection
        self.mac_to_port = {}
        connection.addListeners(self)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            return
        in_port = event.port
        self.mac_to_port[packet.src] = in_port

        ip_pkt = packet.find("ipv4")
        udp_pkt = packet.find("udp")
        is_service = (ip_pkt is not None and udp_pkt is not None and
                      (udp_pkt.dstport in SERVICE_PORTS or
                       udp_pkt.srcport in SERVICE_PORTS))

        if is_service:
            role = SERVICE_PORTS.get(udp_pkt.dstport) or SERVICE_PORTS.get(udp_pkt.srcport)
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
                # High-priority rule specific to service-discovery UDP traffic
                msg.match = of.ofp_match.from_packet(packet, in_port)
                msg.priority = 200
                msg.idle_timeout = 60
                log.info("Installed HIGH-PRIORITY UDP flow (port %s -> %s)",
                         in_port, out_port)
            else:
                # Generic L2 rule for everything else (ARP, ICMP, ...)
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
            log.info("Switch %s connected - service-aware controller active", event.dpid)
            ServiceSwitch(event.connection)
        core.openflow.addListenerByName("ConnectionUp", up)
    core.call_when_ready(start, "openflow")

