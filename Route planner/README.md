# HU Pharma Map — Route Time Matrix (Step 3)

Computes **driving time from every warehouse to every client** using OSRM's
`table` (matrix) service, and writes an Excel matrix plus a nearest-warehouse
summary that feeds the coverage heat-map in a later phase.

## Output

`route_time_matrix.xlsx` — a single sheet:

- **Matrix (min)** — one row per client (`Client Nr`, `Client Name`), one column
  per warehouse; each value is the drive time in minutes from that warehouse to
  that client. This is the complete client×warehouse matrix.

There is intentionally **no precomputed "nearest warehouse" sheet**: the dashboard
computes each client's nearest *active* warehouse live from this matrix (warehouses
can be toggled off in the Logistics View), so a static nearest column would only go
stale. Every "nearest" question is just a lookup against the currently-active columns.

`run_log.txt` — timestamped log of the last run (progress + QA report).
`failures.csv` — only written if any client↔warehouse pair fails or is unroutable
(lists `client_nr, warehouse, reason`). Absent means everything routed.

## OSRM setup

Uses the **public OSRM demo server** (`router.project-osrm.org`), car profile,
global OpenStreetMap data (covers Hungary).

- **Batching:** the demo server caps how many coordinates a single `table`
  request may contain, so requests are chunked to **9 warehouses + 90 clients =
  99 coordinates** each (~58 requests for 5,191 clients). Each request returns a
  9×90 block of the matrix.
- **Tradeoffs:** it's rate-limited and best-effort (can be slow/flaky), so the
  script has retry + backoff and logs any failures. For the current volume this
  is fine — a full run takes under a minute.
- **Self-hosting:** not needed at this scale. Consider it only if the client list
  grows to tens of thousands, you re-run frequently, or you need guaranteed
  reliability/offline use. To switch: stand up a local OSRM (Hungary extract +
  `osrm-extract/partition/customize` + `osrm-routed --max-table-size <big>`),
  then set `OSRM_BASE` to your instance and raise `DEST_CHUNK`.

## How to (re)run

If the client/warehouse workbook changes, just re-run:

```bash
cd "Route planner"
python route_matrix.py
```

Requires Python 3 with `pandas`, `numpy`, `requests`, `openpyxl`.

- **Input:** `../Dashboard Input/Clients and warehouses.xlsx`
  (sheet `Clients`, sheet `Warehouses`).
- Sheet/column names are matched flexibly (case-insensitive) and **latitude vs.
  longitude is detected by value range**, so a swapped/mislabeled `Lat`/`Long`
  column can't corrupt the result.
- Warehouse columns become the matrix columns; duplicate warehouse names are
  disambiguated automatically.

### Tunables (top of `route_matrix.py`)

| Setting | Meaning |
|---------|---------|
| `OSRM_BASE` | OSRM server (swap for a self-hosted URL). |
| `DEST_CHUNK` | Clients per request (raise it on a self-hosted server). |
| `MAX_RETRIES`, `TIMEOUT`, `PAUSE` | Retry count, per-request timeout, polite delay. |
| `SUSPICIOUS_HIGH_MIN` | Threshold for flagging long drive times in the report. |

## Last run — results

- **Runtime:** ~55 s for 5,191 clients × 9 warehouses = **46,719 pairs**.
- **Quality:** 0 missing/null, 0 zero-minute, **0 unroutable clients**, 0 failed
  requests.
- **Nearest-warehouse drive time:** min 0.6 / median ~39 / max 146 min — every
  client is within ~2.5 h of its closest warehouse.
- 856 matrix cells exceed 300 min; these are legitimate corner-to-corner
  warehouse→client pairs (max 372 min) and are never a client's nearest
  warehouse — i.e. not data errors, just long hauls you wouldn't serve.
