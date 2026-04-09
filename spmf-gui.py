#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# spmf-client.py
# GUI client for SPMF-Server
#
# Copyright (C) 2026 Philippe Fournier-Viger
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
"""
spmf-gui.py
===========
Graphical client for SPMF-Server.

Requirements:
  pip install requests
  tkinter (built-in with standard Python on Windows/macOS/most Linux distros)

Usage:
  python spmf-gui.py
"""

import base64
import json
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

try:
    import requests
except ImportError:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Missing Dependency",
                         "'requests' is not installed.\n\nRun:  pip install requests")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────

VERSION      = "1.0.0"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8585

# ── Colour Palette ─────────────────────────────────────────────────────────────

DARK_BG      = "#1e1e2e"
PANEL_BG     = "#2a2a3e"
HEADER_BG    = "#12121e"
ACCENT       = "#7c6af7"
ACCENT_HOVER = "#9d8fff"
SUCCESS      = "#50fa7b"
ERROR_COL    = "#ff5555"
WARNING      = "#ffb86c"
TEXT_PRIMARY = "#f8f8f2"
TEXT_SEC     = "#aaaacc"
TEXT_DIM     = "#666688"
ENTRY_BG     = "#13131f"
BORDER       = "#3a3a5c"
TAG_BG       = "#3d3560"
CONSOLE_FG   = "#a8ff80"   # green tint for console output

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _headers(apikey: str) -> dict:
    h = {"Content-Type": "application/json"}
    if apikey:
        h["X-API-Key"] = apikey
    return h


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def api_get(host, port, apikey, path, timeout=15):
    url = _base_url(host, port) + path
    resp = requests.get(url, headers=_headers(apikey), timeout=timeout)
    return resp


def api_post(host, port, apikey, path, payload, timeout=30):
    url = _base_url(host, port) + path
    resp = requests.post(url, headers=_headers(apikey),
                         data=json.dumps(payload), timeout=timeout)
    return resp


def api_delete(host, port, apikey, path, timeout=15):
    url = _base_url(host, port) + path
    resp = requests.delete(url, headers=_headers(apikey), timeout=timeout)
    return resp


# ── Styled widget helpers ──────────────────────────────────────────────────────

def styled_button(parent, text, command, bg=ACCENT, fg=TEXT_PRIMARY,
                  width=None, font_size=10):
    kw = dict(
        text=text, command=command, bg=bg, fg=fg,
        relief="flat", cursor="hand2", font=("Segoe UI", font_size, "bold"),
        padx=12, pady=6, bd=0, activebackground=ACCENT_HOVER,
        activeforeground=TEXT_PRIMARY,
    )
    if width:
        kw["width"] = width
    btn = tk.Button(parent, **kw)

    def on_enter(_):
        btn.config(bg=ACCENT_HOVER)

    def on_leave(_):
        btn.config(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def card_frame(parent, **kw):
    return tk.Frame(parent, bg=PANEL_BG, bd=0,
                    highlightthickness=1, highlightbackground=BORDER, **kw)


# ══════════════════════════════════════════════════════════════════════════════
#  About Window
# ══════════════════════════════════════════════════════════════════════════════

class AboutWindow(tk.Toplevel):
    GPLv3_SUMMARY = (
        "This program is free software: you can redistribute it and/or\n"
        "modify it under the terms of the GNU General Public License as\n"
        "published by the Free Software Foundation, either version 3 of\n"
        "the License, or (at your option) any later version.\n"
        "\n"
        "This program is distributed in the hope that it will be useful,\n"
        "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
        "GNU General Public License for more details.\n"
        "\n"
        "You should have received a copy of the GNU General Public License\n"
        "along with this program.  If not, see:\n"
        "https://www.gnu.org/licenses/gpl-3.0.html"
    )

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("About SPMF Server Client")
        self.resizable(False, False)
        self.configure(bg=DARK_BG)
        self.grab_set()
        self.focus_set()
        self._build()
        self._center(parent)

    def _build(self):
        tk.Frame(self, bg=ACCENT, height=6).pack(fill="x", side="top")

        logo_frame = tk.Frame(self, bg=DARK_BG)
        logo_frame.pack(fill="x", padx=32, pady=(28, 0))
        tk.Label(logo_frame, text="⬡", bg=DARK_BG, fg=ACCENT,
                 font=("Segoe UI", 42)).pack(side="left", padx=(0, 16))

        title_block = tk.Frame(logo_frame, bg=DARK_BG)
        title_block.pack(side="left", anchor="w")
        tk.Label(title_block, text="SPMF Server Client", bg=DARK_BG,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 18, "bold"),
                 anchor="w").pack(anchor="w")
        tk.Label(title_block, text=f"Version {VERSION}", bg=DARK_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 10),
                 anchor="w").pack(anchor="w")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(20, 0))

        card = tk.Frame(self, bg=PANEL_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=24, pady=16)

        for label, value in [
            ("Author",    "Philippe Fournier-Viger"),
            ("Website",   "https://www.philippe-fournier-viger.com/spmf/"),
            ("License",   "GNU General Public License v3.0  (GPLv3)"),
            ("Copyright", "© Philippe Fournier-Viger.  All rights reserved."),
            ("Built with","Python  •  tkinter  •  requests"),
        ]:
            row = tk.Frame(card, bg=PANEL_BG)
            row.pack(fill="x", padx=20, pady=5)
            tk.Label(row, text=f"{label}:", bg=PANEL_BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), width=12,
                     anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 9), anchor="w").pack(side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(self,
                 text=("SPMF Server Client is a graphical interface for the SPMF\n"
                       "data mining server, allowing users to browse algorithms,\n"
                       "submit jobs, and view results — all without the command line."),
                 bg=DARK_BG, fg=TEXT_SEC, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=32, pady=(0, 12))

        tk.Label(self, text="License", bg=DARK_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=32, pady=(0, 4))

        lic_box = tk.Text(self, bg=ENTRY_BG, fg=TEXT_SEC, font=("Consolas", 8),
                          relief="flat", height=13, wrap="word", state="normal",
                          cursor="arrow", highlightthickness=1,
                          highlightbackground=BORDER)
        lic_box.insert("1.0", self.GPLv3_SUMMARY)
        lic_box.config(state="disabled")
        lic_box.pack(fill="x", padx=24, pady=(0, 12))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        bottom = tk.Frame(self, bg=DARK_BG)
        bottom.pack(fill="x", padx=24, pady=12)
        tk.Label(bottom, text="SPMF  —  Sequential Pattern Mining Framework",
                 bg=DARK_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "italic")).pack(side="left")
        tk.Button(bottom, text="Close", command=self.destroy,
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=20, pady=4,
                  activebackground=ACCENT_HOVER,
                  activeforeground=TEXT_PRIMARY).pack(side="right")

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        px = parent.winfo_x() + (parent.winfo_width()  // 2) - (w // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"+{px}+{py}")


# ══════════════════════════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════════════════════════

class SPMFGui(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("SPMF Server Client")
        self.geometry("1280x820")
        self.minsize(960, 600)
        self.configure(bg=DARK_BG)

        self._host      = tk.StringVar(value=DEFAULT_HOST)
        self._port      = tk.StringVar(value=str(DEFAULT_PORT))
        self._apikey    = tk.StringVar(value="")
        self._connected = False
        self._algorithms: list[dict] = []
        self._jobs: list[dict] = []

        self._build_header()
        self._build_main()
        self._build_statusbar()
        self._apply_ttk_style()
        self.after(100, self._try_auto_connect)

    # ── TTK Style ──────────────────────────────────────────────────────────────

    def _apply_ttk_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".",
                         background=DARK_BG, foreground=TEXT_PRIMARY,
                         fieldbackground=ENTRY_BG, bordercolor=BORDER,
                         darkcolor=DARK_BG, lightcolor=PANEL_BG,
                         troughcolor=DARK_BG, focuscolor=ACCENT,
                         selectbackground=ACCENT, selectforeground=TEXT_PRIMARY,
                         font=("Segoe UI", 10))
        style.configure("Treeview", background=ENTRY_BG, foreground=TEXT_PRIMARY,
                         fieldbackground=ENTRY_BG, bordercolor=BORDER, rowheight=26)
        style.map("Treeview",
                   background=[("selected", ACCENT)],
                   foreground=[("selected", TEXT_PRIMARY)])
        style.configure("Treeview.Heading", background=PANEL_BG, foreground=ACCENT,
                         relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading", background=[("active", TAG_BG)])
        style.configure("TNotebook", background=DARK_BG, bordercolor=BORDER,
                         tabmargins=[2, 4, 0, 0])
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_SEC,
                         padding=[16, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                   background=[("selected", DARK_BG)],
                   foreground=[("selected", ACCENT)],
                   expand=[("selected", [1, 1, 1, 0])])
        style.configure("TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG,
                         foreground=TEXT_PRIMARY, arrowcolor=ACCENT,
                         bordercolor=BORDER, selectbackground=ACCENT)
        style.map("TCombobox",
                   fieldbackground=[("readonly", ENTRY_BG)],
                   foreground=[("readonly", TEXT_PRIMARY)])
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background=PANEL_BG,
                             troughcolor=DARK_BG, arrowcolor=ACCENT,
                             bordercolor=BORDER, width=10)

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=HEADER_BG, height=60)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⬡  SPMF Server Client", bg=HEADER_BG,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 14, "bold")).pack(
            side="left", padx=20, pady=10)
        tk.Label(hdr, text=f"v{VERSION}", bg=HEADER_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side="left", pady=10)

        tk.Button(hdr, text="ℹ  About", command=self._open_about,
                  bg=HEADER_BG, fg=TEXT_SEC, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), padx=10, pady=6, bd=0,
                  activebackground=TAG_BG,
                  activeforeground=TEXT_PRIMARY).pack(
            side="left", padx=(8, 0), pady=10)

        conn_frame = tk.Frame(hdr, bg=HEADER_BG)
        conn_frame.pack(side="right", padx=16, pady=8)

        for lbl, var, w, show in [
            ("Host:",    self._host,   14, None),
            ("Port:",    self._port,    6, None),
            ("API Key:", self._apikey, 14, "•"),
        ]:
            tk.Label(conn_frame, text=lbl, bg=HEADER_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
            kw = dict(textvariable=var, width=w, bg=ENTRY_BG, fg=TEXT_PRIMARY,
                      relief="flat", font=("Consolas", 10),
                      insertbackground=TEXT_PRIMARY,
                      highlightthickness=1, highlightbackground=BORDER,
                      highlightcolor=ACCENT)
            if show:
                kw["show"] = show
            tk.Entry(conn_frame, **kw).pack(side="left", padx=(0, 10))

        self._conn_btn = tk.Button(
            conn_frame, text="Connect", command=self._on_connect,
            bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=14, pady=4,
            activebackground=ACCENT_HOVER, activeforeground=TEXT_PRIMARY)
        self._conn_btn.pack(side="left")

        self._dot_lbl = tk.Label(hdr, text="●", bg=HEADER_BG,
                                  fg=ERROR_COL, font=("Segoe UI", 16))
        self._dot_lbl.pack(side="right", padx=(0, 8))

    def _open_about(self):
        AboutWindow(self)

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Not connected.")
        tk.Label(bar, textvariable=self._status_var, bg=HEADER_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8), anchor="w").pack(
            side="left", padx=10, fill="y")
        self._busy_lbl = tk.Label(bar, text="", bg=HEADER_BG,
                                   fg=WARNING, font=("Segoe UI", 8))
        self._busy_lbl.pack(side="right", padx=10)

    def _set_status(self, msg: str, colour: str = TEXT_DIM):
        self._status_var.set(msg)

    def _set_busy(self, msg: str = ""):
        self._busy_lbl.config(text=msg)

    # ── Main layout ────────────────────────────────────────────────────────────

    def _build_main(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        self._tab_dashboard  = tk.Frame(self._notebook, bg=DARK_BG)
        self._tab_algorithms = tk.Frame(self._notebook, bg=DARK_BG)
        self._tab_run        = tk.Frame(self._notebook, bg=DARK_BG)
        self._tab_jobs       = tk.Frame(self._notebook, bg=DARK_BG)
        self._tab_result     = tk.Frame(self._notebook, bg=DARK_BG)

        self._notebook.add(self._tab_dashboard,  text="  Dashboard  ")
        self._notebook.add(self._tab_algorithms, text="  Algorithms  ")
        self._notebook.add(self._tab_run,        text="  Run Job  ")
        self._notebook.add(self._tab_jobs,       text="  Jobs  ")
        self._notebook.add(self._tab_result,     text="  Result  ")

        self._build_tab_dashboard()
        self._build_tab_algorithms()
        self._build_tab_run()
        self._build_tab_jobs()
        self._build_tab_result()

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Dashboard
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_dashboard(self):
        tab = self._tab_dashboard
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        health_card = card_frame(tab)
        health_card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        tk.Label(health_card, text="Server Health", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Separator(health_card).pack(fill="x", padx=10, pady=6)

        self._health_vars = {}
        for key, label in [
            ("status",               "Status"),
            ("version",              "Version"),
            ("spmfAlgorithmsLoaded", "Algorithms Loaded"),
            ("uptimeSeconds",        "Uptime (sec)"),
            ("activeJobs",           "Active Jobs"),
            ("queuedJobs",           "Queued Jobs"),
            ("totalJobsInRegistry",  "Jobs in Registry"),
        ]:
            row = tk.Frame(health_card, bg=PANEL_BG)
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(row, text=label + ":", bg=PANEL_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9), width=22, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self._health_vars[key] = var
            tk.Label(row, textvariable=var, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=("Consolas", 10), anchor="w").pack(side="left")

        btn_row = tk.Frame(health_card, bg=PANEL_BG)
        btn_row.pack(fill="x", padx=16, pady=12)
        styled_button(btn_row, "↺  Refresh Health",
                      self._refresh_health).pack(side="left")

        info_card = card_frame(tab)
        info_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        tk.Label(info_card, text="Server Configuration", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Separator(info_card).pack(fill="x", padx=10, pady=6)

        self._info_vars = {}
        for key, label in [
            ("version",        "Version"),
            ("port",           "Port"),
            ("host",           "Host"),
            ("coreThreads",    "Core Threads"),
            ("maxThreads",     "Max Threads"),
            ("jobTtlMinutes",  "Job TTL (min)"),
            ("maxQueueSize",   "Max Queue Size"),
            ("workDir",        "Work Directory"),
            ("maxInputSizeMb", "Max Input (MB)"),
            ("apiKeyEnabled",  "API Key Enabled"),
            ("logLevel",       "Log Level"),
        ]:
            row = tk.Frame(info_card, bg=PANEL_BG)
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(row, text=label + ":", bg=PANEL_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9), width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self._info_vars[key] = var
            tk.Label(row, textvariable=var, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=("Consolas", 10), anchor="w").pack(side="left")

        btn_row2 = tk.Frame(info_card, bg=PANEL_BG)
        btn_row2.pack(fill="x", padx=16, pady=12)
        styled_button(btn_row2, "↺  Refresh Info",
                      self._refresh_info).pack(side="left")

        log_card = card_frame(tab)
        log_card.grid(row=1, column=0, columnspan=2,
                      padx=10, pady=(0, 10), sticky="nsew")

        hdr2 = tk.Frame(log_card, bg=PANEL_BG)
        hdr2.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(hdr2, text="Activity Log", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        styled_button(hdr2, "Clear", self._clear_log,
                      bg=PANEL_BG, fg=TEXT_DIM, font_size=8).pack(side="right")

        self._log = scrolledtext.ScrolledText(
            log_card, bg=ENTRY_BG, fg=TEXT_PRIMARY,
            font=("Consolas", 9), relief="flat", wrap="word",
            state="disabled", height=8)
        self._log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._log.tag_config("ok",   foreground=SUCCESS)
        self._log.tag_config("err",  foreground=ERROR_COL)
        self._log.tag_config("warn", foreground=WARNING)
        self._log.tag_config("info", foreground=TEXT_SEC)
        self._log.tag_config("dim",  foreground=TEXT_DIM)

    def _log_write(self, msg: str, tag: str = "info"):
        self._log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] ", "dim")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Algorithms
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_algorithms(self):
        tab = self._tab_algorithms
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(0, weight=1)

        left = card_frame(tab)
        left.grid(row=0, column=0, padx=(10, 4), pady=10, sticky="nsew")
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        hdr = tk.Frame(left, bg=PANEL_BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        tk.Label(hdr, text="Algorithm List", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        styled_button(hdr, "↺ Refresh", self._refresh_algorithms,
                      font_size=8).pack(side="right")

        sf = tk.Frame(left, bg=PANEL_BG)
        sf.grid(row=1, column=0, sticky="ew", padx=8, pady=6)
        tk.Label(sf, text="Search:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._algo_search = tk.StringVar()
        self._algo_search.trace_add("write", self._filter_algorithms)
        tk.Entry(sf, textvariable=self._algo_search, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True)

        tree_frame = tk.Frame(left, bg=PANEL_BG)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._algo_tree = ttk.Treeview(
            tree_frame, columns=("name", "category"), show="headings",
            selectmode="browse")
        self._algo_tree.heading("name",     text="Algorithm")
        self._algo_tree.heading("category", text="Category")
        self._algo_tree.column("name",     width=200, minwidth=120)
        self._algo_tree.column("category", width=160, minwidth=100)
        self._algo_tree.grid(row=0, column=0, sticky="nsew")
        self._algo_tree.bind("<<TreeviewSelect>>", self._on_algo_select)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self._algo_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._algo_tree.configure(yscrollcommand=vsb.set)

        right = card_frame(tab)
        right.grid(row=0, column=1, padx=(4, 10), pady=10, sticky="nsew")
        right.rowconfigure(7, weight=1)
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="Algorithm Details", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 0))

        self._detail_vars = {}
        for i, (key, label) in enumerate([
            ("name",                     "Name"),
            ("algorithmCategory",         "Category"),
            ("implementationAuthorNames", "Author(s)"),
            ("algorithmType",             "Type"),
            ("documentationURL",          "Documentation"),
        ], start=1):
            row = tk.Frame(right, bg=PANEL_BG)
            row.grid(row=i, column=0, sticky="ew", padx=16, pady=2)
            tk.Label(row, text=label + ":", bg=PANEL_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self._detail_vars[key] = var
            tk.Label(row, textvariable=var, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=("Consolas", 9), anchor="w", wraplength=420,
                     justify="left").pack(side="left", fill="x", expand=True)

        tk.Label(right, text="Parameters & I/O", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).grid(
            row=6, column=0, sticky="w", padx=16, pady=(10, 2))

        self._detail_text = scrolledtext.ScrolledText(
            right, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
            relief="flat", state="disabled", wrap="word", height=14)
        self._detail_text.grid(row=7, column=0, sticky="nsew", padx=10, pady=(0, 8))

        btn_row = tk.Frame(right, bg=PANEL_BG)
        btn_row.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 12))
        styled_button(btn_row, "▶  Use in Run Job",
                      self._use_algo_in_run).pack(side="left")

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Run Job
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_run(self):
        tab = self._tab_run
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        left = card_frame(tab)
        left.grid(row=0, column=0, rowspan=2, padx=(10, 4),
                  pady=10, sticky="nsew")
        left.columnconfigure(1, weight=1)

        tk.Label(left, text="Job Configuration", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        ttk.Separator(left).grid(row=1, column=0, columnspan=3,
                                  sticky="ew", padx=10, pady=(0, 8))

        tk.Label(left, text="Algorithm:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=2, column=0, sticky="w", padx=16, pady=4)
        self._run_algo_var = tk.StringVar()
        self._run_algo_combo = ttk.Combobox(
            left, textvariable=self._run_algo_var,
            state="readonly", font=("Consolas", 10))
        self._run_algo_combo.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._run_algo_combo.bind("<<ComboboxSelected>>", self._on_run_algo_select)
        styled_button(left, "ℹ", self._describe_run_algo,
                      font_size=9).grid(row=2, column=2, padx=(0, 8), pady=4)

        tk.Label(left, text="Input File:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=3, column=0, sticky="w", padx=16, pady=4)
        self._run_file_var = tk.StringVar()
        tk.Entry(left, textvariable=self._run_file_var, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(
            row=3, column=1, sticky="ew", padx=(0, 8), pady=4)
        styled_button(left, "Browse…", self._browse_input,
                      font_size=9).grid(row=3, column=2, padx=(0, 8), pady=4)

        tk.Label(left, text="Parameters:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=4, column=0, sticky="nw", padx=16, pady=4)
        self._run_params_var = tk.StringVar()
        tk.Entry(left, textvariable=self._run_params_var, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(
            row=4, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=4)
        tk.Label(left, text="Space-separated, e.g.: 0.5  3",
                 bg=PANEL_BG, fg=TEXT_DIM, font=("Segoe UI", 8)).grid(
            row=5, column=1, sticky="w", padx=(0, 8))

        tk.Label(left, text="Options:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=6, column=0, sticky="w", padx=16, pady=(12, 4))
        opt_frame = tk.Frame(left, bg=PANEL_BG)
        opt_frame.grid(row=6, column=1, columnspan=2, sticky="w", pady=(12, 4))

        self._run_base64_var  = tk.BooleanVar(value=False)
        self._run_noclean_var = tk.BooleanVar(value=False)

        for var, text in [(self._run_base64_var,  "Base64 encode input"),
                           (self._run_noclean_var, "Keep job after completion")]:
            tk.Checkbutton(opt_frame, text=text, variable=var,
                            bg=PANEL_BG, fg=TEXT_PRIMARY, selectcolor=ACCENT,
                            activebackground=PANEL_BG, activeforeground=TEXT_PRIMARY,
                            font=("Segoe UI", 9), cursor="hand2").pack(
                side="left", padx=(0, 16))

        tk.Label(left, text="Poll interval (s):", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=7, column=0, sticky="w", padx=16, pady=4)
        self._run_poll_var = tk.StringVar(value="1.0")
        tk.Entry(left, textvariable=self._run_poll_var, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY, width=8,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(
            row=7, column=1, sticky="w", padx=(0, 8), pady=4)

        tk.Label(left, text="Timeout (s):", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=8, column=0, sticky="w", padx=16, pady=4)
        self._run_timeout_var = tk.StringVar(value="300")
        tk.Entry(left, textvariable=self._run_timeout_var, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY, width=8,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(
            row=8, column=1, sticky="w", padx=(0, 8), pady=4)

        ttk.Separator(left).grid(row=9, column=0, columnspan=3,
                                  sticky="ew", padx=10, pady=10)
        self._run_btn = styled_button(left, "▶  Submit Job",
                                       self._submit_job, font_size=11)
        self._run_btn.grid(row=10, column=0, columnspan=3, pady=(0, 16))

        hint_card = card_frame(tab)
        hint_card.grid(row=0, column=1, padx=(4, 10), pady=10, sticky="nsew")
        hint_card.rowconfigure(1, weight=1)
        hint_card.columnconfigure(0, weight=1)
        tk.Label(hint_card, text="Parameter Guide", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        self._param_hint = scrolledtext.ScrolledText(
            hint_card, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
            relief="flat", state="disabled", wrap="word")
        self._param_hint.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        prog_card = card_frame(tab)
        prog_card.grid(row=1, column=1, padx=(4, 10), pady=(0, 10), sticky="nsew")
        prog_card.rowconfigure(2, weight=1)
        prog_card.columnconfigure(0, weight=1)
        tk.Label(prog_card, text="Job Progress", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        self._progress_var = tk.StringVar(value="Idle")
        tk.Label(prog_card, textvariable=self._progress_var,
                 bg=PANEL_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10)).grid(
            row=1, column=0, sticky="w", padx=16)
        self._run_log = scrolledtext.ScrolledText(
            prog_card, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
            relief="flat", state="disabled", wrap="word", height=8)
        self._run_log.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self._run_log.tag_config("ok",   foreground=SUCCESS)
        self._run_log.tag_config("err",  foreground=ERROR_COL)
        self._run_log.tag_config("warn", foreground=WARNING)
        self._run_log.tag_config("info", foreground=TEXT_SEC)
        self._run_log.tag_config("dim",  foreground=TEXT_DIM)

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Jobs
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_jobs(self):
        tab = self._tab_jobs
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        tb = tk.Frame(tab, bg=DARK_BG)
        tb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        styled_button(tb, "↺  Refresh Jobs",
                      self._refresh_jobs).pack(side="left", padx=(0, 8))
        styled_button(tb, "🗑  Delete Selected",
                      self._delete_selected_job,
                      bg="#44273a").pack(side="left", padx=(0, 8))
        styled_button(tb, "📋  View Result",
                      self._view_selected_result,
                      bg="#1e3a44").pack(side="left")

        card = card_frame(tab)
        card.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        cols = ("jobId", "algorithmName", "status", "submittedAt", "executionTimeMs")
        self._jobs_tree = ttk.Treeview(card, columns=cols, show="headings",
                                        selectmode="browse")
        for col, (text, width) in {
            "jobId":           ("Job ID",       260),
            "algorithmName":   ("Algorithm",    180),
            "status":          ("Status",        90),
            "submittedAt":     ("Submitted At", 180),
            "executionTimeMs": ("Exec (ms)",     90),
        }.items():
            self._jobs_tree.heading(col, text=text)
            self._jobs_tree.column(col, width=width, minwidth=60)

        self._jobs_tree.grid(row=0, column=0, sticky="nsew")
        self._jobs_tree.tag_configure("DONE",    foreground=SUCCESS)
        self._jobs_tree.tag_configure("FAILED",  foreground=ERROR_COL)
        self._jobs_tree.tag_configure("RUNNING", foreground=WARNING)
        self._jobs_tree.tag_configure("QUEUED",  foreground=TEXT_SEC)
        self._jobs_tree.bind("<Double-1>", lambda _: self._view_selected_result())

        vsb = ttk.Scrollbar(card, orient="vertical",
                             command=self._jobs_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._jobs_tree.configure(yscrollcommand=vsb.set)

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Result  (result output + console output side-by-side)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_result(self):
        """
        Single tab showing both:
          - LEFT  : algorithm result output  (output.txt content)
          - RIGHT : console output           (stdout / stderr from the child JVM)
        Both are fetched together, and cleanup only happens after both
        are safely in hand.
        """
        tab = self._tab_result
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        # ── Toolbar ────────────────────────────────────────────────────────
        tb = tk.Frame(tab, bg=DARK_BG)
        tb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        tk.Label(tb, text="Job ID:", bg=DARK_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._result_jobid_var = tk.StringVar()
        tk.Entry(tb, textvariable=self._result_jobid_var, bg=ENTRY_BG,
                 fg=TEXT_PRIMARY, relief="flat", font=("Consolas", 10),
                 insertbackground=TEXT_PRIMARY, width=38,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", padx=(0, 8))

        styled_button(tb, "Fetch Result + Console",
                      self._fetch_result).pack(side="left", padx=(0, 8))
        styled_button(tb, "💾  Save Result",
                      self._save_result, bg="#1e3a44").pack(side="left", padx=(0, 4))
        styled_button(tb, "💾  Save Console",
                      self._save_console, bg="#1e3a44").pack(side="left")

        self._result_info_var = tk.StringVar(value="")
        tk.Label(tb, textvariable=self._result_info_var, bg=DARK_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side="right", padx=10)

        # ── Split pane: result (left) + console (right) ────────────────────
        pane = tk.Frame(tab, bg=DARK_BG)
        pane.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)
        pane.columnconfigure(1, weight=1)

        # ── Result output card (left) ──────────────────────────────────────
        res_card = card_frame(pane)
        res_card.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        res_card.rowconfigure(1, weight=1)
        res_card.columnconfigure(0, weight=1)

        res_hdr = tk.Frame(res_card, bg=PANEL_BG)
        res_hdr.grid(row=0, column=0, columnspan=2, sticky="ew",
                     padx=8, pady=(8, 4))
        tk.Label(res_hdr, text="Result Output", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        self._result_text = scrolledtext.ScrolledText(
            res_card, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 10),
            relief="flat", state="disabled", wrap="none")
        self._result_text.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        res_hsb = ttk.Scrollbar(res_card, orient="horizontal",
                                 command=self._result_text.xview)
        res_hsb.grid(row=2, column=0, sticky="ew", padx=4)
        self._result_text.configure(xscrollcommand=res_hsb.set)

        # ── Console output card (right) ────────────────────────────────────
        con_card = card_frame(pane)
        con_card.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        con_card.rowconfigure(1, weight=1)
        con_card.columnconfigure(0, weight=1)

        con_hdr = tk.Frame(con_card, bg=PANEL_BG)
        con_hdr.grid(row=0, column=0, columnspan=2, sticky="ew",
                     padx=8, pady=(8, 4))
        tk.Label(con_hdr, text="Console Output  (stdout / stderr)",
                 bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        self._console_text = scrolledtext.ScrolledText(
            con_card, bg=ENTRY_BG, fg=CONSOLE_FG, font=("Consolas", 10),
            relief="flat", state="disabled", wrap="none")
        self._console_text.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        con_hsb = ttk.Scrollbar(con_card, orient="horizontal",
                                 command=self._console_text.xview)
        con_hsb.grid(row=2, column=0, sticky="ew", padx=4)
        self._console_text.configure(xscrollcommand=con_hsb.set)

    # ══════════════════════════════════════════════════════════════════════════
    #  Connection
    # ══════════════════════════════════════════════════════════════════════════

    def _try_auto_connect(self):
        self._on_connect()

    def _on_connect(self):
        host   = self._host.get().strip()
        port_s = self._port.get().strip()
        try:
            port = int(port_s)
        except ValueError:
            messagebox.showerror("Invalid Port",
                                 f"'{port_s}' is not a valid port number.")
            return

        self._set_status("Connecting…", WARNING)
        self._set_busy("⟳ connecting")

        def worker():
            try:
                resp = api_get(host, port, self._apikey.get(),
                               "/api/health", timeout=5)
                if resp.status_code == 200:
                    self.after(0, self._on_connected, resp.json())
                else:
                    self.after(0, self._on_connect_fail,
                               f"Server returned HTTP {resp.status_code}")
            except Exception as exc:
                self.after(0, self._on_connect_fail, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connected(self, health_data: dict):
        self._connected = True
        self._dot_lbl.config(fg=SUCCESS)
        self._conn_btn.config(text="Reconnect")
        self._set_status(
            f"Connected to {self._host.get()}:{self._port.get()}  |  "
            f"SPMF {health_data.get('version','?')}  |  "
            f"{health_data.get('spmfAlgorithmsLoaded','?')} algorithms",
            SUCCESS)
        self._set_busy("")
        self._log_write(f"Connected to {self._host.get()}:{self._port.get()}", "ok")
        self._update_health_card(health_data)
        self._refresh_info()
        self._refresh_algorithms()

    def _on_connect_fail(self, reason: str):
        self._connected = False
        self._dot_lbl.config(fg=ERROR_COL)
        self._set_status(f"Connection failed: {reason}", ERROR_COL)
        self._set_busy("")
        self._log_write(f"Connection failed: {reason}", "err")

    # ══════════════════════════════════════════════════════════════════════════
    #  API helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _get_conn(self):
        return (self._host.get().strip(),
                int(self._port.get().strip()),
                self._apikey.get().strip())

    def _require_connection(self) -> bool:
        if not self._connected:
            messagebox.showwarning("Not Connected",
                                   "Please connect to an SPMF server first.")
            return False
        return True

    # ── Health ─────────────────────────────────────────────────────────────────

    def _refresh_health(self):
        if not self._require_connection():
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_get(host, port, key, "/api/health")
                if resp.status_code == 200:
                    self.after(0, self._update_health_card, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Health check failed: HTTP {resp.status_code}", "err")
            except Exception as e:
                self.after(0, self._log_write, f"Health error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _update_health_card(self, data: dict):
        for key, var in self._health_vars.items():
            val = data.get(key, "—")
            var.set(("✓  " if val == "UP" else "✗  ") + str(val)
                    if key == "status" else str(val))
        self._log_write("Health refreshed.", "ok")

    # ── Info ───────────────────────────────────────────────────────────────────

    def _refresh_info(self):
        if not self._connected:
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_get(host, port, key, "/api/info")
                if resp.status_code == 200:
                    self.after(0, self._update_info_card, resp.json())
            except Exception as e:
                self.after(0, self._log_write, f"Info error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _update_info_card(self, data: dict):
        for key, var in self._info_vars.items():
            var.set(str(data.get(key, "—")))

    # ── Algorithms ─────────────────────────────────────────────────────────────

    def _refresh_algorithms(self):
        if not self._connected:
            return
        host, port, key = self._get_conn()
        self._log_write("Loading algorithms…", "info")

        def worker():
            try:
                resp = api_get(host, port, key, "/api/algorithms", timeout=30)
                if resp.status_code == 200:
                    self.after(0, self._populate_algorithms, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Algorithms list failed: HTTP {resp.status_code}",
                               "err")
            except Exception as e:
                self.after(0, self._log_write, f"Algorithms error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _populate_algorithms(self, data: dict):
        self._algorithms = data.get("algorithms", [])
        self._render_algo_tree(self._algorithms)
        names = sorted(a.get("name", "") for a in self._algorithms)
        self._run_algo_combo["values"] = names
        self._log_write(
            f"Loaded {data.get('count', len(self._algorithms))} algorithms.", "ok")

    def _render_algo_tree(self, algos: list):
        self._algo_tree.delete(*self._algo_tree.get_children())
        for a in sorted(algos, key=lambda x: x.get("name", "")):
            self._algo_tree.insert("", "end",
                                    values=(a.get("name", "?"),
                                            a.get("algorithmCategory", "?")))

    def _filter_algorithms(self, *_):
        query = self._algo_search.get().lower()
        filtered = [a for a in self._algorithms
                    if query in a.get("name", "").lower()
                    or query in a.get("algorithmCategory", "").lower()]
        self._render_algo_tree(filtered)

    def _on_algo_select(self, _event=None):
        sel = self._algo_tree.selection()
        if not sel:
            return
        self._fetch_algo_detail(self._algo_tree.item(sel[0], "values")[0])

    def _fetch_algo_detail(self, name: str):
        host, port, key = self._get_conn()

        def worker():
            try:
                encoded = requests.utils.quote(name, safe="")
                resp = api_get(host, port, key, f"/api/algorithms/{encoded}")
                if resp.status_code == 200:
                    self.after(0, self._show_algo_detail, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Describe failed: HTTP {resp.status_code}", "err")
            except Exception as e:
                self.after(0, self._log_write, f"Describe error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _show_algo_detail(self, data: dict):
        for key, var in self._detail_vars.items():
            var.set(str(data.get(key, "—")))

        self._detail_text.config(state="normal")
        self._detail_text.delete("1.0", "end")
        in_t      = data.get("inputFileTypes", [])
        out_t     = data.get("outputFileTypes", [])
        params    = data.get("parameters", [])
        mandatory = data.get("numberOfMandatoryParameters", 0)

        self._detail_text.insert("end", "Input types  : ", "label")
        self._detail_text.insert("end", (", ".join(in_t) if in_t else "N/A") + "\n")
        self._detail_text.insert("end", "Output types : ", "label")
        self._detail_text.insert("end", (", ".join(out_t) if out_t else "N/A") + "\n\n")
        self._detail_text.insert("end",
            f"Parameters   : {len(params)} total, {mandatory} mandatory\n\n")
        for i, p in enumerate(params, 1):
            opt = " [optional]" if p.get("isOptional") else " [mandatory]"
            self._detail_text.insert("end", f"  [{i}] {p.get('name','?')}{opt}\n")
            self._detail_text.insert("end", f"       type   : {p.get('parameterType','?')}\n")
            self._detail_text.insert("end", f"       example: {p.get('example','?')}\n\n")

        self._detail_text.tag_config("label", foreground=ACCENT)
        self._detail_text.config(state="disabled")

    # ── Run Job ────────────────────────────────────────────────────────────────

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select input file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._run_file_var.set(path)

    def _on_run_algo_select(self, _event=None):
        name = self._run_algo_var.get()
        if name:
            self._fetch_param_hint(name)

    def _describe_run_algo(self):
        name = self._run_algo_var.get()
        if not name:
            messagebox.showinfo("No Algorithm", "Select an algorithm first.")
            return
        self._fetch_param_hint(name)

    def _fetch_param_hint(self, name: str):
        host, port, key = self._get_conn()

        def worker():
            try:
                encoded = requests.utils.quote(name, safe="")
                resp = api_get(host, port, key, f"/api/algorithms/{encoded}")
                if resp.status_code == 200:
                    self.after(0, self._show_param_hint, resp.json())
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _show_param_hint(self, data: dict):
        self._param_hint.config(state="normal")
        self._param_hint.delete("1.0", "end")
        params    = data.get("parameters", [])
        mandatory = data.get("numberOfMandatoryParameters", 0)
        in_t      = data.get("inputFileTypes", [])
        out_t     = data.get("outputFileTypes", [])
        doc       = data.get("documentationURL", "")

        self._param_hint.insert("end", f"Algorithm : {data.get('name','?')}\n")
        self._param_hint.insert("end", f"Category  : {data.get('algorithmCategory','?')}\n")
        self._param_hint.insert("end", f"Input     : {', '.join(in_t)}\n")
        self._param_hint.insert("end", f"Output    : {', '.join(out_t)}\n")
        if doc:
            self._param_hint.insert("end", f"Docs      : {doc}\n")
        self._param_hint.insert("end",
            f"\nParameters ({len(params)} total, {mandatory} mandatory):\n")
        self._param_hint.insert("end", "─" * 40 + "\n")
        for i, p in enumerate(params, 1):
            opt = "[optional]" if p.get("isOptional") else "[required]"
            self._param_hint.insert("end",
                f"  {i}. {p.get('name','?')}  {opt}\n")
            self._param_hint.insert("end",
                f"     type   : {p.get('parameterType','?')}\n")
            self._param_hint.insert("end",
                f"     example: {p.get('example','?')}\n\n")
        self._param_hint.config(state="disabled")

    def _use_algo_in_run(self):
        sel = self._algo_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an algorithm from the list first.")
            return
        name = self._algo_tree.item(sel[0], "values")[0]
        self._run_algo_var.set(name)
        self._fetch_param_hint(name)
        self._notebook.select(self._tab_run)
        self._log_write(f"Loaded '{name}' into Run Job.", "info")

    def _run_log_write(self, msg: str, tag: str = "info"):
        self._run_log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._run_log.insert("end", f"[{ts}] ", "dim")
        self._run_log.insert("end", msg + "\n", tag)
        self._run_log.see("end")
        self._run_log.config(state="disabled")

    def _submit_job(self):
        if not self._require_connection():
            return

        algo       = self._run_algo_var.get().strip()
        fpath      = self._run_file_var.get().strip()
        params_raw = self._run_params_var.get().strip()
        params     = params_raw.split() if params_raw else []

        if not algo:
            messagebox.showwarning("Missing Algorithm", "Please select an algorithm.")
            return
        if not fpath:
            messagebox.showwarning("Missing File", "Please choose an input file.")
            return

        p = Path(fpath)
        if not p.exists():
            messagebox.showerror("File Not Found", f"Input file not found:\n{fpath}")
            return

        try:
            poll_interval = float(self._run_poll_var.get())
            timeout       = int(self._run_timeout_var.get())
        except ValueError:
            messagebox.showerror("Invalid Option",
                                 "Poll interval and timeout must be numbers.")
            return

        self._run_btn.config(state="disabled", text="Running…")
        self._progress_var.set("Submitting…")
        self._run_log_write(f"Submitting: {algo}  params={params}", "info")

        host, port, key = self._get_conn()
        use_b64         = self._run_base64_var.get()
        no_cleanup      = self._run_noclean_var.get()

        def worker():
            try:
                text = p.read_text(encoding="utf-8")
                if use_b64:
                    input_data     = base64.b64encode(text.encode()).decode("ascii")
                    input_encoding = "base64"
                else:
                    input_data     = text
                    input_encoding = "plain"

                payload = {
                    "algorithmName": algo,
                    "parameters":    params,
                    "inputData":     input_data,
                    "inputEncoding": input_encoding,
                }

                resp = api_post(host, port, key, "/api/run", payload)
                if resp.status_code != 202:
                    err = (resp.json().get("error", resp.text)
                           if "json" in resp.headers.get("content-type", "")
                           else resp.text)
                    self.after(0, self._job_error,
                               f"Submit failed [{resp.status_code}]: {err}")
                    return

                data   = resp.json()
                job_id = data.get("jobId")
                self.after(0, self._run_log_write, f"Accepted: {job_id}", "ok")
                self.after(0, self._progress_var.set, f"Polling: {job_id}")

                elapsed      = 0
                final_status = None
                poll_data    = {}

                while elapsed < timeout:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    pr = api_get(host, port, key, f"/api/jobs/{job_id}")
                    if pr.status_code != 200:
                        self.after(0, self._job_error,
                                   f"Poll error: HTTP {pr.status_code}")
                        return
                    poll_data    = pr.json()
                    final_status = poll_data.get("status")
                    self.after(0, self._progress_var.set,
                               f"Status: {final_status}  ({elapsed:.0f}s elapsed)")
                    if final_status in ("DONE", "FAILED"):
                        break

                if final_status not in ("DONE", "FAILED"):
                    self.after(0, self._job_error, f"Timeout after {timeout}s")
                    return

                # ── FIX: fetch console FIRST before result and before delete ──
                # Once the job is deleted the work directory is removed and
                # console.log is gone forever.
                console_text = ""
                try:
                    cr = api_get(host, port, key, f"/api/jobs/{job_id}/console")
                    if cr.status_code == 200:
                        console_text = cr.json().get("consoleOutput", "")
                except Exception:
                    pass

                if final_status == "FAILED":
                    err_msg = poll_data.get("errorMessage", "unknown error")
                    exec_ms = poll_data.get("executionTimeMs", "?")
                    if not no_cleanup:
                        api_delete(host, port, key, f"/api/jobs/{job_id}")
                    self.after(0, self._job_error_with_console,
                               f"FAILED after {exec_ms}ms: {err_msg}",
                               console_text)
                    return

                # Fetch result
                exec_ms = poll_data.get("executionTimeMs", "?")
                rr = api_get(host, port, key, f"/api/jobs/{job_id}/result")
                if rr.status_code != 200:
                    self.after(0, self._job_error,
                               f"Result fetch failed: HTTP {rr.status_code}")
                    return

                output = rr.json().get("outputData", "")

                # ── FIX: delete AFTER both result and console are fetched ────
                if not no_cleanup:
                    api_delete(host, port, key, f"/api/jobs/{job_id}")

                self.after(0, self._job_done,
                           job_id, output, console_text, exec_ms, no_cleanup)

            except Exception as exc:
                self.after(0, self._job_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _job_done(self, job_id: str, output: str, console: str,
                  exec_ms, no_cleanup: bool):
        self._run_btn.config(state="normal", text="▶  Submit Job")
        self._progress_var.set(f"✓ Done in {exec_ms} ms")
        self._run_log_write(f"Job DONE in {exec_ms} ms.", "ok")
        if no_cleanup:
            self._run_log_write(f"Job kept on server: {job_id}", "warn")
        self._log_write(f"Job {job_id} completed in {exec_ms} ms.", "ok")
        self._result_jobid_var.set(job_id)
        self._show_result_and_console(output, console, exec_ms)
        self._notebook.select(self._tab_result)
        self._refresh_jobs()

    def _job_error(self, msg: str):
        self._run_btn.config(state="normal", text="▶  Submit Job")
        self._progress_var.set("✗ Error")
        self._run_log_write(f"ERROR: {msg}", "err")
        self._log_write(f"Job error: {msg}", "err")
        messagebox.showerror("Job Error", msg)

    def _job_error_with_console(self, msg: str, console: str):
        """Show error but also display whatever console output we captured."""
        self._run_btn.config(state="normal", text="▶  Submit Job")
        self._progress_var.set("✗ Error")
        self._run_log_write(f"ERROR: {msg}", "err")
        self._log_write(f"Job error: {msg}", "err")
        # Show the console even on failure — it often contains the real error
        self._show_result_and_console("(job failed — no result output)", console, "?")
        self._notebook.select(self._tab_result)
        messagebox.showerror("Job Error", msg)

    # ── Jobs ───────────────────────────────────────────────────────────────────

    def _refresh_jobs(self):
        if not self._require_connection():
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_get(host, port, key, "/api/jobs")
                if resp.status_code == 200:
                    self.after(0, self._populate_jobs, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Jobs list failed: HTTP {resp.status_code}", "err")
            except Exception as e:
                self.after(0, self._log_write, f"Jobs error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _populate_jobs(self, data: dict):
        self._jobs = data.get("jobs", [])
        self._jobs_tree.delete(*self._jobs_tree.get_children())
        for j in self._jobs:
            status = j.get("status", "?")
            self._jobs_tree.insert("", "end",
                                    values=(
                                        j.get("jobId", "?"),
                                        j.get("algorithmName", "?"),
                                        status,
                                        j.get("submittedAt", "?"),
                                        j.get("executionTimeMs", "?"),
                                    ),
                                    tags=(status,))
        self._log_write(
            f"Jobs refreshed: {data.get('count', len(self._jobs))} jobs.", "ok")

    def _delete_selected_job(self):
        sel = self._jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a job to delete.")
            return
        job_id = self._jobs_tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("Confirm Delete", f"Delete job {job_id}?"):
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_delete(host, port, key, f"/api/jobs/{job_id}")
                if resp.status_code == 200:
                    self.after(0, self._log_write, f"Deleted job {job_id}.", "ok")
                    self.after(0, self._refresh_jobs)
                else:
                    self.after(0, self._log_write,
                               f"Delete failed: HTTP {resp.status_code}", "err")
            except Exception as e:
                self.after(0, self._log_write, f"Delete error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _view_selected_result(self):
        """Fetch both result and console for the selected job."""
        sel = self._jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a job to view its result.")
            return
        job_id = self._jobs_tree.item(sel[0], "values")[0]
        self._result_jobid_var.set(job_id)
        self._fetch_result()
        self._notebook.select(self._tab_result)

    # ── Result + Console ───────────────────────────────────────────────────────

    def _fetch_result(self):
        """
        Fetch result output AND console output together in one background call.
        Both are displayed side-by-side in the Result tab.
        """
        if not self._require_connection():
            return
        job_id = self._result_jobid_var.get().strip()
        if not job_id:
            messagebox.showwarning("No Job ID",
                                   "Enter a Job ID to fetch results.")
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                # ── Fetch result ───────────────────────────────────────────
                resp = api_get(host, port, key, f"/api/jobs/{job_id}/result")
                if resp.status_code == 200:
                    data    = resp.json()
                    output  = data.get("outputData", "")
                    exec_ms = data.get("executionTimeMs", "?")
                else:
                    err = (resp.json().get("error", resp.text)
                           if "json" in resp.headers.get("content-type", "")
                           else resp.text)
                    self.after(0, self._log_write,
                               f"Result fetch failed: {err}", "err")
                    output  = f"(error fetching result: {err})"
                    exec_ms = "?"

                # ── Fetch console (always attempt, never fail hard) ─────────
                console_text = ""
                try:
                    cr = api_get(host, port, key,
                                 f"/api/jobs/{job_id}/console")
                    if cr.status_code == 200:
                        console_text = cr.json().get("consoleOutput", "")
                except Exception:
                    pass

                self.after(0, self._show_result_and_console,
                           output, console_text, exec_ms)

            except Exception as e:
                self.after(0, self._log_write, f"Result error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _show_result_and_console(self, output: str, console: str, exec_ms):
        """
        Populate both the result text widget and the console text widget.
        Called from the EDT after background fetch completes.
        """
        # ── Result output ──────────────────────────────────────────────────
        self._result_text.config(state="normal")
        self._result_text.delete("1.0", "end")
        self._result_text.insert("end", output)
        self._result_text.config(state="disabled")

        # ── Console output ─────────────────────────────────────────────────
        self._console_text.config(state="normal")
        self._console_text.delete("1.0", "end")
        if console:
            self._console_text.insert("end", console)
        else:
            self._console_text.insert("end", "(no console output available)")
        self._console_text.config(state="disabled")

        # ── Info bar ───────────────────────────────────────────────────────
        r_lines = len(output.splitlines())
        c_lines = len(console.splitlines()) if console else 0
        self._result_info_var.set(
            f"Exec: {exec_ms} ms  |  "
            f"Result: {r_lines} lines / {len(output)} chars  |  "
            f"Console: {c_lines} lines")

        self._log_write(
            f"Result loaded: {r_lines} lines output, "
            f"{c_lines} lines console.", "ok")

    def _save_result(self):
        content = self._result_text.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Empty", "No result to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save result output",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            Path(path).write_text(content, encoding="utf-8")
            self._log_write(f"Result saved to: {path}", "ok")
            messagebox.showinfo("Saved", f"Result saved to:\n{path}")

    def _save_console(self):
        content = self._console_text.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Empty", "No console output to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save console output",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"),
                       ("All files", "*.*")])
        if path:
            Path(path).write_text(content, encoding="utf-8")
            self._log_write(f"Console saved to: {path}", "ok")
            messagebox.showinfo("Saved", f"Console saved to:\n{path}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = SPMFGui()
    app.mainloop()


if __name__ == "__main__":
    main()