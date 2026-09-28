"""
Step 3 - Warehouse -> Client drive-time matrix via OSRM.

Reads the client/warehouse workbook, calls the OSRM `table` (matrix) service to
get driving durations from every warehouse to every client, and writes an Excel
file with the full matrix plus a "nearest warehouse" summary.

OSRM setup: PUBLIC demo server (router.project-osrm.org), car profile.
  - Small per-request table size, so requests are chunked (9 sources + N dests).
  - Rate-limited / best-effort reliability -> retry + backoff + failure logging.
Switch OSRM_BASE to a self-hosted instance (and raise DEST_CHUNK) for large volumes.

Run:  python route_matrix.py
"""
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# --------------------------------------------------------------------- config
ROOT = Path(__file__).resolve().parent
INPUT = ROOT.parent / "Dashboard Input" / "Clients and warehouses.xlsx"
OUT_XLSX = ROOT / "route_time_matrix.xlsx"
FAIL_LOG = ROOT / "failures.csv"
RUN_LOG = ROOT / "run_log.txt"

OSRM_BASE = "https://router.project-osrm.org"
DEST_CHUNK = 90          # clients per request (+9 warehouses => 99 coords <= demo limit)
MAX_RETRIES = 4
TIMEOUT = 45             # seconds per request
PAUSE = 0.4             # polite delay between requests (seconds)
SUSPICIOUS_HIGH_MIN = 300   # flag drive times above this (Hungary end-to-end ~4h)

LAT_RANGE = (45.5, 49.0)
LON_RANGE = (16.0, 23.5)

_log_lines = []
def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    _log_lines.append(line)


# ----------------------------------------------------------------- excel read
def _find_sheet(xl, *keys):
    for n in xl.sheet_names:
        if any(k in n.lower() for k in keys):
            return n
    raise SystemExit(f"No sheet matching {keys} in {xl.sheet_names}")

def _pick(cols, *keys):
    for c in cols:
        if any(k in str(c).lower() for k in keys):
            return c
    return None

def _detect_latlon(df):
    lat = lon = None
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        med = df[c].median()
        if LAT_RANGE[0] <= med <= LAT_RANGE[1]:
            lat = c
        elif LON_RANGE[0] <= med <= LON_RANGE[1]:
            lon = c
    if lat is None or lon is None:
        raise SystemExit(f"Could not detect lat/lon among {list(df.columns)}")
    return lat, lon

def read_inputs():
    xl = pd.ExcelFile(INPUT)
    cdf = pd.read_excel(INPUT, sheet_name=_find_sheet(xl, "client"))
    wdf = pd.read_excel(INPUT, sheet_name=_find_sheet(xl, "warehouse", "depot"))

    c_nr = _pick(cdf.columns, "client nr", "nr", "id")
    c_name = _pick(cdf.columns, "name")
    c_lat, c_lon = _detect_latlon(cdf)
    w_name = _pick(wdf.columns, "warehouse", "name", "depot") or wdf.columns[0]
    w_lat, w_lon = _detect_latlon(wdf)

    cdf = cdf.dropna(subset=[c_lat, c_lon]).reset_index(drop=True)
    wdf = wdf.dropna(subset=[w_lat, w_lon]).reset_index(drop=True)

    clients = [{
        "nr": "" if c_nr is None or pd.isna(r[c_nr]) else str(r[c_nr]),
        "name": "" if c_name is None or pd.isna(r[c_name]) else str(r[c_name]),
        "lat": float(r[c_lat]), "lon": float(r[c_lon]),
    } for _, r in cdf.iterrows()]
    warehouses = [{
        "name": str(r[w_name]).strip(),
        "lat": float(r[w_lat]), "lon": float(r[w_lon]),
    } for _, r in wdf.iterrows()]

    # de-dupe warehouse names for stable, unique columns
    seen = {}
    for w in warehouses:
        if w["name"] in seen:
            seen[w["name"]] += 1
            w["name"] = f'{w["name"]} ({seen[w["name"]]})'
        else:
            seen[w["name"]] = 1
    return clients, warehouses


# ------------------------------------------------------------------- osrm call
def osrm_table(session, warehouses, chunk):
    """Return a (n_wh x n_chunk) list of durations in seconds (None where unroutable)."""
    coords = warehouses + chunk
    coord_str = ";".join(f'{c["lon"]:.6f},{c["lat"]:.6f}' for c in coords)
    nw = len(warehouses)
    sources = ";".join(str(i) for i in range(nw))
    dests = ";".join(str(i) for i in range(nw, nw + len(chunk)))
    url = (f"{OSRM_BASE}/table/v1/driving/{coord_str}"
           f"?sources={sources}&destinations={dests}&annotations=duration")

    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                if j.get("code") == "Ok" and j.get("durations"):
                    return j["durations"]
                last = f'code={j.get("code")} msg={j.get("message")}'
            else:
                last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        wait = 1.5 * attempt
        log(f"    retry {attempt}/{MAX_RETRIES} after error: {last} (wait {wait:.1f}s)")
        time.sleep(wait)
    raise RuntimeError(f"chunk failed after {MAX_RETRIES} retries: {last}")


# ------------------------------------------------------------------------ main
def main():
    t0 = time.time()
    log(f"Reading {INPUT.name} ...")
    clients, warehouses = read_inputs()
    wh_names = [w["name"] for w in warehouses]
    n_c, n_w = len(clients), len(warehouses)
    log(f"Clients: {n_c}  |  Warehouses: {n_w}  |  pairs: {n_c * n_w}")
    log(f"OSRM: {OSRM_BASE}  (chunk {DEST_CHUNK} clients/request => "
        f"~{-(-n_c // DEST_CHUNK)} requests)")

    # minutes matrix: rows=clients, cols=warehouses
    mins = np.full((n_c, n_w), np.nan, dtype=float)
    failures = []

    session = requests.Session()
    session.headers.update({"User-Agent": "HU-Pharma-Map-RouteMatrix/1.0"})

    n_chunks = -(-n_c // DEST_CHUNK)
    for ci in range(n_chunks):
        lo, hi = ci * DEST_CHUNK, min((ci + 1) * DEST_CHUNK, n_c)
        chunk = clients[lo:hi]
        try:
            durs = osrm_table(session, warehouses, chunk)   # [w][c] seconds
            for wi in range(n_w):
                for k in range(len(chunk)):
                    d = durs[wi][k]
                    if d is None:
                        failures.append({"client_nr": chunk[k]["nr"],
                                         "warehouse": wh_names[wi], "reason": "unroutable (null)"})
                    else:
                        mins[lo + k, wi] = d / 60.0
            log(f"  chunk {ci+1}/{n_chunks}  clients {lo+1}-{hi}  ok")
        except Exception as e:  # noqa: BLE001
            log(f"  chunk {ci+1}/{n_chunks}  clients {lo+1}-{hi}  FAILED: {e}")
            for k in range(len(chunk)):
                for wi in range(n_w):
                    failures.append({"client_nr": chunk[k]["nr"],
                                     "warehouse": wh_names[wi], "reason": f"request failed: {e}"})
        time.sleep(PAUSE)

    # ---- build outputs ----
    matrix = pd.DataFrame(np.round(mins, 1), columns=wh_names)
    matrix.insert(0, "Client Nr", [c["nr"] for c in clients])
    matrix.insert(1, "Client Name", [c["name"] for c in clients])

    # nearest-warehouse figures (kept for the QA report only). We deliberately do
    # NOT write a separate "nearest warehouse" sheet: the dashboard computes the
    # nearest *active* warehouse live from this matrix (warehouses can be toggled
    # off), so a precomputed static nearest column would only go stale.
    nearest_idx = np.full(n_c, -1, dtype=int)
    nearest_min = np.full(n_c, np.nan, dtype=float)
    for i in range(n_c):
        row = mins[i]
        if np.all(np.isnan(row)):
            continue
        j = int(np.nanargmin(row))
        nearest_idx[i] = j
        nearest_min[i] = row[j]

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        matrix.to_excel(xw, sheet_name="Matrix (min)", index=False)
    log(f"Wrote {OUT_XLSX.name}  ({n_c} rows x {n_w} warehouses; single matrix sheet)")

    if failures:
        pd.DataFrame(failures).to_csv(FAIL_LOG, index=False, encoding="utf-8-sig")
        log(f"Wrote {FAIL_LOG.name}  ({len(failures)} failed pairs)")

    # ---- QA report ----
    total_cells = n_c * n_w
    n_nan = int(np.isnan(mins).sum())
    n_zero = int((mins == 0).sum())
    n_high = int((mins > SUSPICIOUS_HIGH_MIN).sum())
    unroutable_clients = int(np.sum(np.all(np.isnan(mins), axis=1)))
    far_clients = int(np.sum(nearest_min > SUSPICIOUS_HIGH_MIN))

    log("=" * 56)
    log("REPORT")
    log(f"  runtime:            {time.time() - t0:.1f}s")
    log(f"  matrix cells:       {total_cells}")
    log(f"  missing (null):     {n_nan}  ({n_nan/total_cells*100:.2f}%)")
    log(f"  exactly 0 min:      {n_zero}")
    log(f"  > {SUSPICIOUS_HIGH_MIN} min:          {n_high}")
    log(f"  clients w/ no route to ANY warehouse: {unroutable_clients}")
    log(f"  clients whose nearest WH > {SUSPICIOUS_HIGH_MIN} min: {far_clients}")
    if np.any(~np.isnan(nearest_min)):
        log(f"  nearest-WH drive time: min {np.nanmin(nearest_min):.1f}  "
            f"median {np.nanmedian(nearest_min):.1f}  max {np.nanmax(nearest_min):.1f} min")
    log("  sample (first 5 clients):")
    for i in range(min(5, n_c)):
        j = nearest_idx[i]
        near = f"{wh_names[j]} @ {nearest_min[i]:.1f}m" if j >= 0 else "NONE"
        log(f"    {clients[i]['nr']}  nearest={near}")
    log("=" * 56)

    RUN_LOG.write_text("\n".join(_log_lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
