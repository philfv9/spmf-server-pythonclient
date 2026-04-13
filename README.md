[![License](https://img.shields.io/github/license/philfv9/spmf-server-pythonclient.svg)](https://github.com/philfv9/spmf-server-pythonclient/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/philfv9/spmf-server-pythonclient.svg)](https://github.com/philfv9/spmf-server-pythonclient/stargazers)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python-yellow)]()
[![Last Commit](https://img.shields.io/github/last-commit/philfv9/spmf-server-webclient)](https://github.com/philfv9/spmf-server-webclient/commits/main)
[![SPMF](https://img.shields.io/badge/SPMF-300%2B%20Algorithms-blue)](http://www.philippe-fournier-viger.com/spmf/)

# The CLI and GUI Python Clients for the SPMF Server

This repository provides a **command-line client (CLI)** (`spmf-client.py`) and **graphical desktop client (GUI)** (`spmf-gui.py` written in Python for sending pattern mining and data mining jobs to the
[SPMF-Server](https://github.com/philfv9/spmf-server), which provides a REST API wrapper for the popular [SPMF](https://www.philippe-fournier-viger.com/spmf/) data-mining library.

---

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [CLI Client — spmf-client.py](#cli-client--spmf-clientpy)
  - [Global Options](#global-options)
  - [Commands](#commands)
  - [CLI Examples](#cli-examples)
  - [What run does automatically](#what-run-does-automatically)
- [GUI Client — spmf-gui.py](#gui-client--spmf-guipy)
  - [Launching the GUI](#launching-the-gui)
  - [GUI Features](#gui-features)
  - [GUI Tabs](#gui-tabs)
- [Algorithm Parameters](#algorithm-parameters)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

This repository provides two Python clients for
[SPMF-Server](https://github.com/philfv9/spmf-server):

<div align="center">
  <img src="/images/pythonclient.png" alt="SPMF server" width="600">
</div>

Both clients handle the full job lifecycle automatically:
submit → poll → fetch console → fetch result → cleanup.

To try these clients, you will first need to download and install the [SPMF-Server](https://github.com/philfv9/spmf-server).

The clients depends on: 

- Python 3.8 or later
- `requests` library
- `tkinter` — for the GUI client only (included with the standard Python installer)

---

## Installation

```bash
pip install requests
```

Clone or download this repository and run from the
folder containing the scripts.

```bash
git clone https://github.com/philfv9/spmf-server-pythonclient.git
cdspmf-server-pythonclient
pip install requests
```

---

## CLI Client — spmf-client.py

A single-file CLI that covers every spmf-server endpoint.

```
python spmf-client.py [global options] <subcommand> [subcommand arguments]
```

### Global Options

Global options **must** be placed **before** the subcommand name.

| Option | Default | Description |
|---|---|---|
| `--host` | `localhost` | Server hostname or IP |
| `--port` | `8585` | Server port |
| `--apikey` | *(none)* | Value for `X-API-Key` header |
| `--out <file>` | *(stdout)* | Save output text to a file instead of printing |
| `--poll-interval` | `1.0` | Seconds between status polls |
| `--timeout` | `300` | Max seconds to wait for job completion |
| `--base64` | off | Encode input file as base64 before sending |
| `--no-cleanup` | off | Skip `DELETE` after `run` (keep job on server) |
| `--raw` | off | Print raw JSON instead of formatted output |

---

### Commands

| Command | Description |
|---|---|
| `health` | Check server health and queue stats |
| `info` | Show full server configuration |
| `list` | List all available algorithms by category |
| `describe <name>` | Show parameters for one algorithm |
| `jobs` | List all jobs in the server registry |
| `run <name> <file> [params…]` | Submit a job, wait, print result and console output |
| `result <jobId>` | Fetch result and console output for a finished job |
| `console <jobId>` | Fetch console output only |
| `delete <jobId>` | Delete a job from the server |

---

### CLI Examples

#### Server status

```bash
python spmf-client.py health
python spmf-client.py info
python spmf-client.py --raw health
```

#### Discover algorithms

```bash
# List all algorithms grouped by category
python spmf-client.py list

# Save the full list to a file
python spmf-client.py --out algorithms.txt list

# Describe one algorithm — always do this before running
python spmf-client.py describe Apriori
python spmf-client.py describe FPGrowth_itemsets
```

#### Run algorithms

```bash
# Apriori — 1 mandatory parameter (minsup as Double)
python spmf-client.py run Apriori input.txt 0.5

# Apriori — with optional max-pattern-length (must be Integer)
python spmf-client.py run Apriori input.txt 0.5 3

# FP-Growth
python spmf-client.py run FPGrowth_itemsets input.txt 0.4

# Save result output to file
python spmf-client.py --out results.txt run Apriori input.txt 0.5

# Base64-encode the input before sending
python spmf-client.py --base64 run Apriori input.txt 0.5

# Keep job on server after completion (skip auto-delete)
python spmf-client.py --no-cleanup run Apriori input.txt 0.5
```

#### Connect to a remote server

```bash
python spmf-client.py --host 192.168.1.50 --port 9090 health
python spmf-client.py --host 192.168.1.50 --port 9090 run Apriori input.txt 0.5
```

#### Manage jobs manually

```bash
# List all jobs
python spmf-client.py jobs

# Fetch result + console for an existing job
python spmf-client.py result 5d0b27f6-f330-4cfb-9803-53f74c7bfa6a

# Fetch console output only
python spmf-client.py console 5d0b27f6-f330-4cfb-9803-53f74c7bfa6a

# Delete a job
python spmf-client.py delete 5d0b27f6-f330-4cfb-9803-53f74c7bfa6a
```

---

### What `run` does automatically

The `run` command manages the full job lifecycle end-to-end:

```
1. Read input file from disk (optionally base64-encode it)
2. POST /api/run              ->  receive jobId  (202 Accepted)
3. Poll GET /api/jobs/{id}       until status is DONE or FAILED
4. GET /api/jobs/{id}/console    fetch console output FIRST
5. GET /api/jobs/{id}/result     then fetch result output
6. Print result output
7. Print console output
8. DELETE /api/jobs/{id}         clean up (unless --no-cleanup)
```

> **Why console before result?**
> Deleting a job removes its working directory from disk.
> Console output is fetched first so it is never lost,
> even if a later step fails.

---

## GUI Client — spmf-gui.py

The GUI client for the SPMF server is modern dark-themed graphical desktop application providing the same
capabilities as the CLI — without the command line.

To run the GUI client:

```bash
python spmf-gui.py
```

The interface of the GUI client is organized around five views.

The **Dashboard** provides an overview of the server’s current status,  server configuration, and a timestamped activity log showing every action taken during the session.

<div align="center">
  <img src="/images/dashboard.png" alt="Dashboard view" width="800">
</div>

The **Algorithms** view enables users to explore the full list of available algorithms.  Click any algorithm to see its full description: category, author, input/output file types, and every parameter
with its type and an example value. Click **"Use in Run Job"** to load the selected algorithm directly into the Run Job tab.

<div align="center">
  <img src="/images/algorithms.png" alt="Algorithms view" width="800">
</div>

The **Run Job** interface guides users through the process of executing a task. Users can selelect algorithm from a searchable dropdown, browse for an input data file,  enter space-separated parameters  (the **Parameter Guide** panel on the right shows exactly what is expected). There are also options of using base64 encoding and keeping the job after completion, and adjusting the poll interval and timeout. Click **Submit Job** to submit a job, then the Result tab
  opens automatically on completion.

<div align="center">
  <img src="/images/runjob.png" alt="Run job view" width="800">
</div>

The **Jobs** view displays a live list of all submitted jobs. It allows users to track the status of each job and delete jobs when necessary. Double-click any row to load its result and console output.
Delete individual jobs from this tab.

<div align="center">
  <img src="/images/jobs.png" alt="Jobs view" width="800">
</div>

Finally, the **Result** view allows to view the results of a completed job.  The left panel displays he algorithm result output (the patterns, rules, or clusters found) while the right panel shows the console output (stdout/stderr from the SPMF Java process. Both panels support horizontal scrolling. Either panel can be saved to a file
independently using the toolbar buttons.

<div align="center">
  <img src="/images/results.png" alt="Result view" width="800">
</div>

## Algorithm Parameters

> Getting parameters wrong is the most common source of `400 Bad Request` errors.

### Rules

- **Always** run `describe <algorithmName>` (CLI) or check the Algorithms tab (GUI)
  before running an algorithm for the first time.
- Pass parameters in the **exact order** shown by `describe`.
- Pass **only mandatory parameters** unless you specifically want the optional ones.
- **Integer parameters must be integers** — passing `3.0` for an `Integer` causes a 400 error.
- **Double parameters must be decimals** — use `0.5`, not `1/2`.

### Common mistakes

| Mistake | Error | Fix |
|---|---|---|
| Passing `0.6` for an `Integer` parameter | `400 Bad Request` | Use `1`, `2`, `3`, … |
| Algorithm name `FPGrowth` | `404 Not Found` | Correct name is `FPGrowth_itemsets` |
| Placing `--base64` after the subcommand | Flag ignored or parse error | All `--flags` must come **before** the subcommand |
| Not deleting completed jobs | Server registry fills up | Auto-cleanup is on by default; or call `delete` manually |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR: Cannot connect tospmf-server` | Server not running | Startspmf-server first |
| `ERROR [400]` on `run` | Wrong parameter type or count | Run `describe <name>` to check types |
| `ERROR [404]` on algorithm | Misspelled algorithm name | Run `list` to find the exact name |
| `ERROR [403]` on all requests | API key required or wrong | Pass `--apikey <value>` matching the server config |
| `UnicodeEncodeError` on Windows | Terminal codepage not UTF-8 | Run `chcp 65001` or set `PYTHONIOENCODING=utf-8` |
| Console output is empty | Fetched after job was deleted | Both clients always fetch console before result and before delete |
| Job stuck in `PENDING` | Server at max concurrent jobs | Wait, or ask admin to increase `spmf.max-concurrent-jobs` |
| Job `FAILED` | Bad input data or wrong params | Check console output — it contains the Java stack trace |
| GUI won't start — `tkinter` missing | Python from Microsoft Store | Reinstall from [python.org](https://www.python.org/downloads/) |
| GUI connection dot stays red | Server not reachable | Verify host/port and confirm the server is running |

---

## License and copyright

This software and this webpage is copyright © Philippe Fournier-Viger and contributors.

The software is distributed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). 

**Related links:**

- SPMF Library source code: [https://github.com/philfv9/spmf](https://github.com/philfv9/spmf)
-spmf-server: [https://github.com/philfv9/spmf-server](https://github.com/philfv9/spmf-server)
- Official SPMF website: [http://philippe-fournier-viger.com/spmf/](http://philippe-fournier-viger.com/spmf/)
