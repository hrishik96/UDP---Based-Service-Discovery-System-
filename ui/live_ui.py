#!/usr/bin/env python3
"""
Live cyberpunk console for the UDP Service Discovery + SDN project.
Standard library only. Run with:  sudo python3 ui/live_ui.py
Then open http://localhost:8000 in the browser.

Real data: /tmp/registry_events.log, ovs-ofctl dump-flows / dump-ports on s1,
process checks. Real actions: discover from h4, kill / restore primary on h2.
"""
import json
import os
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EVENTS = "/tmp/registry_events.log"
SERVICE = "video"
PORT = 8000


def sh(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "ERR " + str(e)


def pid_of(host):
    out = sh(["pgrep", "-f", "mininet:" + host]).split()
    return out[0] if out and out[0].isdigit() else ""


def running(pattern):
    return sh(["pgrep", "-f", pattern]).strip().replace("ERR", "") != ""


def tail(path, n):
    try:
        with open(path) as f:
            return [l.rstrip() for l in f.readlines()[-n:]]
    except Exception:
        return []


def flows():
    out = sh(["ovs-ofctl", "dump-flows", "s1", "udp"])
    rows = []
    for line in out.splitlines():
        if "priority=" not in line:
            continue

        def g(p):
            m = re.search(p, line)
            return m.group(1) if m else ""

        act = line.split("actions=")[-1].strip() if "actions=" in line else "drop"
        rows.append({"pri": g(r"priority=(\d+)"), "src": g(r"nw_src=([\d.]+)"),
                     "dst": g(r"nw_dst=([\d.]+)"), "dport": g(r"tp_dst=(\d+)"),
                     "pkts": g(r"n_packets=(\d+)"), "act": act})
    return rows


def ports():
    out = sh(["ovs-ofctl", "dump-ports", "s1"])
    d = {}
    for m in re.finditer(r"port\s+\"?([\w-]+)\"?:\s+rx pkts=(\d+).*?\n\s+tx pkts=(\d+)", out):
        d[m.group(1)] = [int(m.group(2)), int(m.group(3))]
    return d


def state():
    return {
        "mininet": pid_of("h1") != "",
        "events": tail(EVENTS, 40),
        "flows": flows(),
        "ports": ports(),
        "nodes": {"h1": running("registry_v2.py"),
                  "h2": running("server_v2.py.*5001"),
                  "h3": running("server_v2.py.*5002")},
    }


def parse_ms(out):
    m = re.search(r"([\d.]+)\s*ms", out, re.I)
    return float(m.group(1)) if m else None


def burst(n=10):
    client = os.path.join(ROOT, "client", "client_v2.py")
    pids = [p for p in (pid_of("h3"), pid_of("h4")) if p]
    if not pids:
        return "h3 and h4 not found. Is Mininet running?"
    t0 = time.time()
    procs = []
    for i in range(n):
        cmd = ["mnexec", "-a", pids[i % len(pids)], "python3", client, "10.0.0.1", SERVICE]
        procs.append(subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True))
    ok, lats = 0, []
    for p in procs:
        try:
            out, _ = p.communicate(timeout=40)
        except Exception:
            p.kill()
            continue
        if "SUCCESS" in out or "served by" in out:
            ok += 1
        v = parse_ms(out)
        if v is not None:
            lats.append(v)
    wall = (time.time() - t0) * 1000
    if not lats:
        return "BURST clients=%d ok=%d (no latency found in client output, wall %.0f ms)" % (n, ok, wall)
    return "BURST clients=%d ok=%d mean=%.2f ms max=%.2f ms min=%.2f ms (wall %.0f ms)" % (
        n, ok, sum(lats) / len(lats), max(lats), min(lats), wall)


def action(name):
    if name == "burst":
        return burst()
    if name == "discover":
        pid = pid_of("h4")
        if not pid:
            return "h4 not found. Is Mininet running?"
        client = os.path.join(ROOT, "client", "client_v2.py")
        return sh(["mnexec", "-a", pid, "python3", client, "10.0.0.1", SERVICE], 30)
    if name == "kill":
        sh(["pkill", "-f", "server_v2.py.*5001"])
        return "Primary server (h2, port 5001) stopped. The registry expires it in about 9 s."
    if name == "restore":
        pid = pid_of("h2")
        if not pid:
            return "h2 not found. Is Mininet running?"
        if running("server_v2.py.*5001"):
            return "Primary is already running."
        server = os.path.join(ROOT, "server", "server_v2.py")
        subprocess.Popen(["mnexec", "-a", pid, "python3", server, "10.0.0.1", SERVICE, "5001"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return "Primary server restarted on h2. It re-registers within a few seconds."
    return "Unknown action"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, body, ctype="application/json", code=200):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def host_ok(self):
        return self.headers.get("Host", "").split(":")[0] in ("localhost", "127.0.0.1")

    def do_GET(self):
        if not self.host_ok():
            return self.reply("forbidden", "text/plain", 403)
        if self.path.startswith("/api/state"):
            self.reply(json.dumps(state()))
        else:
            self.reply(PAGE, "text/html")

    def do_POST(self):
        if not self.host_ok() or self.headers.get("X-Demo") != "1":
            return self.reply("forbidden", "text/plain", 403)
        m = re.match(r"/api/action/(\w+)", self.path)
        self.reply(json.dumps({"output": action(m.group(1)) if m else "bad request"}))


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>SDN // SERVICE DISCOVERY</title>
<style>
:root{--c:#00f0ff;--p:#ff2bd6;--y:#fcee0a;--r:#ff3860;--g:#39ff88;--dim:#6b7a99}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 50% 0,#171446,#070812 60%);color:#cfe9ff;font:13px/1.4 "Courier New",monospace;min-height:100vh}
body:after{content:"";position:fixed;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(0,240,255,.05) 0 1px,transparent 1px 3px)}
header{display:flex;justify-content:space-between;align-items:center;padding:14px 22px;border-bottom:1px solid var(--c);box-shadow:0 0 18px rgba(0,240,255,.35)}
h1{margin:0;font-size:22px;letter-spacing:4px;color:var(--c);text-shadow:2px 0 var(--p),-2px 0 var(--y);animation:gl 3s infinite}
@keyframes gl{0%,92%,100%{transform:none}94%{transform:translateX(3px);text-shadow:-4px 0 var(--p),4px 0 var(--y)}96%{transform:translateX(-3px)}}
.tag{color:var(--g);letter-spacing:2px;font-size:12px}.tag span{margin-left:18px}
.wrap{display:grid;grid-template-columns:2fr 1fr;gap:14px;padding:14px 22px}
.bottom{display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:14px;padding:0 22px 14px}
.card{border:1px solid rgba(0,240,255,.5);background:rgba(10,12,32,.82);padding:10px;box-shadow:0 0 16px rgba(0,240,255,.12) inset}
.card h2{margin:0 0 8px;font-size:12px;letter-spacing:3px;color:var(--p)}
canvas{width:100%;height:430px;display:block}
.btn{display:block;width:100%;margin:9px 0;padding:12px;background:transparent;color:var(--c);border:1px solid var(--c);font:inherit;letter-spacing:2px;cursor:pointer;clip-path:polygon(9px 0,100% 0,100% calc(100% - 9px),calc(100% - 9px) 100%,0 100%,0 9px)}
.btn:hover{background:var(--c);color:#000;box-shadow:0 0 18px var(--c)}
.btn.d{color:var(--r);border-color:var(--r)}.btn.d:hover{background:var(--r);box-shadow:0 0 18px var(--r)}
.btn.g{color:var(--g);border-color:var(--g)}.btn.g:hover{background:var(--g);box-shadow:0 0 18px var(--g)}
.btn.y{color:var(--y);border-color:var(--y)}.btn.y:hover{background:var(--y);box-shadow:0 0 18px var(--y)}
#story{margin:12px 22px 0;padding:10px 14px;border:1px solid var(--y);color:var(--y);letter-spacing:1px;display:grid;grid-template-columns:1fr 210px;gap:4px 14px;align-items:center}
#story .btn{margin:0;grid-row:1/3;grid-column:2}#sLook{color:#9ff;font-size:12px;letter-spacing:0}
.btn:disabled{opacity:.35;cursor:wait}
.nd{display:flex;align-items:center;gap:8px;padding:4px 0}.nd i{width:10px;height:10px;border-radius:50%}.nd b{margin-left:auto;font-size:11px}
.kpi{display:flex;justify-content:space-between;margin-top:10px;text-align:center}.kpi div{font-size:11px;color:var(--dim)}.kpi p{margin:0;font-size:22px;color:var(--y)}
.log{height:210px;overflow:auto;margin:0;white-space:pre-wrap;color:#9ff;font:12px "Courier New",monospace}
.r{color:var(--r)}.g{color:var(--g)}.dim{color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:3px 5px;text-align:left;border-bottom:1px solid #1b2350}th{color:var(--dim)}
tr.drop td{color:var(--r);animation:bl 1s infinite}@keyframes bl{50%{background:rgba(255,56,96,.18)}}
footer{padding:0 22px 18px;color:var(--dim);font-size:11px}
</style></head><body>
<header><h1>SDN // SERVICE DISCOVERY</h1><div class="tag"><span id="mn">MININET: ...</span><span id="conn">LINK: ...</span></div></header>
<div id="story"><div id="sTop"></div><div id="sLook"></div><button class="btn y" id="sBtn" onclick="guide()"></button></div>
<div class="wrap">
 <div class="card"><h2>LIVE TOPOLOGY</h2><canvas id="cv"></canvas></div>
 <div>
  <div class="card"><h2>CONTROL</h2>
   <button class="btn" id="bD" onclick="act('discover','discover video from h4')">&#9654; DISCOVER FROM H4</button>
   <button class="btn d" id="bK" onclick="act('kill','kill primary server on h2')">&#9760; KILL PRIMARY (H2)</button>
   <button class="btn g" id="bR" onclick="act('restore','restore primary server on h2')">&#8635; RESTORE PRIMARY</button>
   <button class="btn" onclick="act('burst','burst: 10 concurrent clients on h3 and h4')">&#9889; BURST: 10 CLIENTS</button></div>
  <div class="card" style="margin-top:14px"><h2>NODES</h2><div id="nodes"></div>
   <div class="kpi"><div><p id="kF">0</p>UDP FLOWS</div><div><p id="kD">0</p>DROP RULES</div><div><p id="kL">-</p>LAST LATENCY</div><div><p id="kB">-</p>BURST MEAN</div></div></div>
 </div>
</div>
<div class="bottom">
 <div class="card"><h2>TERMINAL</h2><pre class="log" id="term"></pre></div>
 <div class="card"><h2>REGISTRY EVENTS</h2><div class="log" id="ev"></div></div>
 <div class="card"><h2>SWITCH FLOW TABLE (UDP)</h2><div class="log"><table><thead><tr><th>PRI</th><th>SRC</th><th>DST</th><th>DPORT</th><th>PKTS</th><th>ACTION</th></tr></thead><tbody id="fl"></tbody></table></div></div>
</div>
<footer>Real data: registry event log, ovs-ofctl dump-flows and dump-ports. Glowing dots on links = real packet counts from the switch. Labelled dots after a discovery are an animated replay of the exchange.</footer>
<script>
const $=id=>document.getElementById(id);
const cv=$('cv'),cx=cv.getContext('2d');
const N={sw:{x:.5,y:.5,l:'S1',s:'SWITCH'},h1:{x:.14,y:.2,l:'H1',s:'REGISTRY'},h2:{x:.86,y:.2,l:'H2',s:'PRIMARY'},h3:{x:.86,y:.8,l:'H3',s:'BACKUP'},h4:{x:.14,y:.8,l:'H4',s:'CLIENT'}};
const COL={up:'#00f0ff',silent:'#fcee0a',blocked:'#ff3860',offline:'#4a5575'};
let LAST=null,prev=null,parts=[],busy=false,st={h1:'offline',h2:'offline',h3:'offline',h4:'offline'};
function fit(){cv.width=cv.clientWidth;cv.height=cv.clientHeight}
window.onresize=fit;fit();
const P=n=>({x:N[n].x*cv.width,y:N[n].y*cv.height});
function spawn(a,b,c,l){parts.push({a:P(a),b:P(b),t:0,v:.018+Math.random()*.008,c:c,l:l||''})}
function via(a,b,l,c){spawn(a,'sw',c,l);setTimeout(()=>spawn('sw',b,c,l),450)}
function hex(x,y,r){cx.beginPath();for(let i=0;i<6;i++){const a=Math.PI/3*i+Math.PI/6;cx.lineTo(x+r*Math.cos(a),y+r*Math.sin(a))}cx.closePath()}
function draw(ts){
 cx.clearRect(0,0,cv.width,cv.height);cx.lineWidth=1;cx.strokeStyle='rgba(0,240,255,.07)';
 for(let x=0;x<cv.width;x+=40){cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,cv.height);cx.stroke()}
 for(let y=0;y<cv.height;y+=40){cx.beginPath();cx.moveTo(0,y);cx.lineTo(cv.width,y);cx.stroke()}
 const s=P('sw');
 ['h1','h2','h3','h4'].forEach(h=>{const p=P(h),c=COL[st[h]];cx.strokeStyle=c;cx.shadowColor=c;cx.shadowBlur=10;cx.lineWidth=2;cx.setLineDash(st[h]==='blocked'?[7,7]:[]);cx.beginPath();cx.moveTo(s.x,s.y);cx.lineTo(p.x,p.y);cx.stroke()});
 cx.setLineDash([]);cx.shadowBlur=0;cx.textAlign='left';
 parts=parts.filter(p=>p.t<1);
 parts.forEach(p=>{p.t+=p.v;const x=p.a.x+(p.b.x-p.a.x)*p.t,y=p.a.y+(p.b.y-p.a.y)*p.t;cx.fillStyle=p.c;cx.shadowColor=p.c;cx.shadowBlur=14;cx.beginPath();cx.arc(x,y,p.l?5:3,0,7);cx.fill();if(p.l){cx.shadowBlur=0;cx.font='bold 11px Courier New';cx.fillText(p.l,x+8,y-8)}});
 cx.shadowBlur=0;cx.textAlign='center';
 Object.keys(N).forEach(k=>{const p=P(k),c=k==='sw'?'#ff2bd6':COL[st[k]];hex(p.x,p.y,34+(k==='sw'?3*Math.sin(ts/300):0));cx.fillStyle='#0a0c20';cx.fill();cx.strokeStyle=c;cx.shadowColor=c;cx.shadowBlur=16;cx.lineWidth=2;cx.stroke();cx.shadowBlur=0;cx.fillStyle=c;cx.font='bold 16px Courier New';cx.fillText(N[k].l,p.x,p.y+5);cx.font='11px Courier New';cx.fillText(N[k].s,p.x,p.y+54);if(k!=='sw'){cx.fillStyle='#8aa';cx.fillText(st[k].toUpperCase(),p.x,p.y+68)}});
 requestAnimationFrame(draw)}
requestAnimationFrame(draw);
const esc=t=>String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function calc(S){
 if(!S.mininet){st={h1:'offline',h2:'offline',h3:'offline',h4:'offline'};return}
 const bl=new Set(S.flows.filter(f=>f.act==='drop'&&f.dst).map(f=>'h'+f.dst.split('.')[3]));
 const f=(up,h)=>bl.has(h)?'blocked':(up?'up':'silent');
 st={h1:S.nodes.h1?'up':'offline',h2:f(S.nodes.h2,'h2'),h3:f(S.nodes.h3,'h3'),h4:'up'}}
function traffic(S){
 if(prev){for(const k in S.ports){const m=k.match(/(\d+)$/);if(!m||!prev[k])continue;const h='h'+m[1];if(!N[h])continue;
  const rx=Math.min(S.ports[k][0]-prev[k][0],4),tx=Math.min(S.ports[k][1]-prev[k][1],4);
  for(let i=0;i<rx;i++)setTimeout(()=>spawn(h,'sw','#00f0ff'),i*180);
  for(let i=0;i<tx;i++)setTimeout(()=>spawn('sw',h,'#ff2bd6'),i*180)}}
 prev=S.ports}
function render(S){
 LAST=S;calc(S);traffic(S);
 $('mn').textContent='MININET: '+(S.mininet?'ONLINE':'NOT FOUND');
 $('nodes').innerHTML=['h1','h2','h3','h4'].map(h=>`<div class="nd"><i style="background:${COL[st[h]]};box-shadow:0 0 8px ${COL[st[h]]}"></i>${N[h].l} ${N[h].s}<b style="color:${COL[st[h]]}">${st[h].toUpperCase()}</b></div>`).join('');
 $('kF').textContent=S.flows.length;$('kD').textContent=S.flows.filter(f=>f.act==='drop').length;
 const ev=$('ev');ev.innerHTML=S.events.length?S.events.map(l=>`<div class="${/EXPIRED/.test(l)?'r':/REGISTERED/.test(l)?'g':''}">${esc(l)}</div>`).join(''):'<div class="dim">no events yet</div>';ev.scrollTop=ev.scrollHeight;
 $('fl').innerHTML=S.flows.map(f=>`<tr class="${f.act==='drop'?'drop':''}"><td>${f.pri}</td><td>${f.src||'*'}</td><td>${f.dst||'*'}</td><td>${f.dport}</td><td>${f.pkts}</td><td>${esc(f.act)}</td></tr>`).join('')}
async function poll(){try{const r=await fetch('/api/state');render(await r.json());$('conn').textContent='LINK: ONLINE'}catch(e){$('conn').textContent='LINK: OFFLINE'}}
setInterval(poll,1000);poll();
function term(t){const e=$('term');e.textContent+=new Date().toLocaleTimeString()+'  '+t+'\n';e.scrollTop=e.scrollHeight}
function replay(o){
 const m=[...o.matchAll(/10\.0\.0\.([23])/g)],srv=m.length&&m[m.length-1][1]==='3'?'h3':'h2';
 const steps=/NOT_FOUND/.test(o)?[['h4','h1','DISCOVER'],['h1','h4','NOT_FOUND']]:[['h4','h1','DISCOVER'],['h1','h4','SERVICE'],['h4',srv,'REQUEST'],[srv,'h4','SUCCESS']];
 steps.forEach((s,i)=>setTimeout(()=>via(s[0],s[1],s[2],'#fcee0a'),i*1100))}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const lock=b=>document.querySelectorAll('.btn').forEach(x=>x.disabled=b);
const blocked=S=>S.flows.some(f=>f.act==='drop');
async function until(f,max){for(let i=0;i<max;i++){if(LAST&&f(LAST))return true;await sleep(1000)}return false}
async function call(n,msg){
 term('> '+msg);
 try{const r=await fetch('/api/action/'+n,{method:'POST',headers:{'X-Demo':'1'}});const j=await r.json();term(j.output.trim());
  if(n==='discover'){replay(j.output);const m=j.output.match(/([\d.]+)\s*ms/i);if(m)$('kL').textContent=m[1]+' ms'}
  if(n==='burst'){const m=j.output.match(/mean=([\d.]+)/);if(m)$('kB').textContent=m[1]+' ms'}}
 catch(e){term('request failed: '+e)}}
async function act(n,msg){if(busy)return;busy=true;lock(true);await call(n,msg);busy=false;lock(false)}
const G=[
 ['Discovery','The client only knows the registry. It asks for video and gets the server address back.','the terminal reply, the yellow message dots, and the LAST LATENCY box.',()=>call('discover','discover video from h4')],
 ['Many clients at once','Ten clients on two hosts ask the registry at the same time.','the BURST MEAN box and the terminal line with the number of successful clients.',()=>call('burst','burst: 10 concurrent clients on h3 and h4')],
 ['Kill the primary','We stop the primary server, so the registry stops hearing its heartbeat.','H2 turns yellow (SILENT), then red once the controller blocks it.',()=>call('kill','kill primary server on h2')],
 ['Controller reacts','After the registry timeout of about 9 s it expires the server, and the controller blocks it at the switch.','the EXPIRED line in registry events, the red dashed link to H2, DROP RULES = 1, and the red priority 300 row in the flow table.',async()=>{term('waiting for the DROP rule...');const ok=await until(blocked,30);term(ok?'DROP rule installed by the controller':'no DROP rule seen. Is POX running service_sdn_v2?')}],
 ['Client fails over','A new discovery request now returns the backup server on h3.','the terminal reply with 10.0.0.3 and port 5002, and the yellow dots going to H3.',()=>call('discover','discover video from h4')],
 ['Primary recovers','We restart the primary. It registers again and the controller removes the block.','a new REGISTERED line, DROP RULES back to 0, and the link to H2 turning cyan again.',async()=>{await call('restore','restore primary server on h2');const ok=await until(S=>!blocked(S),30);term(ok?'DROP rule removed':'DROP rule still present')}],
 ['Back to normal','Both servers are registered again and the same client code keeps working.','the terminal reply and the latency boxes.',()=>call('discover','discover video from h4')]];
let gi=0,gLook='';
function showGuide(){
 const done=gi>=G.length;
 $('sTop').innerHTML=done?'DEMO COMPLETE // press restart to run it again':'NEXT STEP '+(gi+1)+'/'+G.length+' // '+esc(G[gi][0])+' &mdash; '+esc(G[gi][1]);
 $('sLook').innerHTML=gLook;
 $('sBtn').innerHTML=done?'&#8635; RESTART':'RUN STEP '+(gi+1)+' &#9654;'}
async function guide(){
 if(busy)return;
 if(gi>=G.length){gi=0;gLook='';showGuide();return}
 busy=true;lock(true);const s=G[gi];
 $('sTop').innerHTML='RUNNING STEP '+(gi+1)+'/'+G.length+' // '+esc(s[0])+'...';
 await s[3]();
 gLook='LOOK AT: '+esc(s[2]);gi++;busy=false;lock(false);showGuide()}
showGuide();
</script></body></html>"""


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run with sudo:  sudo python3 ui/live_ui.py")
        sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("Live console on http://localhost:%d   (Ctrl+C to stop)" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
