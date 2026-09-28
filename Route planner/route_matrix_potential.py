"""
V3 helper - compute drive-time columns for the two POTENTIAL warehouses
(Zalaegerszeg, Dunafoldvar) to every client, via OSRM, and merge them with the
existing 9-warehouse matrix into a NEW file so V2's matrix stays untouched.

Reads : ../Dashboard Input/Clients and warehouses - Populated.xlsx  (client coords)
        ./route_time_matrix.xlsx                                    (existing 9 cols)
Writes: ./route_time_matrix_v3.xlsx  (Client Nr, Client Name, 9 existing + 2 potential)

Run:  python route_matrix_potential.py
"""
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
POP = ROOT.parent / "Dashboard Input" / "Clients and warehouses - Populated.xlsx"
EXIST = ROOT / "route_time_matrix.xlsx"
OUT = ROOT / "route_time_matrix_v3.xlsx"

OSRM_BASE = "https://router.project-osrm.org"
DEST_CHUNK = 90
MAX_RETRIES = 5
TIMEOUT = 45
PAUSE = 0.4

POTENTIAL = [
    {"name": "Zalaegerszeg (potential)", "lat": 46.8417, "lon": 16.8416},
    {"name": "Dunafoldvar (potential)",  "lat": 46.8017, "lon": 18.9278},
]


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def read_clients():
    cdf = pd.read_excel(POP, sheet_name="Clients")
    cdf = cdf.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
    return [{"nr": str(r["Client Nr"]), "name": str(r["Client Name"]),
             "lat": float(r["Latitude"]), "lon": float(r["Longitude"])}
            for _, r in cdf.iterrows()]


def osrm_table(session, sources, chunk):
    coords = sources + chunk
    coord_str = ";".join(f'{c["lon"]:.6f},{c["lat"]:.6f}' for c in coords)
    ns = len(sources)
    src = ";".join(str(i) for i in range(ns))
    dst = ";".join(str(i) for i in range(ns, ns + len(chunk)))
    url = (f"{OSRM_BASE}/table/v1/driving/{coord_str}"
           f"?sources={src}&destinations={dst}&annotations=duration")
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                if j.get("code") == "Ok" and j.get("durations"):
                    return j["durations"]
                last = f'code={j.get("code")}'
            else:
                last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        wait = 1.5 * attempt
        log(f"    retry {attempt}/{MAX_RETRIES}: {last} (wait {wait:.1f}s)")
        time.sleep(wait)
    raise RuntimeError(f"chunk failed: {last}")


def main():
    t0 = time.time()
    clients = read_clients()
    n = len(clients)
    log(f"Clients: {n} | potential warehouses: {len(POTENTIAL)}")

    mins = np.full((n, len(POTENTIAL)), np.nan)
    session = requests.Session()
    session.headers.update({"User-Agent": "HU-Pharma-Map-RouteMatrix-V3/1.0"})

    n_chunks = -(-n // DEST_CHUNK)
    for ci in range(n_chunks):
        lo, hi = ci * DEST_CHUNK, min((ci + 1) * DEST_CHUNK, n)
        chunk = clients[lo:hi]
        durs = osrm_table(session, POTENTIAL, chunk)   # [src][client] seconds
        for si in range(len(POTENTIAL)):
            for k in range(len(chunk)):
                d = durs[si][k]
                if d is not None:
                    mins[lo + k, si] = d / 60.0
        log(f"  chunk {ci+1}/{n_chunks}  clients {lo+1}-{hi}  ok")
        time.sleep(PAUSE)

    new = pd.DataFrame(np.round(mins, 1), columns=[w["name"] for w in POTENTIAL])
    new.insert(0, "Client Nr", [c["nr"] for c in clients])

    exist = pd.read_excel(EXIST, sheet_name="Matrix (min)")
    exist["Client Nr"] = exist["Client Nr"].astype(str)
    merged = exist.merge(new, on="Client Nr", how="left")

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        merged.to_excel(xw, sheet_name="Matrix (min)", index=False)

    miss = int(np.isnan(mins).sum())
    log(f"Wrote {OUT.name}: {merged.shape[0]} rows x {merged.shape[1]} cols "
        f"({list(merged.columns)[-2:]} added). Missing potential cells: {miss}")
    log(f"Done in {time.time()-t0:.1f}s")
    for w in POTENTIAL:
        col = merged[w["name"]]
        log(f"  {w['name']}: min {col.min():.1f}  median {col.median():.1f}  max {col.max():.1f} min")


if __name__ == "__main__":
    main()
