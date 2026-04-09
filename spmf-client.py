#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# spmf-client.py
# Command-line client for SPMF-Server
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
spmf-client.py
==============
Command-line client for SPMF-Server.

Usage:
  python spmf-client.py [options] health
  python spmf-client.py [options] info
  python spmf-client.py [options] list
  python spmf-client.py [options] jobs
  python spmf-client.py [options] describe <algorithmName>
  python spmf-client.py [options] run      <algorithmName> <inputFile> [param ...]
  python spmf-client.py [options] delete   <jobId>
  python spmf-client.py [options] result   <jobId>
  python spmf-client.py [options] console  <jobId>

Global options (place BEFORE the subcommand):
  --host          Server host          (default: localhost)
  --port          Server port          (default: 8585)
  --apikey        X-API-Key header     (default: none)
  --out           Save output to file  (default: print to stdout)
  --poll-interval Seconds between polls when waiting for job (default: 1)
  --timeout       Max seconds to wait  (default: 300)
  --base64        Encode input as base64 before sending
  --no-cleanup    Skip DELETE after run (keep job on server)
  --raw           Print raw JSON responses (no formatting)

Requirements:
  pip install requests
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not installed.  Run:  pip install requests",
          file=sys.stderr)
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────

VERSION       = "1.0.0"
DEFAULT_HOST  = "localhost"
DEFAULT_PORT  = 8585

# ── Helpers ────────────────────────────────────────────────────────────────────

def build_url(args, path: str) -> str:
    return f"http://{args.host}:{args.port}{path}"


def build_headers(args) -> dict:
    headers = {"Content-Type": "application/json"}
    if args.apikey:
        headers["X-API-Key"] = args.apikey
    return headers


def http_get(args, path: str) -> requests.Response:
    url = build_url(args, path)
    try:
        resp = requests.get(url, headers=build_headers(args), timeout=15)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to SPMF-Server at {args.host}:{args.port}",
              file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print(f"ERROR: Request timed out connecting to {url}", file=sys.stderr)
        sys.exit(1)
    return resp


def http_post(args, path: str, payload: dict) -> requests.Response:
    url = build_url(args, path)
    try:
        resp = requests.post(
            url,
            headers=build_headers(args),
            data=json.dumps(payload),
            timeout=30,
        )
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to SPMF-Server at {args.host}:{args.port}",
              file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print(f"ERROR: Request timed out connecting to {url}", file=sys.stderr)
        sys.exit(1)
    return resp


def http_delete(args, path: str) -> requests.Response:
    url = build_url(args, path)
    try:
        resp = requests.delete(url, headers=build_headers(args), timeout=15)
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to SPMF-Server at {args.host}:{args.port}",
              file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print(f"ERROR: Request timed out connecting to {url}", file=sys.stderr)
        sys.exit(1)
    return resp


def check_status(resp: requests.Response, expected: int = 200) -> dict:
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    if resp.status_code != expected:
        err = data.get("error", resp.text) if isinstance(data, dict) else resp.text
        print(f"ERROR [{resp.status_code}]: {err}", file=sys.stderr)
        sys.exit(1)
    return data


def print_output(args, text: str):
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Output saved to: {args.out}")
    else:
        print(text)


def pretty(data) -> str:
    return json.dumps(data, indent=2)


def fetch_console_text(args, job_id: str) -> str:
    """
    Fetch console output for a job.
    Returns the console text, or an empty string if not available.
    Never exits -- always returns gracefully so callers can continue.
    """
    resp = http_get(args, f"/api/jobs/{job_id}/console")
    if resp.status_code == 200:
        try:
            return resp.json().get("consoleOutput", "")
        except Exception:
            return ""
    # 410 = not ready, 404 = gone -- just return empty
    return ""


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_health(args):
    resp = http_get(args, "/api/health")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    status = data.get("status", "?")
    icon   = "[OK]" if status == "UP" else "[!!]"
    print(f"{icon} Server status   : {status}")
    print(f"  Version          : {data.get('version','?')}")
    print(f"  SPMF algorithms  : {data.get('spmfAlgorithmsLoaded','?')}")
    print(f"  Uptime (sec)     : {data.get('uptimeSeconds','?')}")
    print(f"  Active jobs      : {data.get('activeJobs','?')}")
    print(f"  Queued jobs      : {data.get('queuedJobs','?')}")
    print(f"  Jobs in registry : {data.get('totalJobsInRegistry','?')}")


def cmd_info(args):
    resp = http_get(args, "/api/info")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    print("Server configuration:")
    for k, v in data.items():
        print(f"  {k:<22}: {v}")


def cmd_list(args):
    resp = http_get(args, "/api/algorithms")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    algorithms = data.get("algorithms", [])
    print(f"Total algorithms: {data.get('count', len(algorithms))}")
    print()
    categories = {}
    for alg in algorithms:
        cat = alg.get("algorithmCategory", "UNKNOWN")
        categories.setdefault(cat, []).append(alg.get("name", "?"))
    for cat, names in sorted(categories.items()):
        print(f"  [{cat}]")
        for name in sorted(names):
            print(f"    - {name}")
        print()


def cmd_describe(args):
    name = args.algorithm_name
    resp = http_get(args, f"/api/algorithms/{requests.utils.quote(name, safe='')}")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    print(f"Algorithm       : {data.get('name')}")
    print(f"Category        : {data.get('algorithmCategory')}")
    print(f"Author(s)       : {data.get('implementationAuthorNames')}")
    print(f"Type            : {data.get('algorithmType')}")
    print(f"Documentation   : {data.get('documentationURL')}")
    print()
    in_types = data.get("inputFileTypes", [])
    print(f"Input types     : {', '.join(in_types) if in_types else 'N/A'}")
    out_types = data.get("outputFileTypes", [])
    print(f"Output types    : {', '.join(out_types) if out_types else 'N/A'}")
    print()
    params    = data.get("parameters", [])
    mandatory = data.get("numberOfMandatoryParameters", 0)
    print(f"Parameters      : {len(params) if params else 0} total, {mandatory} mandatory")
    if params:
        for i, p in enumerate(params):
            opt_tag = " [optional]" if p.get("isOptional") else ""
            print(f"  [{i+1}] {p.get('name')}{opt_tag}")
            print(f"       type   : {p.get('parameterType','?')}")
            print(f"       example: {p.get('example','?')}")


def cmd_jobs(args):
    resp = http_get(args, "/api/jobs")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    jobs = data.get("jobs", [])
    print(f"Total jobs in registry: {data.get('count', len(jobs))}")
    if not jobs:
        print("  (no jobs)")
        return
    print()
    fmt = "  {:<38} {:<30} {:<10} {}"
    print(fmt.format("Job ID", "Algorithm", "Status", "Submitted"))
    print("  " + "-" * 100)
    for j in jobs:
        print(fmt.format(
            j.get("jobId", "?"),
            j.get("algorithmName", "?")[:28],
            j.get("status", "?"),
            j.get("submittedAt", "?"),
        ))


def cmd_delete(args):
    job_id = args.job_id
    resp   = http_delete(args, f"/api/jobs/{job_id}")
    data   = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return
    print(f"Job {job_id} deleted successfully.")


def cmd_result(args):
    """
    Fetch result AND console output for a finished job.
    Both are shown together -- result first, then console.
    """
    job_id = args.job_id

    # -- Fetch result -------------------------------------------------------
    resp = http_get(args, f"/api/jobs/{job_id}/result")
    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        # Also fetch and print console as raw JSON
        c_resp = http_get(args, f"/api/jobs/{job_id}/console")
        if c_resp.status_code == 200:
            print("\n-- Console Output (raw) --")
            print(pretty(c_resp.json()))
        return

    output  = data.get("outputData", "")
    exec_ms = data.get("executionTimeMs", "?")

    print(f"Result for job {job_id} (execution: {exec_ms} ms):")
    print("=" * 60)
    print_output(args, output)
    print("=" * 60)

    # -- Fetch console ------------------------------------------------------
    console_text = fetch_console_text(args, job_id)
    if console_text:
        print()
        print("Console output:")
        print("-" * 60)
        print(console_text)
        print("-" * 60)
    else:
        print("\n(No console output available)")


def cmd_console(args):
    """GET /api/jobs/{id}/console -- fetch algorithm console output only."""
    job_id = args.job_id
    resp   = http_get(args, f"/api/jobs/{job_id}/console")

    if resp.status_code == 410:
        data = resp.json()
        print(f"Console not yet available: {data.get('error')}", file=sys.stderr)
        sys.exit(1)

    data = check_status(resp, 200)
    if args.raw:
        print(pretty(data))
        return

    output = data.get("consoleOutput", "")
    lines  = data.get("lines", 0)
    status = data.get("status", "?")

    print("=" * 59)
    print(f"Console Output -- Job {job_id}")
    print(f"Status: {status}  |  Lines: {lines}")
    print("=" * 59)
    print_output(args, output)
    print("=" * 59)


def cmd_run(args):
    algo_name  = args.algorithm_name
    input_file = args.input_file
    params     = args.params or []

    # -- 1. Read input file -------------------------------------------------
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    input_text = input_path.read_text(encoding="utf-8")

    if args.base64:
        input_data     = base64.b64encode(input_text.encode("utf-8")).decode("ascii")
        input_encoding = "base64"
    else:
        input_data     = input_text
        input_encoding = "plain"

    # -- 2. Submit job ------------------------------------------------------
    payload = {
        "algorithmName": algo_name,
        "parameters":    params,
        "inputData":     input_data,
        "inputEncoding": input_encoding,
    }

    print(f"Submitting job: algorithm={algo_name}, params={params}")
    resp = http_post(args, "/api/run", payload)
    data = check_status(resp, 202)

    job_id = data.get("jobId")
    if not job_id:
        print("ERROR: Server did not return a jobId.", file=sys.stderr)
        sys.exit(1)

    print(f"Job accepted  : {job_id}")
    print(f"Status        : {data.get('status')}")

    # -- 3. Poll for completion ---------------------------------------------
    print(f"Waiting for result", end="", flush=True)
    elapsed       = 0
    poll_interval = args.poll_interval
    timeout       = args.timeout
    final_status  = None
    poll_data     = {}

    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        print(".", end="", flush=True)

        poll_resp = http_get(args, f"/api/jobs/{job_id}")
        if poll_resp.status_code != 200:
            print()
            print(f"ERROR: Unexpected status {poll_resp.status_code} while polling.",
                  file=sys.stderr)
            sys.exit(1)

        poll_data    = poll_resp.json()
        final_status = poll_data.get("status")

        if final_status in ("DONE", "FAILED"):
            break

    print()

    # -- 4. Handle timeout --------------------------------------------------
    if final_status not in ("DONE", "FAILED"):
        print(f"ERROR: Timeout after {timeout}s waiting for job {job_id}",
              file=sys.stderr)
        sys.exit(2)

    # -- 5. Fetch console FIRST, before anything else ----------------------
    print("Fetching console output...")
    console_text = fetch_console_text(args, job_id)

    # -- 6. Handle failure --------------------------------------------------
    if final_status == "FAILED":
        err_msg = poll_data.get("errorMessage", "unknown error")
        exec_ms = poll_data.get("executionTimeMs", "?")
        print(f"ERROR: Job FAILED after {exec_ms} ms: {err_msg}", file=sys.stderr)

        if console_text:
            print()
            print("Console output (may show the cause of failure):")
            print("-" * 60)
            print(console_text)
            print("-" * 60)

        if not args.no_cleanup:
            http_delete(args, f"/api/jobs/{job_id}")
        sys.exit(1)

    # -- 7. Fetch result ----------------------------------------------------
    exec_ms = poll_data.get("executionTimeMs", "?")
    print(f"Job DONE in {exec_ms} ms. Fetching result...")

    result_resp = http_get(args, f"/api/jobs/{job_id}/result")
    result_data = check_status(result_resp, 200)
    output_text = result_data.get("outputData", "")

    # -- 8. Print result output ---------------------------------------------
    print()
    print("Result output:")
    print("=" * 60)
    print_output(args, output_text)
    print("=" * 60)
    print(f"Lines in output : {len(output_text.splitlines())}")
    print(f"Chars in output : {len(output_text)}")

    # -- 9. Print console output --------------------------------------------
    print()
    print("Console output:")
    print("-" * 60)
    if console_text:
        print(console_text)
    else:
        print("(no console output captured)")
    print("-" * 60)

    # -- 10. Cleanup LAST -- only after both outputs are secured -----------
    if not args.no_cleanup:
        del_resp = http_delete(args, f"/api/jobs/{job_id}")
        if del_resp.status_code == 200:
            print(f"Job {job_id} cleaned up from server.")
        else:
            print(f"Warning: cleanup of job {job_id} returned "
                  f"{del_resp.status_code}", file=sys.stderr)


# ── Argument Parser ────────────────────────────────────────────────────────────

def make_parser() -> argparse.ArgumentParser:
    global_parser = argparse.ArgumentParser(add_help=False)
    g = global_parser.add_argument_group("global options")
    g.add_argument("--host",          default=DEFAULT_HOST, help="Server host (default: localhost)")
    g.add_argument("--port",          default=DEFAULT_PORT, type=int, help="Server port (default: 8585)")
    g.add_argument("--apikey",        default="",           help="X-API-Key header value")
    g.add_argument("--out",           default="",           help="Save output to file (default: stdout)")
    g.add_argument("--poll-interval", default=1.0,          type=float, dest="poll_interval",
                   help="Seconds between status polls (default: 1)")
    g.add_argument("--timeout",       default=300,          type=int,
                   help="Max seconds to wait for job completion (default: 300)")
    g.add_argument("--base64",        action="store_true",
                   help="Encode input file as base64 before sending")
    g.add_argument("--no-cleanup",    action="store_true",  dest="no_cleanup",
                   help="Do not DELETE job after run")
    g.add_argument("--raw",           action="store_true",
                   help="Print raw JSON responses instead of formatted output")

    parser = argparse.ArgumentParser(
        prog="spmf-client",
        description="Command-line client for SPMF-Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[global_parser],
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    sub.add_parser("health",
                   help="Check server health",
                   parents=[global_parser])

    sub.add_parser("info",
                   help="Show server configuration",
                   parents=[global_parser])

    sub.add_parser("list",
                   help="List all available algorithms",
                   parents=[global_parser])

    sub.add_parser("jobs",
                   help="List all jobs currently on the server",
                   parents=[global_parser])

    p_desc = sub.add_parser("describe",
                             help="Describe a single algorithm",
                             parents=[global_parser])
    p_desc.add_argument("algorithm_name", help="Exact algorithm name")

    p_run = sub.add_parser("run",
                            help="Run an algorithm",
                            parents=[global_parser])
    p_run.add_argument("algorithm_name", help="Exact algorithm name")
    p_run.add_argument("input_file",     help="Path to the input data file")
    p_run.add_argument("params",         nargs="*",
                       help="Algorithm parameters in order (e.g. 0.4 0.8)")

    p_res = sub.add_parser("result",
                            help="Fetch result AND console output of a finished job",
                            parents=[global_parser])
    p_res.add_argument("job_id", help="Job UUID")

    p_con = sub.add_parser("console",
                            help="Fetch console output only of a job",
                            parents=[global_parser])
    p_con.add_argument("job_id", help="Job UUID")

    p_del = sub.add_parser("delete",
                            help="Delete a job from the server",
                            parents=[global_parser])
    p_del.add_argument("job_id", help="Job UUID")

    return parser


# ── Entry Point ────────────────────────────────────────────────────────────────

COMMANDS = {
    "health":   cmd_health,
    "info":     cmd_info,
    "list":     cmd_list,
    "jobs":     cmd_jobs,
    "describe": cmd_describe,
    "run":      cmd_run,
    "result":   cmd_result,
    "console":  cmd_console,
    "delete":   cmd_delete,
}


def main():
    parser = make_parser()
    args   = parser.parse_args()
    args.out = args.out.strip() if args.out else None

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()