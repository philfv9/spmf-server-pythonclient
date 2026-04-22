#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# spmf-client.py
# CLI client for SPMF-Server
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
spmf-client.py  —  Command-line client for SPMF-Server.

Usage:
    python spmf-client.py [global options] <command> [arguments]

Global options:
    --host <h>           Server hostname  (default: localhost)
    --port <p>           Server port      (default: 8585)
    --apikey <k>         X-API-Key header value
    --out <file>         Write output to file instead of stdout
    --poll-interval <s>  Seconds between status polls  (default: 1.0)
    --timeout <s>        Max seconds to wait for job   (default: 300)
    --base64             Base64-encode input file before sending
    --no-cleanup         Skip DELETE after run (keep job on server)
    --raw                Print raw JSON instead of formatted output

Commands:
    health               Check server health and queue stats
    info                 Show full server configuration
    list                 List all available algorithms by category
    describe <name>      Show parameters for one algorithm
    jobs                 List all jobs in the server registry
    run <name> <file> [params...]
                         Submit a job, wait, print result + console
    result <jobId>       Fetch result and console for a finished job
    console <jobId>      Fetch console output only
    delete <jobId>       Delete a job from the server
"""

import base64
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed.  Run:  pip install requests",
          file=sys.stderr)
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_HOST          = "localhost"
DEFAULT_PORT          = 8585
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_TIMEOUT       = 300
POLL_STATES           = ("DONE", "FAILED", "CANCELLED")

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _headers(apikey: str) -> dict:
    h = {"Content-Type": "application/json"}
    if apikey:
        h["X-API-Key"] = apikey
    return h


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def api_get(host, port, apikey, path, timeout=15):
    return requests.get(
        _base_url(host, port) + path,
        headers=_headers(apikey), timeout=timeout)


def api_post(host, port, apikey, path, payload, timeout=30):
    return requests.post(
        _base_url(host, port) + path,
        headers=_headers(apikey),
        data=json.dumps(payload), timeout=timeout)


def api_delete(host, port, apikey, path, timeout=15):
    return requests.delete(
        _base_url(host, port) + path,
        headers=_headers(apikey), timeout=timeout)


def _safe_json_error(resp) -> str:
    try:
        if "json" in resp.headers.get("content-type", ""):
            return resp.json().get("error", resp.text)
    except Exception:
        pass
    return resp.text


# ── Output helpers ─────────────────────────────────────────────────────────────

def _out(text: str, out_file: str = None):
    """Print to stdout or write to file."""
    if out_file:
        Path(out_file).write_text(text, "utf-8")
        print(f"Output written to: {out_file}")
    else:
        print(text)


def _err(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)


def _die(msg: str):
    _err(msg)
    sys.exit(1)


# ── Argument parser ────────────────────────────────────────────────────────────

def _parse_args(argv):
    """
    Hand-rolled parser so we have zero dependencies beyond 'requests'.
    Returns (opts dict, command str, command_args list).
    """
    opts = {
        "host":          DEFAULT_HOST,
        "port":          DEFAULT_PORT,
        "apikey":        "",
        "out":           None,
        "poll_interval": DEFAULT_POLL_INTERVAL,
        "timeout":       DEFAULT_TIMEOUT,
        "base64":        False,
        "no_cleanup":    False,
        "raw":           False,
    }

    args = list(argv)
    # Parse global options (everything before the first non-option token)
    while args:
        a = args[0]
        if a == "--host" and len(args) > 1:
            opts["host"] = args[1]; args = args[2:]
        elif a == "--port" and len(args) > 1:
            try:
                opts["port"] = int(args[1])
            except ValueError:
                _die(f"--port must be an integer, got: {args[1]}")
            args = args[2:]
        elif a == "--apikey" and len(args) > 1:
            opts["apikey"] = args[1]; args = args[2:]
        elif a == "--out" and len(args) > 1:
            opts["out"] = args[1]; args = args[2:]
        elif a == "--poll-interval" and len(args) > 1:
            try:
                opts["poll_interval"] = float(args[1])
            except ValueError:
                _die(f"--poll-interval must be a number, got: {args[1]}")
            args = args[2:]
        elif a == "--timeout" and len(args) > 1:
            try:
                opts["timeout"] = int(args[1])
            except ValueError:
                _die(f"--timeout must be an integer, got: {args[1]}")
            args = args[2:]
        elif a == "--base64":
            opts["base64"] = True; args = args[1:]
        elif a == "--no-cleanup":
            opts["no_cleanup"] = True; args = args[1:]
        elif a == "--raw":
            opts["raw"] = True; args = args[1:]
        elif a.startswith("--"):
            _die(f"Unknown global option: {a}")
        else:
            break   # first non-option → must be the command

    if not args:
        return opts, None, []

    command     = args[0]
    command_args = args[1:]
    return opts, command, command_args


# ── Formatters ─────────────────────────────────────────────────────────────────

def _fmt_health(data: dict) -> str:
    lines = [
        "═" * 44,
        "  Server Health",
        "═" * 44,
    ]
    for key, label in [
        ("status",               "Status              "),
        ("version",              "Version             "),
        ("spmfAlgorithmsLoaded", "Algorithms Loaded   "),
        ("uptimeSeconds",        "Uptime (s)          "),
        ("activeJobs",           "Active Jobs         "),
        ("queuedJobs",           "Queued Jobs         "),
        ("totalJobsInRegistry",  "Total in Registry   "),
    ]:
        lines.append(f"  {label}: {data.get(key, '—')}")
    lines.append("═" * 44)
    return "\n".join(lines)


def _fmt_info(data: dict) -> str:
    lines = [
        "═" * 44,
        "  Server Configuration",
        "═" * 44,
    ]
    for key, label in [
        ("version",        "Version          "),
        ("port",           "Port             "),
        ("host",           "Host             "),
        ("coreThreads",    "Core Threads     "),
        ("maxThreads",     "Max Threads      "),
        ("jobTtlMinutes",  "Job TTL (min)    "),
        ("maxQueueSize",   "Max Queue        "),
        ("workDir",        "Work Dir         "),
        ("maxInputSizeMb", "Max Input (MB)   "),
        ("apiKeyEnabled",  "API Key Enabled  "),
        ("logLevel",       "Log Level        "),
    ]:
        lines.append(f"  {label}: {data.get(key, '—')}")
    lines.append("═" * 44)
    return "\n".join(lines)


def _fmt_list(data: dict) -> str:
    algorithms = data.get("algorithms", [])
    # Group by category
    cats: dict[str, list] = {}
    for a in algorithms:
        cat  = a.get("algorithmCategory", "Uncategorized")
        name = a.get("name", "?")
        cats.setdefault(cat, []).append(name)

    lines = [
        "═" * 60,
        f"  Algorithms  ({data.get('count', len(algorithms))} total)",
        "═" * 60,
    ]
    for cat in sorted(cats):
        lines.append(f"\n  [{cat}]")
        for name in sorted(cats[cat]):
            lines.append(f"    • {name}")
    lines.append("")
    return "\n".join(lines)


def _fmt_describe(data: dict) -> str:
    params    = data.get("parameters", [])
    mandatory = data.get("numberOfMandatoryParameters", 0)
    in_t      = data.get("inputFileTypes",  [])
    out_t     = data.get("outputFileTypes", [])
    doc       = data.get("documentationURL", "")

    lines = [
        "═" * 60,
        f"  {data.get('name', '?')}",
        "═" * 60,
        f"  Category  : {data.get('algorithmCategory', '—')}",
        f"  Type      : {data.get('algorithmType', '—')}",
        f"  Author(s) : {data.get('implementationAuthorNames', '—')}",
        f"  Input     : {', '.join(in_t) if in_t else 'N/A'}",
        f"  Output    : {', '.join(out_t) if out_t else 'N/A'}",
    ]
    if doc:
        lines.append(f"  Docs      : {doc}")
    lines += [
        "",
        f"  Parameters  ({len(params)} total, {mandatory} mandatory)",
        "  " + "─" * 56,
    ]
    for i, p in enumerate(params, 1):
        req = "[optional]" if p.get("isOptional") else "[required]"
        lines += [
            f"  {i:2d}. {p.get('name','?')}  {req}",
            f"      type   : {p.get('parameterType','?')}",
            f"      example: {p.get('example','?')}",
            "",
        ]
    lines.append("═" * 60)
    return "\n".join(lines)


def _fmt_jobs(data: dict) -> str:
    jobs = data.get("jobs", [])
    lines = [
        "═" * 90,
        f"  Jobs  ({len(jobs)} total)",
        "═" * 90,
        f"  {'Job ID':<38}  {'Algorithm':<28}  {'Status':<10}  Exec(ms)",
        "  " + "─" * 86,
    ]
    for j in sorted(jobs,
                    key=lambda x: x.get("submittedAt", ""),
                    reverse=True):
        lines.append(
            f"  {j.get('jobId','?'):<38}  "
            f"{j.get('algorithmName','?'):<28}  "
            f"{j.get('status','?'):<10}  "
            f"{j.get('executionTimeMs','?')}")
    lines.append("═" * 90)
    return "\n".join(lines)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_health(opts, _args):
    try:
        resp = api_get(opts["host"], opts["port"], opts["apikey"],
                       "/api/health")
    except requests.exceptions.ConnectionRefusedError:
        _die(f"Connection refused at {opts['host']}:{opts['port']}")
    except requests.exceptions.Timeout:
        _die("Connection timed out.")
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = json.dumps(data, indent=2) if opts["raw"] else _fmt_health(data)
    _out(text, opts["out"])


def cmd_info(opts, _args):
    try:
        resp = api_get(opts["host"], opts["port"], opts["apikey"], "/api/info")
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = json.dumps(data, indent=2) if opts["raw"] else _fmt_info(data)
    _out(text, opts["out"])


def cmd_list(opts, _args):
    try:
        resp = api_get(opts["host"], opts["port"], opts["apikey"],
                       "/api/algorithms", timeout=30)
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = json.dumps(data, indent=2) if opts["raw"] else _fmt_list(data)
    _out(text, opts["out"])


def cmd_describe(opts, args):
    if not args:
        _die("Usage:  describe <algorithm-name>")
    name = args[0]
    try:
        encoded = requests.utils.quote(name, safe="")
        resp    = api_get(opts["host"], opts["port"], opts["apikey"],
                          f"/api/algorithms/{encoded}")
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = json.dumps(data, indent=2) if opts["raw"] else _fmt_describe(data)
    _out(text, opts["out"])


def cmd_jobs(opts, _args):
    try:
        resp = api_get(opts["host"], opts["port"], opts["apikey"], "/api/jobs")
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = json.dumps(data, indent=2) if opts["raw"] else _fmt_jobs(data)
    _out(text, opts["out"])


def cmd_run(opts, args):
    if len(args) < 2:
        _die("Usage:  run <algorithm-name> <input-file> [param1 param2 ...]")

    algo      = args[0]
    fpath     = args[1]
    params    = args[2:]

    p = Path(fpath)
    if not p.exists():
        _die(f"Input file not found: {fpath}")

    host          = opts["host"]
    port          = opts["port"]
    apikey        = opts["apikey"]
    poll_interval = opts["poll_interval"]
    timeout       = opts["timeout"]
    use_b64       = opts["base64"]
    no_cleanup    = opts["no_cleanup"]

    # ── 1. Read input ──────────────────────────────────────────────────────
    try:
        raw_text = p.read_text(encoding="utf-8")
    except Exception as e:
        _die(f"Cannot read input file: {e}")

    if use_b64:
        input_data     = base64.b64encode(raw_text.encode()).decode("ascii")
        input_encoding = "base64"
    else:
        input_data     = raw_text
        input_encoding = "plain"

    payload = {
        "algorithmName": algo,
        "parameters":    params,
        "inputData":     input_data,
        "inputEncoding": input_encoding,
    }

    # ── 2. POST /api/run ───────────────────────────────────────────────────
    print(f"Submitting job: {algo}  params={params}")
    try:
        resp = api_post(host, port, apikey, "/api/run", payload)
    except Exception as e:
        _die(str(e))

    if resp.status_code != 202:
        _die(f"Submit failed [{resp.status_code}]: {_safe_json_error(resp)}")

    job_id = resp.json().get("jobId")
    print(f"Job accepted: {job_id}")

    # ── 3. Poll ────────────────────────────────────────────────────────────
    elapsed      = 0.0
    final_status = None
    poll_data    = {}

    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            pr = api_get(host, port, apikey, f"/api/jobs/{job_id}")
        except Exception as e:
            _die(f"Poll error: {e}")

        if pr.status_code != 200:
            _die(f"Poll error: HTTP {pr.status_code}")

        poll_data    = pr.json()
        final_status = poll_data.get("status")
        print(f"  Status: {final_status}  ({elapsed:.0f}s elapsed)",
              end="\r", flush=True)

        if final_status in POLL_STATES:
            break

    print()   # newline after \r progress

    if final_status not in POLL_STATES:
        _die(f"Timeout after {timeout}s — last status: {final_status}")

    # ── 4. Fetch console FIRST ─────────────────────────────────────────────
    console_text = ""
    try:
        cr = api_get(host, port, apikey, f"/api/jobs/{job_id}/console")
        if cr.status_code == 200:
            console_text = cr.json().get("consoleOutput", "")
    except Exception:
        pass

    # ── 5. Handle FAILED / CANCELLED ──────────────────────────────────────
    if final_status in ("FAILED", "CANCELLED"):
        err_msg = poll_data.get("errorMessage", "unknown error")
        exec_ms = poll_data.get("executionTimeMs", "?")
        if not no_cleanup:
            try:
                api_delete(host, port, apikey, f"/api/jobs/{job_id}")
            except Exception:
                pass
        print("\n── Console Output ──────────────────────────────────")
        print(console_text if console_text else "(no console output)")
        _die(f"Job {final_status} after {exec_ms}ms: {err_msg}")

    # ── 6. Fetch result ────────────────────────────────────────────────────
    exec_ms = poll_data.get("executionTimeMs", "?")
    try:
        rr = api_get(host, port, apikey, f"/api/jobs/{job_id}/result")
    except Exception as e:
        _die(f"Result fetch error: {e}")

    if rr.status_code != 200:
        _die(f"Result fetch failed: HTTP {rr.status_code}")

    output = rr.json().get("outputData", "")

    # ── 7. Clean up ────────────────────────────────────────────────────────
    if not no_cleanup:
        try:
            api_delete(host, port, apikey, f"/api/jobs/{job_id}")
        except Exception:
            pass
    else:
        print(f"Job kept on server: {job_id}")

    # ── 8. Print result + console ──────────────────────────────────────────
    result_block = (
        f"Job DONE in {exec_ms} ms\n"
        f"{'═' * 60}\n"
        f"Result Output\n"
        f"{'═' * 60}\n"
        f"{output}\n"
        f"{'═' * 60}\n"
        f"Console Output\n"
        f"{'═' * 60}\n"
        f"{console_text if console_text else '(no console output)'}\n"
    )
    _out(result_block, opts["out"])


def cmd_result(opts, args):
    if not args:
        _die("Usage:  result <jobId>")
    job_id = args[0]
    host, port, apikey = opts["host"], opts["port"], opts["apikey"]

    output  = ""
    exec_ms = "?"

    try:
        resp = api_get(host, port, apikey, f"/api/jobs/{job_id}/result")
        if resp.status_code == 200:
            data    = resp.json()
            output  = data.get("outputData", "")
            exec_ms = data.get("executionTimeMs", "?")
        else:
            _err(f"Result fetch failed: HTTP {resp.status_code} "
                 f"{_safe_json_error(resp)}")
    except Exception as e:
        _die(str(e))

    console_text = ""
    try:
        cr = api_get(host, port, apikey, f"/api/jobs/{job_id}/console")
        if cr.status_code == 200:
            console_text = cr.json().get("consoleOutput", "")
    except Exception:
        pass

    if opts["raw"]:
        _out(json.dumps({"outputData": output,
                         "consoleOutput": console_text}, indent=2),
             opts["out"])
        return

    block = (
        f"Job: {job_id}  |  Exec: {exec_ms} ms\n"
        f"{'═' * 60}\n"
        f"Result Output\n"
        f"{'═' * 60}\n"
        f"{output}\n"
        f"{'═' * 60}\n"
        f"Console Output\n"
        f"{'═' * 60}\n"
        f"{console_text if console_text else '(no console output)'}\n"
    )
    _out(block, opts["out"])


def cmd_console(opts, args):
    if not args:
        _die("Usage:  console <jobId>")
    job_id = args[0]

    try:
        resp = api_get(opts["host"], opts["port"], opts["apikey"],
                       f"/api/jobs/{job_id}/console")
    except Exception as e:
        _die(str(e))

    if resp.status_code != 200:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")

    data = resp.json()
    text = (json.dumps(data, indent=2) if opts["raw"]
            else data.get("consoleOutput", "(no console output)"))
    _out(text, opts["out"])


def cmd_delete(opts, args):
    if not args:
        _die("Usage:  delete <jobId>")
    job_id = args[0]

    try:
        resp = api_delete(opts["host"], opts["port"], opts["apikey"],
                          f"/api/jobs/{job_id}")
    except Exception as e:
        _die(str(e))

    if resp.status_code == 200:
        print(f"Deleted job: {job_id}")
    else:
        _die(f"HTTP {resp.status_code}: {_safe_json_error(resp)}")


# ── Help ───────────────────────────────────────────────────────────────────────

def _print_help():
    print(__doc__)


# ── Dispatch ───────────────────────────────────────────────────────────────────

COMMANDS = {
    "health":   cmd_health,
    "info":     cmd_info,
    "list":     cmd_list,
    "describe": cmd_describe,
    "jobs":     cmd_jobs,
    "run":      cmd_run,
    "result":   cmd_result,
    "console":  cmd_console,
    "delete":   cmd_delete,
    "help":     lambda o, a: _print_help(),
    "--help":   lambda o, a: _print_help(),
    "-h":       lambda o, a: _print_help(),
}


def main():
    opts, command, command_args = _parse_args(sys.argv[1:])

    if command is None:
        _print_help()
        sys.exit(0)

    handler = COMMANDS.get(command)
    if handler is None:
        _err(f"Unknown command: '{command}'")
        _print_help()
        sys.exit(1)

    handler(opts, command_args)


if __name__ == "__main__":
    main()