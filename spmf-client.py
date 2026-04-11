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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
spmf-client.py  —  Graphical client for SPMF-Server.

Requirements:
    pip install requests
    tkinter  (bundled with standard CPython on Windows / macOS / most Linux)

Usage:
    python spmf-client.py
"""

# ── stdlib ─────────────────────────────────────────────────────────────────────
import base64
import json
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional, Dict, List

# ── third-party ────────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    # Show a GUI error even before the main window exists
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "'requests' is not installed.\n\nRun:  pip install requests")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════════

VERSION       = "2.0.0"
DEFAULT_HOST  = "localhost"
DEFAULT_PORT  = 8585
CONFIG_FILE   = Path.home() / ".spmf_client_config.json"
MAX_LOG_LINES = 500
POLL_STATES   = ("DONE", "FAILED", "CANCELLED")

# ══════════════════════════════════════════════════════════════════════════════
#  Colour palette
# ══════════════════════════════════════════════════════════════════════════════

DARK_BG      = "#1e1e2e"
PANEL_BG     = "#2a2a3e"
HEADER_BG    = "#12121e"
ACCENT       = "#7c6af7"
ACCENT_HOVER = "#9d8fff"
SUCCESS      = "#50fa7b"
ERROR_COL    = "#ff5555"
WARNING      = "#ffb86c"
INFO_COL     = "#8be9fd"
TEXT_PRIMARY = "#f8f8f2"
TEXT_SEC     = "#aaaacc"
TEXT_DIM     = "#666688"
ENTRY_BG     = "#13131f"
BORDER       = "#3a3a5c"
TAG_BG       = "#3d3560"
CONSOLE_FG   = "#a8ff80"
DANGER_BG    = "#44273a"
SAFE_BG      = "#1e3a44"
FAV_COL      = "#ffb86c"

# ══════════════════════════════════════════════════════════════════════════════
#  Tooltip
# ══════════════════════════════════════════════════════════════════════════════

class Tooltip:
    """Lightweight hover tooltip."""

    _DELAY = 600   # ms

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text   = text
        self._job_id = None          # after() handle
        self._top    = None          # Toplevel
        widget.bind("<Enter>",  self._schedule, add="+")
        widget.bind("<Leave>",  self._cancel,   add="+")
        widget.bind("<Button>", self._cancel,   add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job_id = self._widget.after(self._DELAY, self._show)

    def _cancel(self, _=None):
        if self._job_id:
            self._widget.after_cancel(self._job_id)
            self._job_id = None
        if self._top:
            self._top.destroy()
            self._top = None

    def _show(self):
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._top = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, bg="#ffffcc", fg="#111111",
                 relief="solid", bd=1, padx=6, pady=3,
                 font=("Segoe UI", 8), justify="left",
                 wraplength=320).pack()


# ══════════════════════════════════════════════════════════════════════════════
#  Config
# ══════════════════════════════════════════════════════════════════════════════

class Config:
    _DEFAULTS: Dict[str, object] = {
        "host":          DEFAULT_HOST,
        "port":          str(DEFAULT_PORT),
        "apikey":        "",
        "poll_interval": "1.0",
        "timeout":       "300",
        "auto_refresh":  False,
        "refresh_every": "10",
        "favorites":     [],
        "last_algo":     "",
        "last_file":     "",
        "wrap_result":   False,
    }

    def __init__(self):
        self._data: dict = dict(self._DEFAULTS)
        self.load()

    def load(self):
        try:
            if CONFIG_FILE.exists():
                loaded = json.loads(CONFIG_FILE.read_text("utf-8"))
                self._data.update(loaded)
        except Exception:
            pass   # corrupt config — use defaults silently

    def save(self):
        try:
            CONFIG_FILE.write_text(json.dumps(self._data, indent=2), "utf-8")
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, self._DEFAULTS.get(key, default))

    def set(self, key: str, value):
        self._data[key] = value

    def toggle_favorite(self, name: str) -> bool:
        favs: list = self._data.setdefault("favorites", [])
        if name in favs:
            favs.remove(name)
            return False
        favs.append(name)
        return True

    def is_favorite(self, name: str) -> bool:
        return name in self._data.get("favorites", [])


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP helpers
# ══════════════════════════════════════════════════════════════════════════════

def _headers(apikey: str) -> dict:
    h = {"Content-Type": "application/json"}
    if apikey:
        h["X-API-Key"] = apikey
    return h


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def api_get(host: str, port: int, apikey: str,
            path: str, timeout: int = 15):
    return requests.get(
        _base_url(host, port) + path,
        headers=_headers(apikey), timeout=timeout)


def api_post(host: str, port: int, apikey: str,
             path: str, payload: dict, timeout: int = 30):
    return requests.post(
        _base_url(host, port) + path,
        headers=_headers(apikey),
        data=json.dumps(payload), timeout=timeout)


def api_delete(host: str, port: int, apikey: str,
               path: str, timeout: int = 15):
    return requests.delete(
        _base_url(host, port) + path,
        headers=_headers(apikey), timeout=timeout)


def _safe_json_error(resp) -> str:
    try:
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            return resp.json().get("error", resp.text)
    except Exception:
        pass
    return resp.text


# ══════════════════════════════════════════════════════════════════════════════
#  Widget helpers
# ══════════════════════════════════════════════════════════════════════════════

def styled_button(parent, text: str, command,
                  bg=ACCENT, fg=TEXT_PRIMARY,
                  width=None, font_size: int = 10,
                  tooltip: str = "") -> tk.Button:
    kw = dict(
        text=text, command=command, bg=bg, fg=fg,
        relief="flat", cursor="hand2",
        font=("Segoe UI", font_size, "bold"),
        padx=12, pady=6, bd=0,
        activebackground=ACCENT_HOVER,
        activeforeground=TEXT_PRIMARY,
    )
    if width:
        kw["width"] = width
    btn = tk.Button(parent, **kw)
    btn.bind("<Enter>", lambda _: btn.config(bg=ACCENT_HOVER
                                              if bg == ACCENT else bg))
    btn.bind("<Leave>", lambda _: btn.config(bg=bg))
    if tooltip:
        Tooltip(btn, tooltip)
    return btn


def icon_button(parent, text: str, command,
                tooltip: str = "", fg=TEXT_SEC) -> tk.Button:
    btn = tk.Button(parent, text=text, command=command,
                    bg=PANEL_BG, fg=fg, relief="flat", cursor="hand2",
                    font=("Segoe UI", 11), padx=4, pady=2, bd=0,
                    activebackground=TAG_BG,
                    activeforeground=TEXT_PRIMARY)
    if tooltip:
        Tooltip(btn, tooltip)
    return btn


def card_frame(parent, **kw) -> tk.Frame:
    return tk.Frame(parent, bg=PANEL_BG, bd=0,
                    highlightthickness=1,
                    highlightbackground=BORDER, **kw)


def section_label(parent, text: str):
    tk.Label(parent, text=text, bg=PANEL_BG, fg=ACCENT,
             font=("Segoe UI", 11, "bold")).pack(
        anchor="w", padx=16, pady=(12, 0))
    ttk.Separator(parent).pack(fill="x", padx=10, pady=(4, 6))


def kv_row(parent, label: str, var: tk.StringVar,
           label_width: int = 22, tooltip: str = ""):
    row = tk.Frame(parent, bg=PANEL_BG)
    row.pack(fill="x", padx=16, pady=2)
    lbl = tk.Label(row, text=label + ":", bg=PANEL_BG, fg=TEXT_SEC,
                   font=("Segoe UI", 9), width=label_width, anchor="w")
    lbl.pack(side="left")
    val = tk.Label(row, textvariable=var, bg=PANEL_BG, fg=TEXT_PRIMARY,
                   font=("Consolas", 10), anchor="w")
    val.pack(side="left", fill="x", expand=True)
    if tooltip:
        Tooltip(lbl, tooltip)
        Tooltip(val, tooltip)


def styled_entry(parent, var: tk.Variable,
                 width: int = None, show: str = None,
                 font_size: int = 10) -> tk.Entry:
    kw = dict(
        textvariable=var, bg=ENTRY_BG, fg=TEXT_PRIMARY,
        relief="flat", font=("Consolas", font_size),
        insertbackground=TEXT_PRIMARY,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    if width:
        kw["width"] = width
    if show:
        kw["show"] = show
    return tk.Entry(parent, **kw)


# ══════════════════════════════════════════════════════════════════════════════
#  About window
# ══════════════════════════════════════════════════════════════════════════════

class AboutWindow(tk.Toplevel):
    _LICENSE = (
        "This program is free software: you can redistribute it and/or\n"
        "modify it under the terms of the GNU General Public License as\n"
        "published by the Free Software Foundation, either version 3 of\n"
        "the License, or (at your option) any later version.\n\n"
        "This program is distributed in the hope that it will be useful,\n"
        "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
        "GNU General Public License for more details.\n\n"
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
        tk.Frame(self, bg=ACCENT, height=6).pack(fill="x")

        logo = tk.Frame(self, bg=DARK_BG)
        logo.pack(fill="x", padx=32, pady=(28, 0))
        tk.Label(logo, text="⬡", bg=DARK_BG, fg=ACCENT,
                 font=("Segoe UI", 42)).pack(side="left", padx=(0, 16))
        tb = tk.Frame(logo, bg=DARK_BG)
        tb.pack(side="left", anchor="w")
        tk.Label(tb, text="SPMF Server Client", bg=DARK_BG,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 18, "bold"),
                 anchor="w").pack(anchor="w")
        tk.Label(tb, text=f"Version {VERSION}", bg=DARK_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 10),
                 anchor="w").pack(anchor="w")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24,
                                                  pady=(20, 0))
        card = tk.Frame(self, bg=PANEL_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=24, pady=16)
        for lbl, val in [
            ("Author",     "Philippe Fournier-Viger"),
            ("Website",    "https://www.philippe-fournier-viger.com/spmf/"),
            ("License",    "GNU General Public License v3.0  (GPLv3)"),
            ("Copyright",  "© Philippe Fournier-Viger.  All rights reserved."),
            ("Built with", "Python  •  tkinter  •  requests"),
        ]:
            row = tk.Frame(card, bg=PANEL_BG)
            row.pack(fill="x", padx=20, pady=5)
            tk.Label(row, text=f"{lbl}:", bg=PANEL_BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), width=12,
                     anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 9), anchor="w").pack(side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24,
                                                  pady=(0, 12))
        tk.Label(self,
                 text=("SPMF Server Client is a graphical interface for the SPMF\n"
                       "data mining server — browse algorithms, submit jobs,\n"
                       "and view results without the command line."),
                 bg=DARK_BG, fg=TEXT_SEC, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=32, pady=(0, 12))

        tk.Label(self, text="License", bg=DARK_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=32,
                                                      pady=(0, 4))
        box = tk.Text(self, bg=ENTRY_BG, fg=TEXT_SEC,
                      font=("Consolas", 8), relief="flat", height=12,
                      wrap="word", cursor="arrow",
                      highlightthickness=1, highlightbackground=BORDER)
        box.insert("1.0", self._LICENSE)
        box.config(state="disabled")
        box.pack(fill="x", padx=24, pady=(0, 12))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)
        bot = tk.Frame(self, bg=DARK_BG)
        bot.pack(fill="x", padx=24, pady=12)
        tk.Label(bot, text="SPMF — Sequential Pattern Mining Framework",
                 bg=DARK_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "italic")).pack(side="left")
        tk.Button(bot, text="Close", command=self.destroy,
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat",
                  cursor="hand2", font=("Segoe UI", 9, "bold"),
                  padx=20, pady=4,
                  activebackground=ACCENT_HOVER,
                  activeforeground=TEXT_PRIMARY).pack(side="right")

    def _center(self, parent: tk.Tk):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        px = parent.winfo_x() + (parent.winfo_width()  // 2) - (w // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"+{px}+{py}")


# ══════════════════════════════════════════════════════════════════════════════
#  Settings window
# ══════════════════════════════════════════════════════════════════════════════

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, config: Config, on_save=None):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.configure(bg=DARK_BG)
        self.grab_set()
        self.focus_set()
        self._cfg     = config
        self._on_save = on_save
        self._vars: Dict[str, tk.Variable] = {}
        self._build()
        self._center(parent)

    def _build(self):
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")
        tk.Label(self, text="⚙  Settings", bg=DARK_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=20, pady=(16, 4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16,
                                                  pady=(0, 8))

        card = card_frame(self)
        card.pack(fill="x", padx=16, pady=4)

        section_label(card, "Network")
        self._str_row(card, "Default Host",      "host")
        self._str_row(card, "Default Port",      "port")

        section_label(card, "Job Defaults")
        self._str_row(card, "Poll Interval (s)", "poll_interval")
        self._str_row(card, "Timeout (s)",       "timeout")

        section_label(card, "Auto-Refresh")
        self._bool_row(card, "Enable auto-refresh", "auto_refresh")
        self._str_row(card, "Refresh every (s)", "refresh_every")

        section_label(card, "Display")
        self._bool_row(card, "Word-wrap result output", "wrap_result")

        btns = tk.Frame(self, bg=DARK_BG)
        btns.pack(fill="x", padx=16, pady=12)
        styled_button(btns, "Save", self._save).pack(side="right",
                                                       padx=(4, 0))
        styled_button(btns, "Cancel", self.destroy,
                      bg=PANEL_BG, fg=TEXT_SEC).pack(side="right")

    def _str_row(self, parent, label: str, key: str):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", padx=16, pady=3)
        tk.Label(row, text=label + ":", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), width=22,
                 anchor="w").pack(side="left")
        var = tk.StringVar(value=str(self._cfg.get(key, "")))
        self._vars[key] = var
        styled_entry(row, var, width=20).pack(side="left")

    def _bool_row(self, parent, label: str, key: str):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", padx=16, pady=3)
        var = tk.BooleanVar(value=bool(self._cfg.get(key, False)))
        self._vars[key] = var
        tk.Checkbutton(row, text=label, variable=var,
                        bg=PANEL_BG, fg=TEXT_PRIMARY,
                        selectcolor=ACCENT,
                        activebackground=PANEL_BG,
                        font=("Segoe UI", 9)).pack(anchor="w")

    def _save(self):
        for key, var in self._vars.items():
            self._cfg.set(key, var.get())
        self._cfg.save()
        if self._on_save:
            self._on_save()
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        px = parent.winfo_x() + (parent.winfo_width()  // 2) - (w // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"+{px}+{py}")


# ══════════════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════════════

class SPMFGui(tk.Tk):

	def __init__(self):
    super().__init__()
    self.title("SPMF Server Client")
    self.geometry("1380x860")
    self.minsize(1000, 640)
    self.configure(bg=DARK_BG)
    self.protocol("WM_DELETE_WINDOW", self._on_close)

    self._cfg        = Config()
    self._connected  = False
    self._algorithms: List[dict] = []
    self._jobs:       List[dict] = []
    self._auto_after: Optional[str] = None
    self._submit_thread: Optional[threading.Thread] = None
    self._cancel_flag   = threading.Event()
    self._last_filtered: List[dict] = []
    self._favs_only     = False
    self._jobs_sort_col = "submittedAt"
    self._jobs_sort_rev = True

    self._host   = tk.StringVar(value=str(self._cfg.get("host")))
    self._port   = tk.StringVar(value=str(self._cfg.get("port")))
    self._apikey = tk.StringVar(value=str(self._cfg.get("apikey")))

    # ── IMPORTANT: style MUST be applied before _build_main()
    #    because _build_tab_run() creates a ttk.Progressbar that
    #    references "Horizontal.Accent.TProgressbar" at widget
    #    construction time — if the style does not exist yet,
    #    tkinter raises:
    #      TclError: Layout Horizontal.Accent.TProgressbar not found
    self._apply_ttk_style()   # <-- moved UP, before _build_main()

    self._build_header()
    self._build_main()        # <-- now runs after style is registered
    self._build_statusbar()
    self._bind_shortcuts()

    self.after(200, self._try_auto_connect)
    # ── Window close ──────────────────────────────────────────────────────────

    def _on_close(self):
        self._stop_auto_refresh()
        self._cfg.set("host",   self._host.get())
        self._cfg.set("port",   self._port.get())
        self._cfg.set("apikey", self._apikey.get())
        self._cfg.save()
        self.destroy()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<F5>",            lambda _: self._smart_refresh())
        self.bind("<Control-r>",     lambda _: self._smart_refresh())
        self.bind("<Control-Return>",lambda _: self._submit_job())
        self.bind("<Control-k>",     lambda _: self._clear_log())
        self.bind("<Control-comma>", lambda _: self._open_settings())
        self.bind("<F1>",            lambda _: self._open_about())

    def _smart_refresh(self):
        tab = self._notebook.index(self._notebook.select())
        {0: self._refresh_health,
         1: self._refresh_algorithms,
         3: self._refresh_jobs}.get(tab, lambda: None)()

    # ── TTK style ─────────────────────────────────────────────────────────────

	def _apply_ttk_style(self):
    s = ttk.Style(self)
    s.theme_use("clam")
    s.configure(".",
                 background=DARK_BG, foreground=TEXT_PRIMARY,
                 fieldbackground=ENTRY_BG, bordercolor=BORDER,
                 darkcolor=DARK_BG, lightcolor=PANEL_BG,
                 troughcolor=DARK_BG, focuscolor=ACCENT,
                 selectbackground=ACCENT, selectforeground=TEXT_PRIMARY,
                 font=("Segoe UI", 10))
    s.configure("Treeview",
                 background=ENTRY_BG, foreground=TEXT_PRIMARY,
                 fieldbackground=ENTRY_BG, bordercolor=BORDER,
                 rowheight=26)
    s.map("Treeview",
           background=[("selected", ACCENT)],
           foreground=[("selected", TEXT_PRIMARY)])
    s.configure("Treeview.Heading",
                 background=PANEL_BG, foreground=ACCENT,
                 relief="flat", font=("Segoe UI", 9, "bold"))
    s.map("Treeview.Heading", background=[("active", TAG_BG)])
    s.configure("TNotebook",
                 background=DARK_BG, bordercolor=BORDER,
                 tabmargins=[2, 4, 0, 0])
    s.configure("TNotebook.Tab",
                 background=PANEL_BG, foreground=TEXT_SEC,
                 padding=[16, 8], font=("Segoe UI", 10, "bold"))
    s.map("TNotebook.Tab",
           background=[("selected", DARK_BG)],
           foreground=[("selected", ACCENT)],
           expand=[("selected", [1, 1, 1, 0])])
    s.configure("TCombobox",
                 fieldbackground=ENTRY_BG, background=ENTRY_BG,
                 foreground=TEXT_PRIMARY, arrowcolor=ACCENT,
                 bordercolor=BORDER, selectbackground=ACCENT)
    s.map("TCombobox",
           fieldbackground=[("readonly", ENTRY_BG)],
           foreground=[("readonly", TEXT_PRIMARY)])
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar",
                     background=PANEL_BG, troughcolor=DARK_BG,
                     arrowcolor=ACCENT, bordercolor=BORDER, width=10)

    # ── Progressbar: style the default TProgressbar directly ──────────────
    # Do NOT use a custom named style — it causes TclError on some
    # tkinter/Tk version combinations regardless of name format.
    # Styling the built-in "Horizontal.TProgressbar" directly is safe
    # on all versions.
    s.configure("Horizontal.TProgressbar",
                 troughcolor=ENTRY_BG,
                 background=ACCENT,
                 darkcolor=ACCENT,
                 lightcolor=ACCENT_HOVER,
                 bordercolor=BORDER,
                 thickness=8)
    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=HEADER_BG, height=60)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        left = tk.Frame(hdr, bg=HEADER_BG)
        left.pack(side="left", fill="y")
        tk.Label(left, text="⬡  SPMF Server Client", bg=HEADER_BG,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 14, "bold")).pack(
            side="left", padx=20, pady=10)
        tk.Label(left, text=f"v{VERSION}", bg=HEADER_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 9)).pack(
            side="left", pady=10)
        for text, cmd, tip in [
            ("ℹ  About",     self._open_about,    "About (F1)"),
            ("⚙  Settings",  self._open_settings, "Settings (Ctrl+,)"),
        ]:
            tk.Button(left, text=text, command=cmd,
                       bg=HEADER_BG, fg=TEXT_SEC, relief="flat",
                       cursor="hand2", font=("Segoe UI", 9),
                       padx=10, pady=6, bd=0,
                       activebackground=TAG_BG,
                       activeforeground=TEXT_PRIMARY).pack(
                side="left", padx=(4, 0), pady=10)

        conn = tk.Frame(hdr, bg=HEADER_BG)
        conn.pack(side="right", padx=16, pady=8)
        for lbl, var, w, show, tip in [
            ("Host:",    self._host,   12, None, "Server hostname or IP"),
            ("Port:",    self._port,    6, None, "Server port (default 8585)"),
            ("API Key:", self._apikey, 12, "•",  "API key (leave empty if not required)"),
        ]:
            tk.Label(conn, text=lbl, bg=HEADER_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
            e = styled_entry(conn, var, width=w, show=show)
            e.pack(side="left", padx=(0, 8))
            Tooltip(e, tip)

        self._conn_btn = tk.Button(
            conn, text="Connect", command=self._on_connect,
            bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=14, pady=4,
            activebackground=ACCENT_HOVER, activeforeground=TEXT_PRIMARY)
        self._conn_btn.pack(side="left", padx=(0, 6))
        Tooltip(self._conn_btn, "Connect to SPMF server")

        self._disconn_btn = tk.Button(
            conn, text="Disconnect", command=self._on_disconnect,
            bg=PANEL_BG, fg=TEXT_SEC, relief="flat", cursor="hand2",
            font=("Segoe UI", 9), padx=10, pady=4,
            activebackground=DANGER_BG, activeforeground=TEXT_PRIMARY)
        self._disconn_btn.pack(side="left")
        Tooltip(self._disconn_btn, "Disconnect from server")

        self._dot_lbl = tk.Label(hdr, text="●", bg=HEADER_BG,
                                  fg=ERROR_COL, font=("Segoe UI", 16))
        self._dot_lbl.pack(side="right", padx=(0, 6))
        Tooltip(self._dot_lbl, "Green = connected  /  Red = disconnected")

    def _open_about(self):
        AboutWindow(self)

    def _open_settings(self):
        SettingsWindow(self, self._cfg, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        self._log_write("Settings saved.", "ok")
        if self._cfg.get("auto_refresh"):
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()
        wrap = "word" if self._cfg.get("wrap_result") else "none"
        self._result_text.config(wrap=wrap)
        self._console_text.config(wrap=wrap)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Not connected.")
        tk.Label(bar, textvariable=self._status_var, bg=HEADER_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8), anchor="w").pack(
            side="left", padx=10, fill="y")
        tk.Label(bar,
                 text="F5=Refresh  •  Ctrl+Enter=Submit  •  "
                      "Ctrl+K=Clear Log  •  F1=About",
                 bg=HEADER_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 7)).pack(side="right", padx=12)
        self._busy_lbl = tk.Label(bar, text="", bg=HEADER_BG,
                                   fg=WARNING, font=("Segoe UI", 8))
        self._busy_lbl.pack(side="right", padx=10)

    def _set_status(self, msg: str, colour: str = TEXT_DIM):
        self._status_var.set(msg)

    def _set_busy(self, msg: str = ""):
        self._busy_lbl.config(text=msg)

    # ── Notebook / tabs ───────────────────────────────────────────────────────

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

        # Health card
        hc = card_frame(tab)
        hc.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        section_label(hc, "Server Health")
        self._health_vars: Dict[str, tk.StringVar] = {}
        for key, lbl, tip in [
            ("status",               "Status",            "UP = healthy"),
            ("version",              "Version",           "SPMF version"),
            ("spmfAlgorithmsLoaded", "Algorithms Loaded", "Total algorithms"),
            ("uptimeSeconds",        "Uptime (s)",        "Seconds since start"),
            ("activeJobs",           "Active Jobs",       "Running now"),
            ("queuedJobs",           "Queued Jobs",       "Waiting to run"),
            ("totalJobsInRegistry",  "In Registry",       "All tracked jobs"),
        ]:
            v = tk.StringVar(value="—")
            self._health_vars[key] = v
            kv_row(hc, lbl, v, tooltip=tip)
        br = tk.Frame(hc, bg=PANEL_BG)
        br.pack(fill="x", padx=16, pady=12)
        styled_button(br, "↺  Refresh Health",
                      self._refresh_health,
                      tooltip="Reload server health (F5)").pack(side="left")

        # Info card
        ic = card_frame(tab)
        ic.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        section_label(ic, "Server Configuration")
        self._info_vars: Dict[str, tk.StringVar] = {}
        for key, lbl, tip in [
            ("version",        "Version",        "SPMF library version"),
            ("port",           "Port",           "Listening port"),
            ("host",           "Host",           "Bound interface"),
            ("coreThreads",    "Core Threads",   "Pool core size"),
            ("maxThreads",     "Max Threads",    "Pool maximum"),
            ("jobTtlMinutes",  "Job TTL (min)",  "How long jobs are kept"),
            ("maxQueueSize",   "Max Queue",      "Max waiting jobs"),
            ("workDir",        "Work Dir",       "Job working directory"),
            ("maxInputSizeMb", "Max Input (MB)", "Upload size limit"),
            ("apiKeyEnabled",  "API Key",        "Auth enabled?"),
            ("logLevel",       "Log Level",      "Server log verbosity"),
        ]:
            v = tk.StringVar(value="—")
            self._info_vars[key] = v
            kv_row(ic, lbl, v, label_width=18, tooltip=tip)
        br2 = tk.Frame(ic, bg=PANEL_BG)
        br2.pack(fill="x", padx=16, pady=12)
        styled_button(br2, "↺  Refresh Info",
                      self._refresh_info,
                      tooltip="Reload server configuration").pack(side="left")

        # Activity log
        lc = card_frame(tab)
        lc.grid(row=1, column=0, columnspan=2,
                padx=10, pady=(0, 10), sticky="nsew")
        hdr2 = tk.Frame(lc, bg=PANEL_BG)
        hdr2.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(hdr2, text="Activity Log", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        styled_button(hdr2, "💾 Export", self._export_log,
                      bg=PANEL_BG, fg=TEXT_DIM, font_size=8,
                      tooltip="Save log to file").pack(side="right")
        styled_button(hdr2, "Clear", self._clear_log,
                      bg=PANEL_BG, fg=TEXT_DIM, font_size=8,
                      tooltip="Clear log (Ctrl+K)").pack(
            side="right", padx=(0, 4))
        self._log = scrolledtext.ScrolledText(
            lc, bg=ENTRY_BG, fg=TEXT_PRIMARY,
            font=("Consolas", 9), relief="flat",
            wrap="word", state="disabled", height=8)
        self._log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        for tag, col in [("ok",   SUCCESS), ("err",  ERROR_COL),
                          ("warn", WARNING), ("info", TEXT_SEC),
                          ("dim",  TEXT_DIM)]:
            self._log.tag_config(tag, foreground=col)

    def _log_write(self, msg: str, tag: str = "info"):
        self._log.config(state="normal")
        lines = int(self._log.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self._log.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        ts = time.strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] ", "dim")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _export_log(self):
        content = self._log.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Empty Log", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export activity log", defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt")])
        if path:
            Path(path).write_text(content, "utf-8")
            messagebox.showinfo("Exported", f"Log saved to:\n{path}")

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Algorithms
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_algorithms(self):
        tab = self._tab_algorithms
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(0, weight=1)

        # ── Left: list ────────────────────────────────────────────────────
        left = card_frame(tab)
        left.grid(row=0, column=0, padx=(10, 4), pady=10, sticky="nsew")
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        hdr = tk.Frame(left, bg=PANEL_BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        tk.Label(hdr, text="Algorithm List", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        styled_button(hdr, "↺", self._refresh_algorithms,
                      font_size=9,
                      tooltip="Reload algorithms (F5)").pack(side="right")
        icon_button(hdr, "★", self._toggle_favorites_only,
                    tooltip="Show favorites only",
                    fg=FAV_COL).pack(side="right", padx=(0, 4))

        flt = tk.Frame(left, bg=PANEL_BG)
        flt.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        tk.Label(flt, text="🔍", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 3))
        self._algo_search = tk.StringVar()
        self._algo_search.trace_add("write", lambda *_: self._filter_algorithms())
        styled_entry(flt, self._algo_search).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self._algo_cat_var = tk.StringVar(value="All Categories")
        self._algo_cat_combo = ttk.Combobox(
            flt, textvariable=self._algo_cat_var,
            state="readonly", width=18, font=("Segoe UI", 8))
        self._algo_cat_combo["values"] = ["All Categories"]
        self._algo_cat_combo.bind("<<ComboboxSelected>>",
                                   lambda _: self._filter_algorithms())
        self._algo_cat_combo.pack(side="left")
        Tooltip(self._algo_cat_combo, "Filter by category")

        self._algo_count_var = tk.StringVar(value="0 algorithms")
        tk.Label(left, textvariable=self._algo_count_var,
                 bg=PANEL_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8)).grid(row=2, column=0,
                                             sticky="w", padx=10)

        tf = tk.Frame(left, bg=PANEL_BG)
        tf.grid(row=3, column=0, sticky="nsew", padx=8, pady=(2, 8))
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        self._algo_tree = ttk.Treeview(
            tf, columns=("fav", "name", "category"),
            show="headings", selectmode="browse")
        self._algo_tree.heading("fav",      text="★")
        self._algo_tree.heading("name",     text="Algorithm")
        self._algo_tree.heading("category", text="Category")
        self._algo_tree.column("fav",      width=28,  minwidth=28,  stretch=False)
        self._algo_tree.column("name",     width=190, minwidth=120)
        self._algo_tree.column("category", width=150, minwidth=100)
        self._algo_tree.grid(row=0, column=0, sticky="nsew")
        self._algo_tree.bind("<<TreeviewSelect>>", self._on_algo_select)
        self._algo_tree.bind("<Double-1>", lambda _: self._use_algo_in_run())
        self._algo_tree.tag_configure("fav", foreground=FAV_COL)

        vsb = ttk.Scrollbar(tf, orient="vertical",
                             command=self._algo_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._algo_tree.configure(yscrollcommand=vsb.set)

        # ── Right: detail ─────────────────────────────────────────────────
        right = card_frame(tab)
        right.grid(row=0, column=1, padx=(4, 10), pady=10, sticky="nsew")
        right.rowconfigure(7, weight=1)
        right.columnconfigure(0, weight=1)

        hdr2 = tk.Frame(right, bg=PANEL_BG)
        hdr2.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        tk.Label(hdr2, text="Algorithm Details", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self._fav_btn = icon_button(hdr2, "☆",
                                     self._toggle_current_fav,
                                     tooltip="Add/remove from favorites",
                                     fg=FAV_COL)
        self._fav_btn.pack(side="right")

        self._detail_vars: Dict[str, tk.StringVar] = {}
        for i, (key, lbl, tip) in enumerate([
            ("name",                     "Name",          "Algorithm name"),
            ("algorithmCategory",         "Category",      "Algorithm family"),
            ("implementationAuthorNames", "Author(s)",     "Implementation credit"),
            ("algorithmType",             "Type",          "Output type"),
            ("documentationURL",          "Documentation", "Paper / web page"),
        ], start=1):
            row = tk.Frame(right, bg=PANEL_BG)
            row.grid(row=i, column=0, sticky="ew", padx=16, pady=2)
            tk.Label(row, text=lbl + ":", bg=PANEL_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9), width=14,
                     anchor="w").pack(side="left")
            v = tk.StringVar(value="—")
            self._detail_vars[key] = v
            lw = tk.Label(row, textvariable=v, bg=PANEL_BG,
                           fg=TEXT_PRIMARY, font=("Consolas", 9),
                           anchor="w", wraplength=420, justify="left")
            lw.pack(side="left", fill="x", expand=True)
            Tooltip(lw, tip)

        tk.Label(right, text="Parameters & I/O", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).grid(
            row=6, column=0, sticky="w", padx=16, pady=(10, 2))
        self._detail_text = scrolledtext.ScrolledText(
            right, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
            relief="flat", state="disabled", wrap="word", height=14)
        self._detail_text.grid(row=7, column=0, sticky="nsew",
                                padx=10, pady=(0, 8))
        self._detail_text.tag_config("label",  foreground=ACCENT)
        self._detail_text.tag_config("header", foreground=INFO_COL)
        self._detail_text.tag_config("mand",   foreground=ERROR_COL)
        self._detail_text.tag_config("opt",    foreground=TEXT_DIM)

        br = tk.Frame(right, bg=PANEL_BG)
        br.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 12))
        styled_button(br, "▶  Use in Run Job",
                      self._use_algo_in_run,
                      tooltip="Load into Run Job tab "
                              "(or double-click row)").pack(side="left")
        styled_button(br, "⧉  Copy Name",
                      self._copy_algo_name,
                      bg=PANEL_BG, fg=TEXT_SEC, font_size=9,
                      tooltip="Copy algorithm name to clipboard").pack(
            side="left", padx=(8, 0))

    def _toggle_favorites_only(self):
        self._favs_only = not self._favs_only
        self._filter_algorithms()

    def _toggle_current_fav(self):
        name = self._detail_vars.get("name", tk.StringVar()).get()
        if not name or name == "—":
            return
        added = self._cfg.toggle_favorite(name)
        self._cfg.save()
        self._fav_btn.config(text="★" if added else "☆")
        self._log_write(
            f"{'Added' if added else 'Removed'} '{name}' "
            f"{'to' if added else 'from'} favorites.", "info")
        self._render_algo_tree(self._last_filtered)

    def _copy_algo_name(self):
        name = self._detail_vars.get("name", tk.StringVar()).get()
        if name and name != "—":
            self.clipboard_clear()
            self.clipboard_append(name)
            self._log_write(f"Copied: {name}", "info")

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Run Job
    # ══════════════════════════════════════════════════════════════════════════

 def _build_tab_run(self):
    tab = self._tab_run
    tab.columnconfigure(0, weight=1)
    tab.columnconfigure(1, weight=1)
    tab.rowconfigure(1, weight=1)

    # ── Left: config ──────────────────────────────────────────────────
    left = card_frame(tab)
    left.grid(row=0, column=0, rowspan=2, padx=(10, 4),
              pady=10, sticky="nsew")
    left.columnconfigure(1, weight=1)

    tk.Label(left, text="Job Configuration", bg=PANEL_BG, fg=ACCENT,
             font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w",
        padx=16, pady=(12, 4))
    ttk.Separator(left).grid(row=1, column=0, columnspan=3,
                              sticky="ew", padx=10, pady=(0, 8))

    # Algorithm row
    tk.Label(left, text="Algorithm:", bg=PANEL_BG, fg=TEXT_SEC,
             font=("Segoe UI", 9), anchor="w").grid(
        row=2, column=0, sticky="w", padx=16, pady=4)
    self._run_algo_var = tk.StringVar(
        value=str(self._cfg.get("last_algo", "")))
    self._run_algo_combo = ttk.Combobox(
        left, textvariable=self._run_algo_var,
        state="readonly", font=("Consolas", 10))
    self._run_algo_combo.grid(row=2, column=1, sticky="ew",
                               padx=(0, 4), pady=4)
    self._run_algo_combo.bind("<<ComboboxSelected>>",
                               self._on_run_algo_select)
    Tooltip(self._run_algo_combo, "Select the algorithm to run")
    styled_button(left, "ℹ", self._describe_run_algo,
                  font_size=9,
                  tooltip="Show parameter guide").grid(
        row=2, column=2, padx=(0, 8), pady=4)

    # Input file row
    tk.Label(left, text="Input File:", bg=PANEL_BG, fg=TEXT_SEC,
             font=("Segoe UI", 9), anchor="w").grid(
        row=3, column=0, sticky="w", padx=16, pady=4)
    self._run_file_var = tk.StringVar(
        value=str(self._cfg.get("last_file", "")))
    fe = styled_entry(left, self._run_file_var)
    fe.grid(row=3, column=1, sticky="ew", padx=(0, 4), pady=4)
    Tooltip(fe, "Path to input dataset file")
    styled_button(left, "Browse…", self._browse_input,
                  font_size=9,
                  tooltip="Open file chooser").grid(
        row=3, column=2, padx=(0, 8), pady=4)

    # Parameters row
    tk.Label(left, text="Parameters:", bg=PANEL_BG, fg=TEXT_SEC,
             font=("Segoe UI", 9), anchor="w").grid(
        row=4, column=0, sticky="nw", padx=16, pady=4)
    self._run_params_var = tk.StringVar()
    pe = styled_entry(left, self._run_params_var)
    pe.grid(row=4, column=1, columnspan=2,
            sticky="ew", padx=(0, 16), pady=4)
    Tooltip(pe, "Space-separated values, e.g.: 0.5 3")
    tk.Label(left, text="Space-separated, e.g.: 0.5  3",
             bg=PANEL_BG, fg=TEXT_DIM,
             font=("Segoe UI", 8)).grid(
        row=5, column=1, sticky="w", padx=(0, 8))

    # Options checkboxes
    tk.Label(left, text="Options:", bg=PANEL_BG, fg=TEXT_SEC,
             font=("Segoe UI", 9), anchor="w").grid(
        row=6, column=0, sticky="w", padx=16, pady=(12, 4))
    opt = tk.Frame(left, bg=PANEL_BG)
    opt.grid(row=6, column=1, columnspan=2, sticky="w", pady=(12, 4))
    self._run_base64_var  = tk.BooleanVar(value=False)
    self._run_noclean_var = tk.BooleanVar(value=False)
    for var, text, tip in [
        (self._run_base64_var,
         "Base64 encode input",
         "Encode input file in Base64 before sending"),
        (self._run_noclean_var,
         "Keep job after completion",
         "Do not auto-delete the job when done"),
    ]:
        cb = tk.Checkbutton(opt, text=text, variable=var,
                             bg=PANEL_BG, fg=TEXT_PRIMARY,
                             selectcolor=ACCENT,
                             activebackground=PANEL_BG,
                             activeforeground=TEXT_PRIMARY,
                             font=("Segoe UI", 9), cursor="hand2")
        cb.pack(side="left", padx=(0, 16))
        Tooltip(cb, tip)

    # Poll / timeout rows
    for row_idx, (lbl, attr, cfg_key, tip) in enumerate([
        ("Poll interval (s)", "_run_poll_var",
         "poll_interval", "Seconds between status checks"),
        ("Timeout (s)",       "_run_timeout_var",
         "timeout",       "Max seconds to wait for completion"),
    ], start=7):
        tk.Label(left, text=lbl + ":", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=row_idx, column=0, sticky="w", padx=16, pady=4)
        setattr(self, attr,
                tk.StringVar(value=str(self._cfg.get(cfg_key))))
        e = styled_entry(left, getattr(self, attr), width=8)
        e.grid(row=row_idx, column=1, sticky="w",
               padx=(0, 8), pady=4)
        Tooltip(e, tip)

    ttk.Separator(left).grid(row=9, column=0, columnspan=3,
                              sticky="ew", padx=10, pady=10)

    # Submit / cancel buttons
    btns = tk.Frame(left, bg=PANEL_BG)
    btns.grid(row=10, column=0, columnspan=3, pady=(0, 4))
    self._run_btn = styled_button(
        btns, "▶  Submit Job  (Ctrl+Enter)",
        self._submit_job, font_size=11,
        tooltip="Submit job to server")
    self._run_btn.pack(side="left", padx=(0, 8))
    self._cancel_btn = styled_button(
        btns, "⏹  Cancel",
        self._cancel_job, bg=DANGER_BG, font_size=10,
        tooltip="Cancel current poll")
    self._cancel_btn.pack(side="left")
    self._cancel_btn.config(state="disabled")

    # ── Progressbar ────────────────────────────────────────────────────
    # Style name must match exactly what was registered in
    # _apply_ttk_style: "Horizontal.Accent.TProgressbar"
	self._progress_bar = ttk.Progressbar(
    left,
    orient="horizontal",
    mode="indeterminate")
	self._progress_bar.grid(row=11, column=0, columnspan=3,
                         sticky="ew", padx=16, pady=(4, 12))

    # ── Right top: parameter guide ────────────────────────────────────
    hc = card_frame(tab)
    hc.grid(row=0, column=1, padx=(4, 10), pady=10, sticky="nsew")
    hc.rowconfigure(1, weight=1)
    hc.columnconfigure(0, weight=1)
    tk.Label(hc, text="Parameter Guide", bg=PANEL_BG, fg=ACCENT,
             font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, sticky="w", padx=16, pady=(12, 4))
    self._param_hint = scrolledtext.ScrolledText(
        hc, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
        relief="flat", state="disabled", wrap="word")
    self._param_hint.grid(row=1, column=0, sticky="nsew",
                           padx=8, pady=(0, 8))

    # ── Right bottom: progress log ────────────────────────────────────
    pc = card_frame(tab)
    pc.grid(row=1, column=1, padx=(4, 10), pady=(0, 10), sticky="nsew")
    pc.rowconfigure(2, weight=1)
    pc.columnconfigure(0, weight=1)

    phdr = tk.Frame(pc, bg=PANEL_BG)
    phdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
    tk.Label(phdr, text="Job Progress", bg=PANEL_BG, fg=ACCENT,
             font=("Segoe UI", 11, "bold")).pack(side="left")
    styled_button(phdr, "Clear", self._clear_run_log,
                  bg=PANEL_BG, fg=TEXT_DIM, font_size=8).pack(
        side="right")

    self._progress_var = tk.StringVar(value="Idle")
    tk.Label(pc, textvariable=self._progress_var,
             bg=PANEL_BG, fg=TEXT_PRIMARY,
             font=("Segoe UI", 10)).grid(
        row=1, column=0, sticky="w", padx=16)
    self._run_log = scrolledtext.ScrolledText(
        pc, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 9),
        relief="flat", state="disabled", wrap="word", height=8)
    self._run_log.grid(row=2, column=0, sticky="nsew",
                        padx=8, pady=(4, 8))
    for tag, col in [("ok",   SUCCESS), ("err",  ERROR_COL),
                      ("warn", WARNING), ("info", TEXT_SEC),
                      ("dim",  TEXT_DIM)]:
        self._run_log.tag_config(tag, foreground=col)

    def _clear_run_log(self):
        self._run_log.config(state="normal")
        self._run_log.delete("1.0", "end")
        self._run_log.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Jobs
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_jobs(self):
        tab = self._tab_jobs
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        tb = tk.Frame(tab, bg=DARK_BG)
        tb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        styled_button(tb, "↺  Refresh",
                      self._refresh_jobs,
                      tooltip="Reload jobs (F5)").pack(
            side="left", padx=(0, 6))
        styled_button(tb, "🗑  Delete Selected",
                      self._delete_selected_job, bg=DANGER_BG,
                      tooltip="Delete selected job").pack(
            side="left", padx=(0, 6))
        styled_button(tb, "🗑  Delete All Done",
                      self._delete_all_done, bg=DANGER_BG,
                      tooltip="Delete all DONE/FAILED/CANCELLED jobs").pack(
            side="left", padx=(0, 6))
        styled_button(tb, "📋  View Result",
                      self._view_selected_result, bg=SAFE_BG,
                      tooltip="View result for selected job").pack(
            side="left", padx=(0, 6))
        styled_button(tb, "📤  Export CSV",
                      self._export_jobs_csv,
                      bg=PANEL_BG, fg=TEXT_SEC, font_size=9,
                      tooltip="Export job list as CSV").pack(side="left")

        # Right side of toolbar: auto-refresh + status filter
        right_tb = tk.Frame(tab, bg=DARK_BG)
        right_tb.grid(row=0, column=0, sticky="e", padx=10, pady=(10, 0))

        tk.Label(right_tb, text="Filter:", bg=DARK_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._jobs_filter_var = tk.StringVar(value="All")
        flt = ttk.Combobox(right_tb, textvariable=self._jobs_filter_var,
                            state="readonly", width=10,
                            values=["All", "DONE", "FAILED",
                                    "RUNNING", "QUEUED", "CANCELLED"])
        flt.pack(side="left", padx=(0, 12))
        flt.bind("<<ComboboxSelected>>",
                 lambda _: self._apply_jobs_filter())
        Tooltip(flt, "Filter jobs by status")

        self._auto_refresh_var = tk.BooleanVar(
            value=bool(self._cfg.get("auto_refresh")))
        ar = tk.Checkbutton(
            right_tb, text="Auto-refresh",
            variable=self._auto_refresh_var,
            command=self._toggle_auto_refresh,
            bg=DARK_BG, fg=TEXT_SEC, selectcolor=ACCENT,
            activebackground=DARK_BG, font=("Segoe UI", 9))
        ar.pack(side="left")
        Tooltip(ar, "Periodically refresh jobs and health")

        # Tree
        card = card_frame(tab)
        card.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        cols = ("jobId", "algorithmName", "status",
                "submittedAt", "executionTimeMs")
        self._jobs_tree = ttk.Treeview(card, columns=cols,
                                        show="headings",
                                        selectmode="browse")
        for col, (text, width) in {
            "jobId":           ("Job ID",       260),
            "algorithmName":   ("Algorithm",    180),
            "status":          ("Status",        90),
            "submittedAt":     ("Submitted At", 180),
            "executionTimeMs": ("Exec (ms)",     90),
        }.items():
            self._jobs_tree.heading(
                col, text=text,
                command=lambda c=col: self._sort_jobs_by(c))
            self._jobs_tree.column(col, width=width, minwidth=60)
        self._jobs_tree.grid(row=0, column=0, sticky="nsew")
        for status, colour in [
            ("DONE",      SUCCESS),  ("FAILED",    ERROR_COL),
            ("RUNNING",   WARNING),  ("QUEUED",    TEXT_SEC),
            ("CANCELLED", TEXT_DIM),
        ]:
            self._jobs_tree.tag_configure(status, foreground=colour)
        self._jobs_tree.bind("<Double-1>",
                              lambda _: self._view_selected_result())

        vsb = ttk.Scrollbar(card, orient="vertical",
                             command=self._jobs_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._jobs_tree.configure(yscrollcommand=vsb.set)

        self._jobs_count_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self._jobs_count_var, bg=DARK_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8)).grid(
            row=2, column=0, sticky="w", padx=12, pady=(0, 4))

    def _sort_jobs_by(self, col: str):
        if self._jobs_sort_col == col:
            self._jobs_sort_rev = not self._jobs_sort_rev
        else:
            self._jobs_sort_col = col
            self._jobs_sort_rev = False
        self._apply_jobs_filter()

    def _apply_jobs_filter(self):
        sf   = self._jobs_filter_var.get()
        jobs = self._jobs if sf == "All" else [
            j for j in self._jobs if j.get("status") == sf]
        col  = self._jobs_sort_col
        try:
            jobs = sorted(jobs,
                          key=lambda j: j.get(col, "") or "",
                          reverse=self._jobs_sort_rev)
        except Exception:
            pass
        self._jobs_tree.delete(*self._jobs_tree.get_children())
        for j in jobs:
            st = j.get("status", "?")
            self._jobs_tree.insert(
                "", "end",
                values=(j.get("jobId", "?"),
                        j.get("algorithmName", "?"),
                        st,
                        j.get("submittedAt", "?"),
                        j.get("executionTimeMs", "?")),
                tags=(st,))
        self._jobs_count_var.set(
            f"Showing {len(jobs)} of {len(self._jobs)} jobs")

    def _export_jobs_csv(self):
        if not self._jobs:
            messagebox.showinfo("No Jobs", "No jobs to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export jobs", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        keys = ("jobId", "algorithmName", "status",
                "submittedAt", "executionTimeMs")
        lines = [",".join(keys)]
        for j in self._jobs:
            lines.append(",".join(str(j.get(k, "")) for k in keys))
        Path(path).write_text("\n".join(lines), "utf-8")
        self._log_write(f"Jobs exported to: {path}", "ok")
        messagebox.showinfo("Exported", f"Jobs saved to:\n{path}")

    def _delete_all_done(self):
        done = [j for j in self._jobs
                if j.get("status") in ("DONE", "FAILED", "CANCELLED")]
        if not done:
            messagebox.showinfo("Nothing to Delete",
                                "No completed jobs found.")
            return
        if not messagebox.askyesno(
                "Confirm", f"Delete {len(done)} completed jobs?"):
            return
        host, port, key = self._get_conn()

        def worker():
            errs = 0
            for j in done:
                try:
                    api_delete(host, port, key,
                               f"/api/jobs/{j['jobId']}")
                except Exception:
                    errs += 1
            self.after(0, self._log_write,
                       f"Deleted {len(done) - errs} jobs "
                       f"({errs} errors).", "ok")
            self.after(0, self._refresh_jobs)

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB: Result
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_result(self):
        tab = self._tab_result
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        tb = tk.Frame(tab, bg=DARK_BG)
        tb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        tk.Label(tb, text="Job ID:", bg=DARK_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._result_jobid_var = tk.StringVar()
        jid = styled_entry(tb, self._result_jobid_var, width=38)
        jid.pack(side="left", padx=(0, 8))
        Tooltip(jid, "Paste a Job ID here to fetch its result")

        styled_button(tb, "Fetch Result + Console",
                      self._fetch_result,
                      tooltip="Fetch result and console output").pack(
            side="left", padx=(0, 8))
        styled_button(tb, "💾  Save Result",
                      self._save_result, bg=SAFE_BG,
                      tooltip="Save result to file").pack(
            side="left", padx=(0, 4))
        styled_button(tb, "💾  Save Console",
                      self._save_console, bg=SAFE_BG,
                      tooltip="Save console output to file").pack(
            side="left", padx=(0, 8))

        self._wrap_var = tk.BooleanVar(
            value=bool(self._cfg.get("wrap_result")))
        wc = tk.Checkbutton(
            tb, text="Wrap", variable=self._wrap_var,
            command=self._toggle_wrap,
            bg=DARK_BG, fg=TEXT_SEC, selectcolor=ACCENT,
            activebackground=DARK_BG, font=("Segoe UI", 9))
        wc.pack(side="left", padx=(4, 0))
        Tooltip(wc, "Toggle word-wrap")

        self._result_info_var = tk.StringVar(value="")
        tk.Label(tb, textvariable=self._result_info_var,
                 bg=DARK_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="right", padx=10)

        pane = tk.Frame(tab, bg=DARK_BG)
        pane.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)
        pane.columnconfigure(1, weight=1)

        initial_wrap = "word" if self._wrap_var.get() else "none"

        # Result card
        rc = card_frame(pane)
        rc.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        rc.rowconfigure(1, weight=1)
        rc.columnconfigure(0, weight=1)
        rh = tk.Frame(rc, bg=PANEL_BG)
        rh.grid(row=0, column=0, columnspan=2, sticky="ew",
                padx=8, pady=(8, 4))
        tk.Label(rh, text="Result Output", bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._res_lines_var = tk.StringVar(value="")
        tk.Label(rh, textvariable=self._res_lines_var, bg=PANEL_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="right")
        self._result_text = scrolledtext.ScrolledText(
            rc, bg=ENTRY_BG, fg=TEXT_PRIMARY, font=("Consolas", 10),
            relief="flat", state="disabled", wrap=initial_wrap)
        self._result_text.grid(row=1, column=0, sticky="nsew",
                                padx=4, pady=(0, 4))
        res_hsb = ttk.Scrollbar(rc, orient="horizontal",
                                 command=self._result_text.xview)
        res_hsb.grid(row=2, column=0, sticky="ew", padx=4)
        self._result_text.configure(xscrollcommand=res_hsb.set)

        # Console card
        cc = card_frame(pane)
        cc.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        cc.rowconfigure(1, weight=1)
        cc.columnconfigure(0, weight=1)
        ch = tk.Frame(cc, bg=PANEL_BG)
        ch.grid(row=0, column=0, columnspan=2, sticky="ew",
                padx=8, pady=(8, 4))
        tk.Label(ch, text="Console Output  (stdout / stderr)",
                 bg=PANEL_BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self._con_lines_var = tk.StringVar(value="")
        tk.Label(ch, textvariable=self._con_lines_var, bg=PANEL_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="right")
        self._console_text = scrolledtext.ScrolledText(
            cc, bg=ENTRY_BG, fg=CONSOLE_FG, font=("Consolas", 10),
            relief="flat", state="disabled", wrap=initial_wrap)
        self._console_text.grid(row=1, column=0, sticky="nsew",
                                 padx=4, pady=(0, 4))
        con_hsb = ttk.Scrollbar(cc, orient="horizontal",
                                 command=self._console_text.xview)
        con_hsb.grid(row=2, column=0, sticky="ew", padx=4)
        self._console_text.configure(xscrollcommand=con_hsb.set)

    def _toggle_wrap(self):
        wrap = "word" if self._wrap_var.get() else "none"
        self._result_text.config(wrap=wrap)
        self._console_text.config(wrap=wrap)
        self._cfg.set("wrap_result", self._wrap_var.get())

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
        self._conn_btn.config(state="disabled")

        def worker():
            try:
                resp = api_get(host, port, self._apikey.get(),
                               "/api/health", timeout=5)
                if resp.status_code == 200:
                    self.after(0, self._on_connected, resp.json())
                else:
                    self.after(0, self._on_connect_fail,
                               f"HTTP {resp.status_code}: "
                               f"{_safe_json_error(resp)}")
            except requests.exceptions.ConnectionRefusedError:
                self.after(0, self._on_connect_fail,
                           f"Connection refused at {host}:{port}.")
            except requests.exceptions.Timeout:
                self.after(0, self._on_connect_fail,
                           "Connection timed out.")
            except Exception as exc:
                self.after(0, self._on_connect_fail, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connected(self, health_data: dict):
        self._connected = True
        self._dot_lbl.config(fg=SUCCESS)
        self._conn_btn.config(text="Reconnect", state="normal")
        ver  = health_data.get("version", "?")
        algo = health_data.get("spmfAlgorithmsLoaded", "?")
        self._set_status(
            f"Connected  {self._host.get()}:{self._port.get()}  |  "
            f"SPMF {ver}  |  {algo} algorithms", SUCCESS)
        self._set_busy("")
        self._log_write(
            f"Connected to {self._host.get()}:{self._port.get()} "
            f"(SPMF {ver}, {algo} algos)", "ok")
        self._update_health_card(health_data)
        self._refresh_info()
        self._refresh_algorithms()
        if self._cfg.get("auto_refresh"):
            self._start_auto_refresh()

    def _on_connect_fail(self, reason: str):
        self._connected = False
        self._dot_lbl.config(fg=ERROR_COL)
        self._conn_btn.config(state="normal")
        self._set_status(f"Connection failed: {reason}", ERROR_COL)
        self._set_busy("")
        self._log_write(f"Connection failed: {reason}", "err")

    def _on_disconnect(self):
        self._connected = False
        self._stop_auto_refresh()
        self._dot_lbl.config(fg=ERROR_COL)
        self._conn_btn.config(text="Connect")
        self._set_status("Disconnected.", TEXT_DIM)
        self._log_write("Disconnected.", "warn")

    # ── Auto-refresh ──────────────────────────────────────────────────────────

    def _toggle_auto_refresh(self):
        if self._auto_refresh_var.get():
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()
        self._cfg.set("auto_refresh", self._auto_refresh_var.get())

    def _start_auto_refresh(self):
        self._stop_auto_refresh()
        try:
            every = int(float(self._cfg.get("refresh_every", 10)) * 1000)
        except ValueError:
            every = 10_000
        every = max(every, 2000)

        def tick():
            if self._connected:
                self._refresh_jobs()
                self._refresh_health()
            self._auto_after = self.after(every, tick)

        self._auto_after = self.after(every, tick)
        self._log_write(
            f"Auto-refresh started (every {every // 1000}s).", "info")

    def _stop_auto_refresh(self):
        if self._auto_after:
            self.after_cancel(self._auto_after)
            self._auto_after = None

    # ══════════════════════════════════════════════════════════════════════════
    #  API helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _get_conn(self):
        return (self._host.get().strip(),
                int(self._port.get().strip()),
                self._apikey.get().strip())

    def _require_connection(self) -> bool:
        if not self._connected:
            messagebox.showwarning(
                "Not Connected",
                "Please connect to an SPMF server first.")
            return False
        return True

    # ── Health ────────────────────────────────────────────────────────────────

    def _refresh_health(self):
        if not self._connected:
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_get(host, port, key, "/api/health")
                if resp.status_code == 200:
                    self.after(0, self._update_health_card, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Health check failed: HTTP {resp.status_code}",
                               "err")
            except Exception as e:
                self.after(0, self._log_write,
                           f"Health error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _update_health_card(self, data: dict):
        for key, var in self._health_vars.items():
            val = data.get(key, "—")
            if key == "status":
                var.set(("✓  " if val == "UP" else "✗  ") + str(val))
            else:
                var.set(str(val))

    # ── Info ──────────────────────────────────────────────────────────────────

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
                self.after(0, self._log_write,
                           f"Info error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _update_info_card(self, data: dict):
        for key, var in self._info_vars.items():
            var.set(str(data.get(key, "—")))

    # ── Algorithms ────────────────────────────────────────────────────────────

    def _refresh_algorithms(self):
        if not self._connected:
            return
        host, port, key = self._get_conn()
        self._log_write("Loading algorithms…", "info")
        self._set_busy("⟳ loading algorithms")

        def worker():
            try:
                resp = api_get(host, port, key,
                               "/api/algorithms", timeout=30)
                if resp.status_code == 200:
                    self.after(0, self._populate_algorithms, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Algorithms list failed: "
                               f"HTTP {resp.status_code}", "err")
            except Exception as e:
                self.after(0, self._log_write,
                           f"Algorithms error: {e}", "err")
            finally:
                self.after(0, self._set_busy, "")

        threading.Thread(target=worker, daemon=True).start()

    def _populate_algorithms(self, data: dict):
        self._algorithms = data.get("algorithms", [])
        cats = sorted({a.get("algorithmCategory", "—")
                       for a in self._algorithms})
        self._algo_cat_combo["values"] = ["All Categories"] + cats
        names = sorted(a.get("name", "") for a in self._algorithms)
        self._run_algo_combo["values"] = names
        self._last_filtered = list(self._algorithms)
        self._filter_algorithms()
        self._log_write(
            f"Loaded {data.get('count', len(self._algorithms))} "
            f"algorithms.", "ok")

    def _render_algo_tree(self, algos: list):
        self._algo_tree.delete(*self._algo_tree.get_children())
        for a in sorted(algos, key=lambda x: x.get("name", "")):
            name   = a.get("name", "?")
            is_fav = self._cfg.is_favorite(name)
            self._algo_tree.insert(
                "", "end",
                values=("★" if is_fav else "",
                        name,
                        a.get("algorithmCategory", "?")),
                tags=("fav",) if is_fav else ())
        self._algo_count_var.set(f"{len(algos)} algorithm(s)")

    def _filter_algorithms(self):
        query = self._algo_search.get().lower()
        cat   = self._algo_cat_var.get()
        fav   = self._favs_only
        filtered = [
            a for a in self._algorithms
            if (query in a.get("name", "").lower()
                or query in a.get("algorithmCategory", "").lower())
            and (cat == "All Categories"
                 or a.get("algorithmCategory") == cat)
            and (not fav or self._cfg.is_favorite(a.get("name", "")))
        ]
        self._last_filtered = filtered
        self._render_algo_tree(filtered)

    def _on_algo_select(self, _event=None):
        sel = self._algo_tree.selection()
        if not sel:
            return
        name = self._algo_tree.item(sel[0], "values")[1]
        self._fetch_algo_detail(name)

    def _fetch_algo_detail(self, name: str):
        host, port, key = self._get_conn()

        def worker():
            try:
                encoded = requests.utils.quote(name, safe="")
                resp    = api_get(host, port, key,
                                  f"/api/algorithms/{encoded}")
                if resp.status_code == 200:
                    self.after(0, self._show_algo_detail, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Describe failed: HTTP {resp.status_code}",
                               "err")
            except Exception as e:
                self.after(0, self._log_write,
                           f"Describe error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _show_algo_detail(self, data: dict):
        name = data.get("name", "—")
        for key, var in self._detail_vars.items():
            var.set(str(data.get(key, "—")))
        self._fav_btn.config(
            text="★" if self._cfg.is_favorite(name) else "☆")

        self._detail_text.config(state="normal")
        self._detail_text.delete("1.0", "end")
        in_t      = data.get("inputFileTypes",  [])
        out_t     = data.get("outputFileTypes", [])
        params    = data.get("parameters",      [])
        mandatory = data.get("numberOfMandatoryParameters", 0)

        for lbl, val in [
            ("Input types  ",
             (", ".join(in_t)  if in_t  else "N/A") + "\n"),
            ("Output types ",
             (", ".join(out_t) if out_t else "N/A") + "\n\n"),
        ]:
            self._detail_text.insert("end", f"{lbl}: ", "label")
            self._detail_text.insert("end", val)

        self._detail_text.insert(
            "end",
            f"Parameters   : {len(params)} total, "
            f"{mandatory} mandatory\n\n",
            "header")
        for i, p in enumerate(params, 1):
            is_opt = p.get("isOptional", False)
            badge  = "opt" if is_opt else "mand"
            tag_s  = "[optional]" if is_opt else "[required]"
            self._detail_text.insert(
                "end", f"  [{i}] {p.get('name','?')}  ")
            self._detail_text.insert("end", tag_s + "\n", badge)
            self._detail_text.insert(
                "end",
                f"       type   : {p.get('parameterType','?')}\n"
                f"       example: {p.get('example','?')}\n\n")
        self._detail_text.config(state="disabled")

    # ── Run Job ───────────────────────────────────────────────────────────────

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select input file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._run_file_var.set(path)
            self._cfg.set("last_file", path)

    def _on_run_algo_select(self, _event=None):
        name = self._run_algo_var.get()
        if name:
            self._cfg.set("last_algo", name)
            self._fetch_param_hint(name)

    def _describe_run_algo(self):
        name = self._run_algo_var.get()
        if not name:
            messagebox.showinfo("No Algorithm",
                                "Select an algorithm first.")
            return
        self._fetch_param_hint(name)

    def _fetch_param_hint(self, name: str):
        host, port, key = self._get_conn()

        def worker():
            try:
                encoded = requests.utils.quote(name, safe="")
                resp    = api_get(host, port, key,
                                  f"/api/algorithms/{encoded}")
                if resp.status_code == 200:
                    self.after(0, self._show_param_hint, resp.json())
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _show_param_hint(self, data: dict):
        self._param_hint.config(state="normal")
        self._param_hint.delete("1.0", "end")
        params    = data.get("parameters",      [])
        mandatory = data.get("numberOfMandatoryParameters", 0)
        in_t      = data.get("inputFileTypes",  [])
        out_t     = data.get("outputFileTypes", [])
        doc       = data.get("documentationURL", "")
        lines = [
            f"Algorithm : {data.get('name','?')}",
            f"Category  : {data.get('algorithmCategory','?')}",
            f"Input     : {', '.join(in_t)}",
            f"Output    : {', '.join(out_t)}",
        ]
        if doc:
            lines.append(f"Docs      : {doc}")
        lines += [
            "",
            f"Parameters ({len(params)} total, {mandatory} mandatory):",
            "─" * 44,
        ]
        for i, p in enumerate(params, 1):
            opt = "[optional]" if p.get("isOptional") else "[required]"
            lines += [
                f"  {i}. {p.get('name','?')}  {opt}",
                f"     type   : {p.get('parameterType','?')}",
                f"     example: {p.get('example','?')}",
                "",
            ]
        self._param_hint.insert("end", "\n".join(lines))
        self._param_hint.config(state="disabled")

    def _use_algo_in_run(self):
        sel = self._algo_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an algorithm first.")
            return
        name = self._algo_tree.item(sel[0], "values")[1]
        self._run_algo_var.set(name)
        self._cfg.set("last_algo", name)
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

    def _cancel_job(self):
        self._cancel_flag.set()
        self._run_log_write("Cancel requested…", "warn")

    def _submit_job(self):
        if not self._require_connection():
            return

        algo       = self._run_algo_var.get().strip()
        fpath      = self._run_file_var.get().strip()
        params_raw = self._run_params_var.get().strip()
        params     = params_raw.split() if params_raw else []

        if not algo:
            messagebox.showwarning("Missing Algorithm",
                                   "Please select an algorithm.")
            return
        if not fpath:
            messagebox.showwarning("Missing File",
                                   "Please choose an input file.")
            return
        p = Path(fpath)
        if not p.exists():
            messagebox.showerror("File Not Found",
                                 f"Input file not found:\n{fpath}")
            return
        try:
            poll_interval = float(self._run_poll_var.get())
            timeout       = int(self._run_timeout_var.get())
        except ValueError:
            messagebox.showerror("Invalid Option",
                                 "Poll interval and timeout must be numbers.")
            return

        self._cancel_flag.clear()
        self._run_btn.config(state="disabled", text="Running…")
        self._cancel_btn.config(state="normal")
        self._progress_bar.start(12)
        self._progress_var.set("Submitting…")
        self._run_log_write(
            f"Submitting: {algo}  params={params}", "info")

        host, port, key = self._get_conn()
        use_b64         = self._run_base64_var.get()
        no_cleanup      = self._run_noclean_var.get()

        def worker():
            try:
                text = p.read_text(encoding="utf-8")
                if use_b64:
                    input_data     = base64.b64encode(
                        text.encode()).decode("ascii")
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
                    err = _safe_json_error(resp)
                    self.after(0, self._job_error,
                               f"Submit failed [{resp.status_code}]: {err}")
                    return

                data   = resp.json()
                job_id = data.get("jobId")
                self.after(0, self._run_log_write,
                           f"Accepted: {job_id}", "ok")
                self.after(0, self._progress_var.set,
                           f"Polling: {job_id}")

                elapsed      = 0.0
                final_status = None
                poll_data: dict = {}

                while elapsed < timeout:
                    if self._cancel_flag.is_set():
                        self.after(0, self._run_log_write,
                                   "Cancelled by user.", "warn")
                        self.after(0, self._job_finish_cleanup)
                        return
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
                               f"Status: {final_status}  "
                               f"({elapsed:.0f}s elapsed)")
                    if final_status in POLL_STATES:
                        break

                if final_status not in POLL_STATES:
                    self.after(0, self._job_error,
                               f"Timeout after {timeout}s")
                    return

                # Fetch console BEFORE result and BEFORE delete
                console_text = ""
                try:
                    cr = api_get(host, port, key,
                                 f"/api/jobs/{job_id}/console")
                    if cr.status_code == 200:
                        console_text = cr.json().get("consoleOutput", "")
                except Exception:
                    pass

                if final_status in ("FAILED", "CANCELLED"):
                    err_msg = poll_data.get("errorMessage", "unknown error")
                    exec_ms = poll_data.get("executionTimeMs", "?")
                    if not no_cleanup:
                        try:
                            api_delete(host, port, key,
                                       f"/api/jobs/{job_id}")
                        except Exception:
                            pass
                    self.after(0, self._job_error_with_console,
                               f"{final_status} after {exec_ms}ms: "
                               f"{err_msg}", console_text)
                    return

                exec_ms = poll_data.get("executionTimeMs", "?")
                rr = api_get(host, port, key,
                             f"/api/jobs/{job_id}/result")
                if rr.status_code != 200:
                    self.after(0, self._job_error,
                               f"Result fetch failed: "
                               f"HTTP {rr.status_code}")
                    return
                output = rr.json().get("outputData", "")

                if not no_cleanup:
                    try:
                        api_delete(host, port, key, f"/api/jobs/{job_id}")
                    except Exception:
                        pass

                self.after(0, self._job_done,
                           job_id, output, console_text,
                           exec_ms, no_cleanup)

            except Exception as exc:
                self.after(0, self._job_error, str(exc))

        self._submit_thread = threading.Thread(target=worker, daemon=True)
        self._submit_thread.start()

    def _job_finish_cleanup(self):
        self._run_btn.config(state="normal",
                              text="▶  Submit Job  (Ctrl+Enter)")
        self._cancel_btn.config(state="disabled")
        self._progress_bar.stop()

    def _job_done(self, job_id: str, output: str, console: str,
                  exec_ms, no_cleanup: bool):
        self._job_finish_cleanup()
        self._progress_var.set(f"✓ Done in {exec_ms} ms")
        self._run_log_write(f"Job DONE in {exec_ms} ms.", "ok")
        if no_cleanup:
            self._run_log_write(f"Job kept: {job_id}", "warn")
        self._log_write(f"Job {job_id} completed in {exec_ms} ms.", "ok")
        self._result_jobid_var.set(job_id)
        self._show_result_and_console(output, console, exec_ms)
        self._notebook.select(self._tab_result)
        self._refresh_jobs()

    def _job_error(self, msg: str):
        self._job_finish_cleanup()
        self._progress_var.set("✗ Error")
        self._run_log_write(f"ERROR: {msg}", "err")
        self._log_write(f"Job error: {msg}", "err")
        messagebox.showerror("Job Error", msg)

    def _job_error_with_console(self, msg: str, console: str):
        self._job_finish_cleanup()
        self._progress_var.set("✗ Error")
        self._run_log_write(f"ERROR: {msg}", "err")
        self._log_write(f"Job error: {msg}", "err")
        self._show_result_and_console(
            "(job failed — no result output)", console, "?")
        self._notebook.select(self._tab_result)
        messagebox.showerror("Job Error", msg)

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def _refresh_jobs(self):
        if not self._connected:
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_get(host, port, key, "/api/jobs")
                if resp.status_code == 200:
                    self.after(0, self._populate_jobs, resp.json())
                else:
                    self.after(0, self._log_write,
                               f"Jobs list failed: HTTP {resp.status_code}",
                               "err")
            except Exception as e:
                self.after(0, self._log_write, f"Jobs error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _populate_jobs(self, data: dict):
        self._jobs = data.get("jobs", [])
        self._apply_jobs_filter()

    def _delete_selected_job(self):
        sel = self._jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a job to delete.")
            return
        job_id = self._jobs_tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete job\n{job_id}?"):
            return
        host, port, key = self._get_conn()

        def worker():
            try:
                resp = api_delete(host, port, key, f"/api/jobs/{job_id}")
                if resp.status_code == 200:
                    self.after(0, self._log_write,
                               f"Deleted job {job_id}.", "ok")
                    self.after(0, self._refresh_jobs)
                else:
                    self.after(0, self._log_write,
                               f"Delete failed: HTTP {resp.status_code}",
                               "err")
            except Exception as e:
                self.after(0, self._log_write,
                           f"Delete error: {e}", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _view_selected_result(self):
        sel = self._jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a job to view its result.")
            return
        job_id = self._jobs_tree.item(sel[0], "values")[0]
        self._result_jobid_var.set(job_id)
        self._fetch_result()
        self._notebook.select(self._tab_result)

    # ── Result + Console ──────────────────────────────────────────────────────

    def _fetch_result(self):
        if not self._require_connection():
            return
        job_id = self._result_jobid_var.get().strip()
        if not job_id:
            messagebox.showwarning("No Job ID",
                                   "Enter a Job ID to fetch results.")
            return
        host, port, key = self._get_conn()
        self._set_busy("⟳ fetching result")

        def worker():
            try:
                resp = api_get(host, port, key,
                               f"/api/jobs/{job_id}/result")
                if resp.status_code == 200:
                    data    = resp.json()
                    output  = data.get("outputData", "")
                    exec_ms = data.get("executionTimeMs", "?")
                else:
                    err    = _safe_json_error(resp)
                    output  = f"(error: {err})"
                    exec_ms = "?"
                    self.after(0, self._log_write,
                               f"Result fetch failed: {err}", "err")

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
                self.after(0, self._log_write,
                           f"Result error: {e}", "err")
            finally:
                self.after(0, self._set_busy, "")

        threading.Thread(target=worker, daemon=True).start()

    def _show_result_and_console(self, output: str,
                                  console: str, exec_ms):
        self._result_text.config(state="normal")
        self._result_text.delete("1.0", "end")
        self._result_text.insert("end", output)
        self._result_text.config(state="disabled")

        self._console_text.config(state="normal")
        self._console_text.delete("1.0", "end")
        self._console_text.insert(
            "end", console if console
            else "(no console output available)")
        self._console_text.config(state="disabled")

        r_lines = len(output.splitlines())
        c_lines = len(console.splitlines()) if console else 0
        self._res_lines_var.set(
            f"{r_lines} lines / {len(output):,} chars")
        self._con_lines_var.set(f"{c_lines} lines")
        self._result_info_var.set(
            f"Exec: {exec_ms} ms  |  "
            f"Result: {r_lines} lines / {len(output):,} chars  |  "
            f"Console: {c_lines} lines")
        self._log_write(
            f"Result loaded — {r_lines} lines, "
            f"{c_lines} console lines.", "ok")

    def _save_result(self):
        content = self._result_text.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Empty", "No result to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save result output", defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            Path(path).write_text(content, "utf-8")
            self._log_write(f"Result saved: {path}", "ok")
            messagebox.showinfo("Saved", f"Result saved to:\n{path}")

    def _save_console(self):
        content = self._console_text.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Empty", "No console output to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save console output", defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"),
                       ("All files", "*.*")])
        if path:
            Path(path).write_text(content, "utf-8")
            self._log_write(f"Console saved: {path}", "ok")
            messagebox.showinfo("Saved", f"Console saved to:\n{path}")


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = SPMFGui()
    app.mainloop()


if __name__ == "__main__":
    main()