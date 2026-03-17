#!/usr/bin/env python3
"""SysMonitor - GUI system resource monitor (RAM/CPU/SWAP)."""

import math
import os
import subprocess
import time
from collections import defaultdict

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import psutil

# --- Configuration ---
RAM_WARNING = 80
RAM_CRITICAL = 90
SWAP_WARNING = 70
CHECK_INTERVAL = 3
NOTIFY_COOLDOWN = 300

# --- Color palette ---
C_BG        = "#0d1117"
C_SURFACE   = "#161b22"
C_SURFACE2  = "#1c2333"
C_BORDER    = "#30363d"
C_TEXT      = "#e6edf3"
C_DIM       = "#7d8590"
C_GREEN     = "#3fb950"
C_YELLOW    = "#d29922"
C_RED       = "#f85149"
C_BLUE      = "#58a6ff"
C_CYAN      = "#39d353"
C_ACCENT    = "#58a6ff"
C_ACCENT2   = "#3fb950"
C_BAR_BG    = "#21262d"
C_HEADER    = "#010409"

CSS = f"""
window {{
    background-color: {C_BG};
    color: {C_TEXT};
}}

.header {{
    background-color: {C_HEADER};
    padding: 12px 24px;
    border-bottom: 1px solid {C_BORDER};
}}

.app-title {{
    color: {C_TEXT};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1px;
}}

.status-ok   {{ color: {C_GREEN}; font-weight: 600; font-size: 12px; }}
.status-warn {{ color: {C_YELLOW}; font-weight: 600; font-size: 12px; }}
.status-crit {{ color: {C_RED}; font-weight: 600; font-size: 12px; }}

.metric-card {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 16px 20px;
}}

.card-label {{
    color: {C_DIM};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

.big-value {{
    font-size: 32px;
    font-weight: 700;
}}
.val-green  {{ color: {C_GREEN}; }}
.val-yellow {{ color: {C_YELLOW}; }}
.val-red    {{ color: {C_RED}; }}

.detail-text {{
    color: {C_DIM};
    font-size: 11px;
}}

.section-box {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 14px;
}}

.section-title {{
    color: {C_ACCENT};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* TreeView */
treeview {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    font-family: "Inter", "SF Pro", "Segoe UI", sans-serif;
    font-size: 12px;
}}
treeview:selected {{
    background-color: rgba(88, 166, 255, 0.25);
    color: #ffffff;
}}
treeview header button {{
    background-color: {C_SURFACE2};
    color: {C_DIM};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    font-weight: 600;
    font-size: 11px;
    padding: 8px 10px;
}}

.btn {{
    background: {C_SURFACE2};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 500;
}}
.btn:hover {{
    background: {C_BORDER};
    border-color: {C_ACCENT};
}}

.btn-danger {{
    background: rgba(248, 81, 73, 0.15);
    color: {C_RED};
    border: 1px solid rgba(248, 81, 73, 0.4);
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
.btn-danger:hover {{
    background: rgba(248, 81, 73, 0.3);
    border-color: {C_RED};
}}
.btn-danger:disabled {{
    background: {C_SURFACE2};
    color: {C_DIM};
    border: 1px solid {C_BORDER};
}}

.btn-warn {{
    background: rgba(210, 153, 34, 0.15);
    color: {C_YELLOW};
    border: 1px solid rgba(210, 153, 34, 0.4);
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
.btn-warn:hover {{
    background: rgba(210, 153, 34, 0.3);
    border-color: {C_YELLOW};
}}
.btn-warn:disabled {{
    background: {C_SURFACE2};
    color: {C_DIM};
    border: 1px solid {C_BORDER};
}}

.log-section {{
    background-color: {C_HEADER};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 10px;
}}

.log-title {{
    color: {C_YELLOW};
    font-size: 12px;
    font-weight: 600;
}}

.log-text {{
    background-color: {C_HEADER};
    color: {C_DIM};
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 11px;
}}
"""


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


import threading

_cpu_value = 0.0
_cpu_lock = threading.Lock()

def _cpu_monitor():
    """Thread measuring CPU with interval=1 — stable reading."""
    global _cpu_value
    while True:
        v = psutil.cpu_percent(interval=2)
        with _cpu_lock:
            _cpu_value = v

_cpu_thread = threading.Thread(target=_cpu_monitor, daemon=True)
_cpu_thread.start()

def get_memory_stats():
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    with _cpu_lock:
        cpu = _cpu_value
    return {
        "ram_percent": ram.percent,
        "ram_total_mb": ram.total / (1024 ** 2),
        "ram_available_mb": ram.available / (1024 ** 2),
        "ram_used_mb": ram.used / (1024 ** 2),
        "swap_percent": swap.percent,
        "swap_total_mb": swap.total / (1024 ** 2),
        "swap_used_mb": swap.used / (1024 ** 2),
        "cpu_percent": cpu,
    }


def _get_parent_info(pid):
    """Returns 'name (PID)' of the parent process."""
    try:
        p = psutil.Process(pid)
        parent = p.parent()
        if parent:
            return f"{parent.name()} ({parent.pid})"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return ""


def _get_cwd(pid):
    """Returns the working directory of the process."""
    try:
        return psutil.Process(pid).cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return ""


def _shorten_cmdline(cmdline_list):
    """Shortens cmdline to a readable form. E.g. java -> shows -jar/classname."""
    if not cmdline_list:
        return ""
    full = " ".join(cmdline_list)
    # For java: show the important parts (-jar xxx, -cp, main class)
    if len(full) > 200:
        # Keep first 200 characters
        return full[:200] + "…"
    return full


# Known process patterns that can often be killed
_STALE_PATTERNS = {
    "gradle": "Gradle daemon - eats RAM even when not building",
    "grunt": "Task runner - check if still needed",
    "webpack": "Bundler - may be running in the background unnecessarily",
    "eslint_d": "ESLint daemon - restart if consuming too much",
    "tsserver": "TypeScript server - restart if consuming too much",
}

# Recommendation colors
REC_COLORS = {
    "remove":  C_RED,
    "check":   C_YELLOW,
    "ok":      C_DIM,
}


def _recommend(proc):
    """Analyzes a process and returns (recommendation, color, tooltip_description).

    cpu_ratio = total CPU time / wall time * 100
    - > 5% = process is actively working
    - < 0.1% and old = almost certainly idle
    """

    name = proc["name"].lower()
    rss = proc["rss_mb"]
    cpu_ratio = proc.get("cpu_ratio", 50)
    age_h = proc["uptime_s"] / 3600
    status = proc["status"]
    cmdline = proc.get("desc", "").lower()

    idle = cpu_ratio < 0.5  # < 0.5% CPU time vs wall time = idle
    low_activity = cpu_ratio < 2

    # Zombie - always remove
    if status == "zombie":
        return "ZOMBIE - remove", REC_COLORS["remove"], "Zombie process - dead, occupies an entry in the process table"

    # Stopped
    if status == "stopped":
        return "Stopped", REC_COLORS["remove"], "Stopped process (SIGSTOP) - probably unnecessary"

    # Known patterns - daemons that like to linger in memory
    for pattern, hint in _STALE_PATTERNS.items():
        if pattern in name or pattern in cmdline:
            if idle and age_h > 1:
                return "Unnecessary?", REC_COLORS["remove"], hint
            elif age_h > 0.5:
                return "Check", REC_COLORS["check"], hint

    # Old + high RAM + idle
    if rss > 500 and idle and age_h > 4:
        return "Old, idle", REC_COLORS["remove"], (
            f"Running for {age_h:.0f}h, consuming {rss:.0f} MB, CPU ratio={cpu_ratio:.1f}%.\n"
            f"Probably unused - consider closing."
        )
    if rss > 200 and idle and age_h > 8:
        return "Old, idle", REC_COLORS["remove"], (
            f"Running for {age_h:.0f}h, consuming {rss:.0f} MB.\n"
            f"Check if still needed."
        )

    # High RAM + low activity
    if rss > 500 and low_activity and age_h > 2:
        return "Large, low activity", REC_COLORS["check"], (
            f"Consuming {rss:.0f} MB, CPU ratio={cpu_ratio:.1f}%. Running for {age_h:.1f}h.\n"
            f"May be needed, but worth checking."
        )

    # Medium age, lots of RAM, low activity
    if rss > 300 and low_activity and age_h > 4:
        return "Check", REC_COLORS["check"], (
            f"{rss:.0f} MB RAM, CPU ratio={cpu_ratio:.1f}%, running for {age_h:.1f}h."
        )

    # Active
    if cpu_ratio > 5:
        return "", REC_COLORS["ok"], ""

    return "", REC_COLORS["ok"], ""


def get_top_processes(n=20):
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "create_time",
                                   "username", "status", "cpu_percent",
                                   "exe", "cmdline", "ppid", "cpu_times"]):
        try:
            info = p.info
            rss_mb = info["memory_info"].rss / (1024 ** 2) if info["memory_info"] else 0
            if rss_mb < 1:
                continue
            uptime = time.time() - info["create_time"] if info["create_time"] else 0

            exe = info.get("exe") or ""
            cmdline = info.get("cmdline") or []
            cmdline_str = _shorten_cmdline(cmdline)
            if not exe and cmdline:
                exe = cmdline[0]

            pid = info["pid"]
            safety = classify_process(pid)
            parent_info = _get_parent_info(pid)
            cwd = _get_cwd(pid)

            # Description: readable summary of what it is
            desc = cmdline_str or exe or info["name"] or "?"

            # Tooltip: full info
            tooltip_parts = []
            if cmdline_str:
                tooltip_parts.append(f"Command: {cmdline_str}")
            if exe:
                tooltip_parts.append(f"Exe: {exe}")
            if cwd:
                tooltip_parts.append(f"Directory: {cwd}")
            if parent_info:
                tooltip_parts.append(f"Parent: {parent_info}")
            tooltip = "\n".join(tooltip_parts)

            # cpu_times gives total CPU time - better activity indicator than cpu_percent
            cpu_times = info.get("cpu_times")
            cpu_total_s = (cpu_times.user + cpu_times.system) if cpu_times else 0
            # CPU time to wall time ratio - how much the process uses CPU
            cpu_ratio = (cpu_total_s / uptime * 100) if uptime > 60 else 50  # new processes = unknown

            proc_data = {
                "pid": pid,
                "name": info["name"] or "?",
                "rss_mb": rss_mb,
                "uptime_s": uptime,
                "username": info["username"] or "?",
                "status": info["status"] or "?",
                "cpu": info["cpu_percent"] or 0,
                "cpu_ratio": cpu_ratio,
                "exe": exe or "",
                "safety": safety,
                "desc": desc,
                "tooltip": tooltip,
                "parent": parent_info,
                "cwd": cwd,
            }

            # Recommendation
            rec_label, rec_color, rec_tip = _recommend(proc_data)
            proc_data["rec_label"] = rec_label
            proc_data["rec_color"] = rec_color
            if rec_tip:
                tooltip += f"\n\n→ {rec_tip}"
                proc_data["tooltip"] = tooltip

            procs.append(proc_data)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    procs.sort(key=lambda x: x["rss_mb"], reverse=True)
    return procs[:n]


def group_by_name(processes):
    groups = defaultdict(lambda: {"count": 0, "total_mb": 0.0, "pids": []})
    for p in processes:
        g = groups[p["name"]]
        g["count"] += 1
        g["total_mb"] += p["rss_mb"]
        g["pids"].append(p["pid"])
    result = [(name, d["count"], d["total_mb"], d["pids"]) for name, d in groups.items()]
    result.sort(key=lambda x: x[2], reverse=True)
    return result


def format_uptime(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def format_mb(mb):
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


# Critical system processes - never kill
CRITICAL_PROCS = {
    "systemd", "init", "kthreadd", "ksoftirqd", "kworker", "rcu_gp",
    "rcu_par_gp", "rcu_sched", "migration", "watchdog", "cpuhp",
    "netns", "kauditd", "khungtaskd", "oom_reaper", "kcompactd0",
    "kdevtmpfs", "writeback", "kintegrityd", "kblockd", "blkcg_punt_bio",
    "ata_sff", "md", "edac-poller", "devfreq_wq", "kswapd0",
    "ecryptfs", "kthrotld", "irq", "scsi", "dm_bufio_cache",
    "jbd2", "ext4", "xfs", "btrfs",
    "Xorg", "Xwayland", "gnome-shell", "plasmashell", "kwin",
    "gdm", "sddm", "lightdm", "login", "dbus-daemon",
    "NetworkManager", "wpa_supplicant", "dhclient",
    "pulseaudio", "pipewire", "pipewire-pulse", "wireplumber",
    "polkitd", "udisksd", "upower", "thermald", "acpid",
    "cron", "rsyslogd", "journald", "systemd-logind",
    "systemd-udevd", "systemd-resolved", "systemd-timesyncd",
}

# Important but not critical processes (use caution)
IMPORTANT_PROCS = {
    "sshd", "bash", "zsh", "fish", "tmux", "screen",
    "docker", "containerd", "snapd",
    "nautilus", "dolphin", "thunar",  # file managers
    "gnome-terminal", "konsole", "xterm", "alacritty", "kitty",
}


def classify_process(pid):
    """Classifies a process. Returns: 'safe', 'important', 'system', 'critical'."""
    if pid < 100:
        return "critical"
    if pid == os.getpid():
        return "critical"
    try:
        p = psutil.Process(pid)
        name = p.name()
        user = p.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "system"

    # Kernel processes (PID < 1000 and root)
    if pid < 1000 and user == "root":
        return "critical"

    # By name
    if name in CRITICAL_PROCS:
        return "critical"
    if name in IMPORTANT_PROCS:
        return "important"

    # Root = system
    if user == "root":
        return "system"

    return "safe"


def is_safe_to_kill(pid):
    return classify_process(pid) == "safe"


# Labels and colors for categories
SAFETY_INFO = {
    "safe":      ("Safe to kill", C_GREEN),
    "important": ("Caution",      C_YELLOW),
    "system":    ("System",       C_RED),
    "critical":  ("DO NOT KILL",  C_RED),
}


def kill_process_safe(pid):
    try:
        p = psutil.Process(pid)
        name = p.name()
        safety = classify_process(pid)
        if safety in ("system", "critical"):
            return False, f"Denied: PID {pid} ({name}) - system/critical process"
        p.terminate()
        try:
            p.wait(timeout=5)
            return True, f"Terminated: PID {pid} ({name})"
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=3)
            return True, f"Killed (SIGKILL): PID {pid} ({name})"
    except psutil.NoSuchProcess:
        return True, f"PID {pid} - no longer exists"
    except psutil.AccessDenied:
        return False, f"PID {pid} - access denied"
    except Exception as e:
        return False, f"PID {pid} - error: {e}"


def send_notification(title, message, urgency="normal"):
    try:
        subprocess.run(
            ["notify-send", f"--urgency={urgency}", "--app-name=SysMonitor", title, message],
            timeout=5, capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


# ── Custom drawn widgets ─────────────────────────────────────────


class ArcGauge(Gtk.DrawingArea):
    """Arc-shaped percentage gauge."""

    def __init__(self, color_hex, warn=80, crit=90):
        super().__init__()
        self.value = 0
        self.color_hex = color_hex
        self.warn = warn
        self.crit = crit
        self.set_size_request(80, 40)
        self.connect("draw", self._draw)

    def set_value(self, v):
        self.value = v
        self.queue_draw()

    def _draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx = w / 2
        cy = h - 4
        radius = min(w / 2 - 10, h - 12)
        if radius < 10:
            return

        line_w = 10
        start_a = math.pi
        end_a = 2 * math.pi

        # arc background
        cr.set_line_width(line_w)
        cr.set_line_cap(1)  # round
        r, g, b = hex_to_rgb(C_BAR_BG)
        cr.set_source_rgb(r, g, b)
        cr.arc(cx, cy, radius, start_a, end_a)
        cr.stroke()

        # fill
        if self.value >= self.crit:
            col = C_RED
        elif self.value >= self.warn:
            col = C_YELLOW
        else:
            col = self.color_hex

        fill_a = start_a + (end_a - start_a) * min(self.value / 100, 1)
        r, g, b = hex_to_rgb(col)

        # glow effect
        cr.set_line_width(line_w + 6)
        cr.set_source_rgba(r, g, b, 0.12)
        cr.arc(cx, cy, radius, start_a, fill_a)
        cr.stroke()

        # main arc
        cr.set_line_width(line_w)
        cr.set_source_rgb(r, g, b)
        cr.arc(cx, cy, radius, start_a, fill_a)
        cr.stroke()


# ── Main window ──────────────────────────────────────────────────

class SysMonitorApp(Gtk.Window):

    def __init__(self):
        super().__init__(title="SysMonitor")
        self.set_default_size(1100, 800)
        self.set_icon_name("utilities-system-monitor")

        self.last_notify = {"warning": 0, "critical": 0, "swap": 0}
        self._selected_pids = set()
        self._update_count = 0
        self._refreshing = False  # blocks changed signal during refresh
        self._user_selected = False  # True when user has selected something

        # CSS
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        # ── Header ──
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        hdr.get_style_context().add_class("header")

        lbl = Gtk.Label(label="SYSMONITOR")
        lbl.get_style_context().add_class("app-title")
        hdr.pack_start(lbl, False, False, 0)

        self.status_lbl = Gtk.Label(label="...")
        self.status_lbl.get_style_context().add_class("status-ok")
        hdr.pack_start(self.status_lbl, False, False, 0)

        self.time_lbl = Gtk.Label()
        self.time_lbl.get_style_context().add_class("detail-text")
        hdr.pack_end(self.time_lbl, False, False, 0)

        root.pack_start(hdr, False, False, 0)

        # ── Content ──
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(14)
        content.set_margin_end(14)
        content.set_margin_top(10)
        content.set_margin_bottom(10)

        # ── Metrics + charts (2 rows in one section) ──
        metrics_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        metrics_row.set_homogeneous(True)

        self.ram_w = self._build_metric("RAM", C_GREEN, RAM_WARNING, RAM_CRITICAL)
        self.swap_w = self._build_metric("SWAP", C_CYAN, SWAP_WARNING, 90)
        self.cpu_w = self._build_metric("CPU", C_ACCENT, 80, 95)

        metrics_row.pack_start(self.ram_w["box"], True, True, 0)
        metrics_row.pack_start(self.swap_w["box"], True, True, 0)
        metrics_row.pack_start(self.cpu_w["box"], True, True, 0)

        content.pack_start(metrics_row, False, False, 0)

        # ── Processes + log in paned ──
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)

        proc_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        proc_section.get_style_context().add_class("section-box")

        # Header with buttons
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        title = Gtk.Label(label="TOP PROCESSES (by RAM)")
        title.get_style_context().add_class("section-title")
        title.set_halign(Gtk.Align.START)
        toolbar.pack_start(title, True, True, 0)

        self.pause_lbl = Gtk.Label(label="")
        self.pause_lbl.get_style_context().add_class("status-warn")
        toolbar.pack_start(self.pause_lbl, False, False, 4)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.get_style_context().add_class("btn")
        refresh_btn.connect("clicked", lambda _: self._refresh_procs_manual())
        toolbar.pack_end(refresh_btn, False, False, 0)

        cache_btn = Gtk.Button(label="Clear cache")
        cache_btn.get_style_context().add_class("btn")
        cache_btn.connect("clicked", self._on_drop_caches)
        toolbar.pack_end(cache_btn, False, False, 0)

        swap_btn = Gtk.Button(label="Clear SWAP")
        swap_btn.get_style_context().add_class("btn")
        swap_btn.connect("clicked", self._on_clear_swap)
        toolbar.pack_end(swap_btn, False, False, 0)

        self.kill_group_btn = Gtk.Button(label="Kill group")
        self.kill_group_btn.get_style_context().add_class("btn-warn")
        self.kill_group_btn.connect("clicked", self._on_kill_group)
        self.kill_group_btn.set_sensitive(False)
        toolbar.pack_end(self.kill_group_btn, False, False, 0)

        self.kill_btn = Gtk.Button(label="Kill selected")
        self.kill_btn.get_style_context().add_class("btn-danger")
        self.kill_btn.connect("clicked", self._on_kill_selected)
        self.kill_btn.set_sensitive(False)
        toolbar.pack_end(self.kill_btn, False, False, 0)

        desel_btn = Gtk.Button(label="Deselect")
        desel_btn.get_style_context().add_class("btn")
        desel_btn.connect("clicked", lambda _: self._deselect_all())
        toolbar.pack_end(desel_btn, False, False, 0)

        proc_section.pack_start(toolbar, False, False, 0)

        # TreeView
        # 0:PID  1:Name  2:RAM_MB  3:CPU%  4:Uptime  5:User  6:Status
        # 7:safe(bool)  8:exe  9:safety_label  10:safety_color
        # 11:desc(cmdline)  12:tooltip  13:parent
        # 14:rec_label  15:rec_color
        self.store = Gtk.ListStore(
            int, str, float, float, str, str, str,
            bool, str, str, str,
            str, str, str,
            str, str,
        )
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)
        self.tree.set_enable_search(True)
        self.tree.set_search_column(1)
        self.tree.set_rubber_banding(True)
        self.tree.set_has_tooltip(True)
        self.tree.connect("query-tooltip", self._on_tooltip)
        self._mouse_over_tree = False
        self.tree.connect("enter-notify-event", lambda *_: setattr(self, '_mouse_over_tree', True))
        self.tree.connect("leave-notify-event", lambda *_: setattr(self, '_mouse_over_tree', False))

        sel = self.tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        sel.connect("changed", self._on_sel_changed)

        cols_def = [
            ("",           9,  "safety", 85),
            ("Advice",     14, "rec",    110),
            ("PID",        0,  "int",    60),
            ("Name",       1,  "str",    110),
            ("RAM",        2,  "ram",    70),
            ("CPU %",      3,  "pct",    50),
            ("Time",       4,  "str",    50),
            ("User",       5,  "str",    90),
            ("Parent",     13, "str",    100),
            ("Command",    11, "path",   250),
        ]
        for title, idx, fmt, width in cols_def:
            rend = Gtk.CellRendererText()
            if fmt in ("int", "ram", "pct"):
                rend.set_property("xalign", 1.0)
            if fmt == "path":
                rend.set_property("ellipsize", 3)  # END
            col = Gtk.TreeViewColumn(title or "Status", rend)
            col.set_resizable(True)
            col.set_sort_column_id(idx)
            col.set_min_width(width)
            col.set_cell_data_func(rend, self._render_row_color, (fmt, idx))
            if title in ("Name", "Command"):
                col.set_expand(True)
            self.tree.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(200)
        scroll.add(self.tree)
        proc_section.pack_start(scroll, True, True, 0)

        # Legend
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        for label, color in [("Safe to kill", C_GREEN), ("Caution", C_YELLOW),
                              ("System", C_RED), ("DO NOT KILL", C_RED)]:
            lbl = Gtk.Label()
            lbl.set_markup(f'<span foreground="{color}" font_weight="bold" font_size="small">{label}</span>')
            legend.pack_start(lbl, False, False, 0)
        proc_section.pack_start(legend, False, False, 0)

        self.groups_lbl = Gtk.Label()
        self.groups_lbl.get_style_context().add_class("detail-text")
        self.groups_lbl.set_halign(Gtk.Align.START)
        self.groups_lbl.set_line_wrap(True)
        self.groups_lbl.set_selectable(True)
        proc_section.pack_start(self.groups_lbl, False, False, 0)

        paned.pack1(proc_section, True, False)

        # ── Log ──
        log_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        log_section.get_style_context().add_class("log-section")

        log_title = Gtk.Label(label="LOG")
        log_title.get_style_context().add_class("log-title")
        log_title.set_halign(Gtk.Align.START)
        log_section.pack_start(log_title, False, False, 0)

        self.log_buf = Gtk.TextBuffer()
        log_view = Gtk.TextView(buffer=self.log_buf)
        log_view.get_style_context().add_class("log-text")
        log_view.set_editable(False)
        log_view.set_cursor_visible(False)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.log_tv = log_view

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_scroll.set_size_request(-1, 70)
        log_scroll.add(log_view)
        log_section.pack_start(log_scroll, True, True, 0)

        paned.pack2(log_section, False, True)
        paned.set_position(380)

        content.pack_start(paned, True, True, 0)
        root.pack_start(content, True, True, 0)

        # Init
        self._log("SysMonitor started")

        GLib.timeout_add(CHECK_INTERVAL * 1000, self._tick)
        GLib.idle_add(self._tick)

    # ── Building metric card ──

    def _build_metric(self, name, color, warn, crit):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("metric-card")

        # header with value
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        label = Gtk.Label(label=name)
        label.get_style_context().add_class("card-label")
        label.set_halign(Gtk.Align.START)
        top.pack_start(label, False, False, 0)

        value_lbl = Gtk.Label(label="--%")
        value_lbl.get_style_context().add_class("big-value")
        value_lbl.get_style_context().add_class("val-green")
        value_lbl.set_halign(Gtk.Align.END)
        top.pack_end(value_lbl, False, False, 0)

        box.pack_start(top, False, False, 0)

        # gauge
        gauge = ArcGauge(color, warn, crit)
        gauge.set_size_request(-1, 56)
        box.pack_start(gauge, True, True, 4)

        # details
        detail = Gtk.Label(label="")
        detail.get_style_context().add_class("detail-text")
        detail.set_halign(Gtk.Align.START)
        box.pack_start(detail, False, False, 0)

        return {
            "box": box, "value": value_lbl, "gauge": gauge,
            "detail": detail, "warn": warn, "crit": crit,
        }

    # ── Column renderers ──

    # Mapping fmt -> store column index (for types requiring manual text setting)
    _FMT_COL = {
        "safety": 9,
        "ram": 2,
        "pct": 3,
        "int": 0,
        "str": None,   # ustawiany dynamicznie z idx
        "path": None,
    }

    def _render_row_color(self, col, rend, model, it, data):
        """Universal renderer: sets text + row color."""
        fmt, idx = data
        safety_label = model.get_value(it, 9)
        safety_color = model.get_value(it, 10)

        # --- Set text ---
        if fmt == "safety":
            rend.set_property("text", safety_label)
            rend.set_property("foreground", safety_color)
            rend.set_property("weight", 600)
            return
        elif fmt == "rec":
            rec_text = model.get_value(it, 14)
            rec_color = model.get_value(it, 15)
            rend.set_property("text", rec_text or "")
            rend.set_property("foreground", rec_color or C_DIM)
            rend.set_property("weight", 600 if rec_text else 400)
            return
        elif fmt == "ram":
            rend.set_property("text", format_mb(model.get_value(it, idx)))
        elif fmt == "pct":
            rend.set_property("text", f"{model.get_value(it, idx):.1f}")
        elif fmt == "int":
            rend.set_property("text", str(model.get_value(it, idx)))
        else:
            # str, path
            rend.set_property("text", model.get_value(it, idx) or "")

        # --- Text color by safety level ---
        if safety_label in ("System", "DO NOT KILL"):
            rend.set_property("foreground", C_DIM)
        elif safety_label == "Caution":
            rend.set_property("foreground", C_YELLOW)
        else:
            rend.set_property("foreground", C_TEXT)

    def _on_tooltip(self, tree, x, y, keyboard_mode, tooltip):
        """Shows full process information in the tooltip."""
        result = tree.get_path_at_pos(x, y)
        if not result:
            return False
        path = result[0]
        it = self.store.get_iter(path)
        tip_text = self.store.get_value(it, 12)  # tooltip
        if not tip_text:
            return False
        tooltip.set_text(tip_text)
        tree.set_tooltip_row(tooltip, path)
        return True

    # ── Metric value update ──

    def _update_metric(self, w, value, detail_text):
        w["value"].set_text(f"{value:.1f}%")
        w["gauge"].set_value(value)
        w["detail"].set_text(detail_text)

        ctx = w["value"].get_style_context()
        for c in ("val-green", "val-yellow", "val-red"):
            ctx.remove_class(c)
        if value >= w["crit"]:
            ctx.add_class("val-red")
        elif value >= w["warn"]:
            ctx.add_class("val-yellow")
        else:
            ctx.add_class("val-green")

    # ── Main tick ──

    def _tick(self):
        stats = get_memory_stats()
        now = time.time()
        self._update_count += 1

        self.time_lbl.set_text(time.strftime("%H:%M:%S"))

        # Status
        ram = stats["ram_percent"]
        if ram >= RAM_CRITICAL:
            self.status_lbl.set_text("ALARM")
            self._set_status_class("status-crit")
        elif ram >= RAM_WARNING:
            self.status_lbl.set_text("WARNING")
            self._set_status_class("status-warn")
        else:
            self.status_lbl.set_text("OK")
            self._set_status_class("status-ok")

        # Metryki
        self._update_metric(self.ram_w, stats["ram_percent"],
            f"{format_mb(stats['ram_used_mb'])} / {format_mb(stats['ram_total_mb'])}  "
            f"free: {format_mb(stats['ram_available_mb'])}")
        self._update_metric(self.swap_w, stats["swap_percent"],
            f"{format_mb(stats['swap_used_mb'])} / {format_mb(stats['swap_total_mb'])}")
        self._update_metric(self.cpu_w, stats["cpu_percent"],
            f"{psutil.cpu_count()} cores")

        # Notifications
        if ram >= RAM_CRITICAL and now - self.last_notify["critical"] > NOTIFY_COOLDOWN:
            top3 = get_top_processes(3)
            top_str = ", ".join(f"{p['name']} ({format_mb(p['rss_mb'])})" for p in top3)
            send_notification("ALERT: RAM > 90%!", f"{ram:.0f}% | {top_str}", "critical")
            self.last_notify["critical"] = now
            self._log(f"ALERT RAM {ram:.1f}%")
        elif ram >= RAM_WARNING and now - self.last_notify["warning"] > NOTIFY_COOLDOWN:
            send_notification("RAM > 80%", f"{ram:.0f}%, free: {format_mb(stats['ram_available_mb'])}")
            self.last_notify["warning"] = now
            self._log(f"Warning RAM {ram:.1f}%")

        if stats["swap_percent"] >= SWAP_WARNING and now - self.last_notify["swap"] > NOTIFY_COOLDOWN:
            send_notification("SWAP > 70%", f"{stats['swap_percent']:.0f}%")
            self.last_notify["swap"] = now

        # Processes - don't refresh when user has selection or cursor over the list
        if not self._user_selected and not self._mouse_over_tree:
            self._refresh_procs()

        return True

    def _set_status_class(self, cls):
        ctx = self.status_lbl.get_style_context()
        for c in ("status-ok", "status-warn", "status-crit"):
            ctx.remove_class(c)
        ctx.add_class(cls)

    # ── Processes ──

    def _refresh_procs(self):
        self._refreshing = True
        sel = self.tree.get_selection()

        # Remember selected PIDs
        model, paths = sel.get_selected_rows()
        saved_pids = set()
        for path in paths:
            it = model.get_iter(path)
            saved_pids.add(model.get_value(it, 0))

        self.store.clear()
        procs = get_top_processes(20)

        restore_paths = []
        for i, p in enumerate(procs):
            safety = p.get("safety", "safe")
            label, color = SAFETY_INFO.get(safety, ("?", C_DIM))
            self.store.append([
                p["pid"], p["name"], p["rss_mb"], p["cpu"],
                format_uptime(p["uptime_s"]), p["username"], p["status"],
                safety == "safe", p.get("exe", ""),
                label, color,
                p.get("desc", ""), p.get("tooltip", ""), p.get("parent", ""),
                p.get("rec_label", ""), p.get("rec_color", C_DIM),
            ])
            if p["pid"] in saved_pids:
                restore_paths.append(i)

        # Restore selection
        if restore_paths:
            for i in restore_paths:
                sel.select_path(Gtk.TreePath(i))

        self._refreshing = False

        # Groups
        groups = group_by_name(procs)
        multi = [f"{name}: {cnt} proc., {format_mb(tot)}" for name, cnt, tot, _ in groups if cnt > 1]
        self.groups_lbl.set_text("  |  ".join(multi) if multi else "")

    def _refresh_procs_manual(self):
        """Manual refresh - resets selection."""
        self._user_selected = False
        self.pause_lbl.set_text("")
        self.tree.get_selection().unselect_all()
        self._refresh_procs()

    def _deselect_all(self):
        """Deselect all and resume auto-refresh."""
        self._user_selected = False
        self.pause_lbl.set_text("")
        self.tree.get_selection().unselect_all()
        self.kill_btn.set_sensitive(False)
        self.kill_group_btn.set_sensitive(False)

    # ── Events ──

    def _on_sel_changed(self, sel):
        if self._refreshing:
            return
        model, paths = sel.get_selected_rows()
        any_killable = False
        names = set()
        for path in paths:
            it = model.get_iter(path)
            safety_label = model.get_value(it, 9)
            # Can kill "safe" and "important" (with warning)
            if safety_label in ("Safe to kill", "Caution"):
                any_killable = True
            names.add(model.get_value(it, 1))

        has_sel = len(paths) > 0
        self._user_selected = has_sel
        self.pause_lbl.set_text("(auto-refresh paused)" if has_sel else "")
        self.kill_btn.set_sensitive(any_killable)
        self.kill_group_btn.set_sensitive(any_killable and len(names) == 1)

    def _on_kill_selected(self, _btn):
        sel = self.tree.get_selection()
        model, paths = sel.get_selected_rows()
        targets = []
        has_important = False
        for path in paths:
            it = model.get_iter(path)
            pid = model.get_value(it, 0)
            name = model.get_value(it, 1)
            rss = model.get_value(it, 2)
            safety_label = model.get_value(it, 9)
            if safety_label in ("Safe to kill", "Caution"):
                targets.append((pid, name, rss, safety_label))
                if safety_label == "Caution":
                    has_important = True

        if not targets:
            self._dialog("Cannot kill", "Selected processes are system/critical.")
            return

        desc = "\n".join(
            f"  {'⚠ ' if sl == 'Caution' else ''}{name}  PID {pid}  ({format_mb(rss)})"
            for pid, name, rss, sl in targets
        )
        warning = ""
        if has_important:
            warning = "\n\n⚠ WARNING: Selected processes marked as 'Caution' may be important for system operation!"
        if not self._confirm(f"Kill {len(targets)} processes?\n\n{desc}{warning}"):
            return

        for pid, name, rss, _ in targets:
            ok, msg = kill_process_safe(pid)
            self._log(msg)
        self._deselect_all()
        self._refresh_procs()

    def _on_kill_group(self, _btn):
        sel = self.tree.get_selection()
        model, paths = sel.get_selected_rows()
        if not paths:
            return
        it = model.get_iter(paths[0])
        gname = model.get_value(it, 1)

        targets = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                if p.info["name"] == gname and is_safe_to_kill(p.info["pid"]):
                    rss = p.info["memory_info"].rss / (1024**2) if p.info["memory_info"] else 0
                    targets.append((p.info["pid"], rss))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not targets:
            self._dialog("None", f"No '{gname}' processes to kill.")
            return

        total = sum(r for _, r in targets)
        if not self._confirm(
            f"Kill ALL '{gname}' processes?\n\n"
            f"Count: {len(targets)}\n"
            f"Total RAM: {format_mb(total)}"
        ):
            return

        killed = sum(1 for pid, _ in targets if kill_process_safe(pid)[0])
        self._log(f"Killed {killed}/{len(targets)} proc. '{gname}'")
        self._deselect_all()
        self._refresh_procs()

    def _on_clear_swap(self, _btn):
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        if ram.available < swap.used:
            self._log(f"Not enough free RAM ({format_mb(ram.available / (1024**2))}) "
                      f"for SWAP data ({format_mb(swap.used / (1024**2))})")
            if not self._confirm(
                f"Not enough free RAM!\n"
                f"Free RAM: {format_mb(ram.available / (1024**2))}\n"
                f"Used SWAP: {format_mb(swap.used / (1024**2))}\n\n"
                f"Continue anyway? The system may start killing processes (OOM)."):
                return
        else:
            if not self._confirm("Clear SWAP?\nRequires sudo password.\nMay take a while."):
                return
        self._log("Clearing SWAP...")
        try:
            subprocess.run(
                ["sudo", "swapoff", "-a"],
                check=True, timeout=120,
            )
            subprocess.run(
                ["sudo", "swapon", "-a"],
                check=True, timeout=30,
            )
            self._log("SWAP cleared")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self._log(f"Error clearing SWAP: {e}")
            # Try to re-enable swap
            subprocess.run(["sudo", "swapon", "-a"], timeout=30)

    def _on_drop_caches(self, _btn):
        if not self._confirm("Clear system cache?\nRequires sudo password."):
            return
        self._log("Clearing cache...")
        try:
            subprocess.run(
                ["sudo", "sh", "-c", "sync && echo 3 > /proc/sys/vm/drop_caches"],
                check=True, timeout=30,
            )
            self._log("Cache cleared")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self._log(f"Error: {e}")

    # ── Helpers ──

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        end = self.log_buf.get_end_iter()
        self.log_buf.insert(end, f"[{ts}] {msg}\n")
        GLib.idle_add(lambda: self.log_tv.scroll_to_iter(
            self.log_buf.get_end_iter(), 0, False, 0, 0) or False)

    def _confirm(self, msg):
        d = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO, text="Confirmation")
        d.format_secondary_text(msg)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.YES

    def _dialog(self, title, msg):
        d = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=title)
        d.format_secondary_text(msg)
        d.run()
        d.destroy()


def main():
    app = SysMonitorApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
