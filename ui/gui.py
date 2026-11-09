#!/usr/bin/env python3
"""
Simple GUI front-end for the UDP Service Discovery demo.

The GUI itself runs as a normal program on the VM. When you press Discover,
it runs the existing client (client/client.py) inside Mininet host h3 using
mnexec, feeds it the service name, and shows the result. All discovery
traffic is therefore still real UDP going through the SDN switch.

Usage (after the registry, server and registration steps are running):
    sudo -v
    python3 ui/gui.py
"""
import os
import subprocess
import threading
import tkinter as tk

BASE = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.normpath(os.path.join(BASE, "..", "client", "client.py"))

# colours
BG = "#f4f6f8"
HEADER = "#1f3a5f"
GREEN = "#2e8b57"
ORANGE = "#e08e0b"
RED = "#c0392b"
GREY = "#7f8c8d"
CARD = "#ffffff"


def detect_h3_pid():
    """Find the pid of Mininet host h3 (the same number shown by `dump`)."""
    try:
        out = subprocess.run(["pgrep", "-f", "mininet:h3"],
                             capture_output=True, text=True).stdout.split()
        return out[0] if out else ""
    except Exception:
        return ""


def run_client(pid, service):
    """Run client.py inside h3, give it the service name, return (stdout, stderr)."""
    cmd = ["sudo", "-n", "mnexec", "-a", pid, "python3", CLIENT]
    result = subprocess.run(cmd, input=service + "\n", capture_output=True,
                            text=True, timeout=20)
    return result.stdout, result.stderr


class App:
    def __init__(self, root):
        self.root = root
        root.title("UDP Service Discovery - Demo")
        root.geometry("640x620")
        root.configure(bg=BG)

        self.service = tk.StringVar(value="video")
        self.pid = tk.StringVar()

        # header
        head = tk.Frame(root, bg=HEADER)
        head.pack(fill="x")
        tk.Label(head, text="UDP Service Discovery", bg=HEADER, fg="white",
                 font=("Helvetica", 18, "bold")).pack(pady=(12, 0))
        tk.Label(head, text="Client h3 (10.0.0.3)  \u2192  Registry h1 (10.0.0.1)  \u2192  Server h2 (10.0.0.2)",
                 bg=HEADER, fg="#c9d6e8", font=("Helvetica", 10)).pack(pady=(2, 12))

        # input card
        card = tk.Frame(root, bg=CARD, bd=1, relief="solid")
        card.pack(fill="x", padx=16, pady=(14, 8))

        tk.Label(card, text="Service name", bg=CARD,
                 font=("Helvetica", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 2))
        row = tk.Frame(card, bg=CARD)
        row.grid(row=1, column=0, sticky="w", padx=12)
        tk.Entry(row, textvariable=self.service, width=22,
                 font=("Helvetica", 12)).pack(side="left")
        for name in ("video", "audio"):
            tk.Button(row, text=name, width=7,
                      command=lambda n=name: self.service.set(n)).pack(side="left", padx=(8, 0))

        tk.Label(card, text="h3 process id (from `dump`)", bg=CARD,
                 font=("Helvetica", 10, "bold")).grid(row=2, column=0, sticky="w", padx=12, pady=(10, 2))
        row2 = tk.Frame(card, bg=CARD)
        row2.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 12))
        tk.Entry(row2, textvariable=self.pid, width=12,
                 font=("Helvetica", 12)).pack(side="left")
        tk.Button(row2, text="Auto-detect", command=self.detect).pack(side="left", padx=(8, 0))

        self.go = tk.Button(root, text="Discover service", bg=HEADER, fg="white",
                            font=("Helvetica", 12, "bold"), padx=20, pady=6,
                            command=self.discover)
        self.go.pack(pady=6)

        # status badge
        self.status = tk.Label(root, text="Ready", bg=GREY, fg="white",
                               font=("Helvetica", 14, "bold"), width=30, pady=8)
        self.status.pack(pady=(6, 8))

        # message flow
        flow = tk.Frame(root, bg=CARD, bd=1, relief="solid")
        flow.pack(fill="x", padx=16)
        tk.Label(flow, text="Message flow", bg=CARD,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.steps = []
        for text in ("Client \u2192 Registry : DISCOVER",
                     "Registry \u2192 Client : SERVICE / NOT_FOUND",
                     "Client \u2192 Server : REQUEST",
                     "Server \u2192 Client : SUCCESS"):
            lab = tk.Label(flow, text="\u2022  " + text, bg=CARD, fg=GREY,
                           font=("Helvetica", 11), anchor="w")
            lab.pack(fill="x", padx=12)
            self.steps.append((lab, text))
        tk.Label(flow, text="", bg=CARD).pack(pady=2)

        # details
        self.detail = tk.Label(root, text="", bg=BG, font=("Helvetica", 11), justify="left")
        self.detail.pack(anchor="w", padx=18, pady=(8, 2))

        tk.Label(root, text="Raw client output", bg=BG, fg=GREY,
                 font=("Helvetica", 9)).pack(anchor="w", padx=18)
        self.log = tk.Text(root, height=6, font=("Courier", 9), bg="#101820", fg="#d6e2f0")
        self.log.pack(fill="both", expand=True, padx=16, pady=(2, 14))

        self.detect()

    # ---- helpers ----
    def detect(self):
        pid = detect_h3_pid()
        if pid:
            self.pid.set(pid)

    def set_step(self, i, mark, colour):
        lab, text = self.steps[i]
        lab.config(text=mark + "  " + text, fg=colour)

    def reset_steps(self):
        for i in range(4):
            self.set_step(i, "\u2022", GREY)

    def set_status(self, text, colour):
        self.status.config(text=text, bg=colour)

    # ---- actions ----
    def discover(self):
        service = self.service.get().strip()
        pid = self.pid.get().strip()
        if not service:
            self.set_status("Enter a service name", ORANGE)
            return
        if not pid.isdigit():
            self.set_status("Enter the h3 pid (or press Auto-detect)", ORANGE)
            return
        self.go.config(state="disabled")
        self.reset_steps()
        self.detail.config(text="")
        self.set_status("Discovering...", GREY)
        self.log.delete("1.0", "end")

        def work():
            try:
                out, err = run_client(pid, service)
            except subprocess.TimeoutExpired:
                out, err = "", "The client took too long to answer."
            except Exception as exc:
                out, err = "", str(exc)
            self.root.after(0, lambda: self.show(service, out, err))

        threading.Thread(target=work, daemon=True).start()

    def show(self, service, out, err):
        self.go.config(state="normal")
        self.log.insert("end", out + (("\n" + err) if err.strip() else ""))

        if "password is required" in err or "a terminal is required" in err:
            self.set_status("Run `sudo -v` in the terminal first", ORANGE)
            return
        if not out and ("No such file" in err or "not found" in err.lower()):
            self.set_status("Could not run the client in h3", RED)
            self.detail.config(text="Check Mininet is running and the h3 pid is correct.")
            return

        registry = reply = ""
        for line in out.splitlines():
            if "Registry response:" in line:
                registry = line.split("Registry response:", 1)[1].strip()
            elif "Service response:" in line:
                reply = line.split("Service response:", 1)[1].strip()

        if registry:
            self.set_step(0, "\u2714", GREEN)
        else:
            self.set_step(0, "\u2718", RED)

        if registry.startswith("SERVICE|"):
            parts = registry.split("|")
            ip = parts[2] if len(parts) > 2 else "?"
            port = parts[3] if len(parts) > 3 else "?"
            self.set_step(1, "\u2714", GREEN)
            self.set_step(2, "\u2714", GREEN)
            if reply.startswith("SUCCESS"):
                self.set_step(3, "\u2714", GREEN)
                self.set_status("SERVICE AVAILABLE", GREEN)
                msg = reply.split("|", 2)[-1] if "|" in reply else reply
                self.detail.config(text="Service '%s' found at %s:%s\nServer says: %s"
                                   % (service, ip, port, msg))
            else:
                self.set_step(3, "\u2718", RED)
                self.set_status("SERVER NOT RESPONDING", RED)
                self.detail.config(text="Service '%s' is registered at %s:%s,\nbut the server did not answer (timeout)."
                                   % (service, ip, port))
        elif registry.startswith("NOT_FOUND"):
            self.set_step(1, "!", ORANGE)
            self.set_status("SERVICE NOT FOUND", ORANGE)
            self.detail.config(text="The registry has no service called '%s'." % service)
        elif not registry:
            self.set_status("REGISTRY NOT RESPONDING", RED)
            self.detail.config(text="No answer from the registry. Is it running in h1?")
        else:
            self.set_status("UNEXPECTED RESPONSE", GREY)
            self.detail.config(text=registry)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
