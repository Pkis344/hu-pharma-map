"""
Precompute REAL-ROAD geometry for the default-network delivery routes (all existing
warehouses open) and write Dashboards/Dashboard V4/routes_roads.json.

Keyed by route MEMBERSHIP signature: "<wh>|<sorted client nrs>" — matches the app's
routeSig(), so a route keeps its real road as long as its client set is unchanged
(routes far from a toggled warehouse stay on real roads; only changed routes beeline).

Replicates the app's default routing (assign to nearest existing WH -> sweep cluster
into 10-30 -> NN + 2-opt order), then asks public OSRM for the road path per route.
"""
import openpyxl, math, json, time, urllib.request, urllib.error, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precompute_progress.txt")
WORKERS = 6
SRC = os.path.join(ROOT, "Dashboard Input", "Clients and warehouses - Populated.xlsx")
MAT = os.path.join(ROOT, "Route planner", "route_time_matrix_v3.xlsx")
OUT = os.path.join(ROOT, "Dashboards", "Dashboard V4", "routes_roads.json")
OSRM = "https://router.project-osrm.org/route/v1/driving/"
TARGET, MINS, MAXS = 20, 10, 30

def hav(a, b):
    R = 6371; dlat = math.radians(b[1]-a[1]); dlon = math.radians(b[0]-a[0])
    s = math.sin(dlat/2)**2 + math.cos(math.radians(a[1]))*math.cos(math.radians(b[1]))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(s))

# nearest existing warehouse per client (default network)
mb = openpyxl.load_workbook(MAT, data_only=True, read_only=True); ms = mb["Matrix (min)"]
it = ms.iter_rows(values_only=True); mh = list(next(it))
whcols = [(i, h) for i, h in enumerate(mh) if h not in ("Client Nr", "Client Name") and "potential" not in str(h).lower()]
assign = {}
for r in it:
    nr = r[0]
    if nr is None: continue
    best = None; bn = None
    for i, h in whcols:
        v = r[i]
        if isinstance(v, (int, float)) and (best is None or v < best): best = v; bn = h
    assign[str(nr)] = bn
mb.close()

wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)
wh = {}   # name -> (lon,lat)  in Warehouses-sheet order
whorder = []
for row in list(wb["Warehouses"].iter_rows(values_only=True))[1:]:
    if row and row[0]:
        nm = str(row[0]).strip(); wh[nm] = (row[2], row[1]); whorder.append(nm)
cs = wb["Clients"]; chdr = [c.value for c in next(cs.iter_rows(min_row=1, max_row=1))]
iNr = chdr.index("Client Nr"); iLat = chdr.index("Latitude"); iLon = chdr.index("Longitude")
pt = {}; groups = {}
for row in cs.iter_rows(min_row=2, values_only=True):
    nr = row[iNr]
    if nr is None: continue
    lat, lon = row[iLat], row[iLon]
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)): continue
    nr = str(nr); bn = assign.get(nr)
    if not bn: continue
    pt[nr] = (lon, lat); groups.setdefault(bn, []).append(nr)
wb.close()

def order_route(chunk, w):
    cur = w; rem = chunk[:]; seq = []
    while rem:
        bi = min(range(len(rem)), key=lambda i: hav(cur, pt[rem[i]])); cur = pt[rem[bi]]; seq.append(rem.pop(bi))
    coords = [w] + [pt[n] for n in seq] + [w]
    improved = True; passes = 0
    while improved and passes < 20:
        improved = False; passes += 1
        for i in range(1, len(coords)-2):
            for k in range(i+1, len(coords)-1):
                d0 = hav(coords[i-1], coords[i]) + hav(coords[k], coords[k+1])
                d1 = hav(coords[i-1], coords[k]) + hav(coords[i], coords[k+1])
                if d1 + 1e-9 < d0:
                    coords[i:k+1] = coords[i:k+1][::-1]; improved = True
    # map ordered interior coords back to nrs
    key = {pt[n]: n for n in chunk}
    return [key[c] for c in coords[1:-1]]

def osrm(waypts):
    url = OSRM + ";".join(f"{c[0]},{c[1]}" for c in waypts) + "?overview=full&geometries=geojson"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                j = json.load(resp)
            if j.get("code") == "Ok" and j.get("routes"):
                rt = j["routes"][0]
                return rt["geometry"]["coordinates"], rt["distance"]/1000.0, rt["duration"]/60.0
        except Exception as e:
            time.sleep(1.0 + attempt)
    return None

out = {}; total = 0; done = 0; failed = 0
# build chunks per warehouse (sweep), matching the app
plan = []
for name in whorder:
    cl = groups.get(name)
    if not cl: continue
    wlon, wlat = wh[name]; n = len(cl)
    withang = sorted(cl, key=lambda nr: (math.atan2(pt[nr][1]-wlat, pt[nr][0]-wlon), str(nr)))
    nR = math.floor(n/TARGET + 0.5); nR = max(math.ceil(n/MAXS), nR); nR = min(max(1, n//MINS), nR); nR = max(1, nR)
    base, rem = divmod(n, nR); idx = 0
    for rr in range(nR):
        size = base + (1 if rr < rem else 0)
        plan.append((name, withang[idx:idx+size])); idx += size
total = len(plan)
t0 = time.time()
lock = threading.Lock()
def write_progress():
    el = int(time.time() - t0); n = done + failed
    rate = n / el if el else 0
    eta = int((total - n) / rate) if rate else 0
    with open(PROGRESS, "w") as fp:
        fp.write(f"{n}/{total} done (ok {done}, failed {failed}) | elapsed {el}s | eta ~{eta}s\n")

def work(item):
    name, chunk = item
    w = wh[name]
    seq = order_route(chunk, w)
    waypts = [w] + [pt[n] for n in seq] + [w]
    res = osrm(waypts)
    sig = name + "|" + ",".join(sorted(chunk))     # MEMBERSHIP signature (matches app routeSig)
    return sig, res

write_progress()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = [ex.submit(work, it) for it in plan]
    for fut in as_completed(futs):
        sig, res = fut.result()
        with lock:
            if res:
                coords, km, mn = res
                out[sig] = {"km": round(km, 2), "min": round(mn, 1), "coords": coords}
                done += 1
            else:
                failed += 1
            if (done + failed) % 5 == 0 or (done + failed) == total:
                write_progress()

json.dump(out, open(OUT, "w"), separators=(",", ":"))
sz = os.path.getsize(OUT)/1024/1024
with open(PROGRESS, "a") as fp:
    fp.write(f"DONE: wrote {done} routes ({failed} failed) -> routes_roads.json ({sz:.2f} MB) in {int(time.time()-t0)}s\n")
print(f"Wrote {done} routes ({failed} failed) -> {OUT}  ({sz:.2f} MB)")
