# V5 — Self-hosted OSRM setup

V5 adds **real road routing for every scenario** by talking to your own copy of
OSRM (the Open Source Routing Machine) running on `http://localhost:5000`.

You don't *have* to run it — V5 opens and works without it, falling back to the
precomputed roads + straight-line estimates (exactly like V4). But with the local
server running, **every** delivery route in **every** open/close scenario draws on
real roads, and the cost model uses real drive times instead of estimates.

The dashboard detects the server automatically. The little line under
"Delivery routes" in the Scenario calculator tells you which mode you're in:

- **● Local OSRM** — real road distances & times, live for every scenario ← the goal
- **● Public OSRM** — real roads only for the default network & single routes
- **● OSRM offline** — precomputed roads + straight-line estimates

---

## One-time setup (~30–45 min, mostly unattended)

### 1. Install Docker Desktop (free)
Download and install from
<https://www.docker.com/products/docker-desktop/>. Accept the WSL2 option if
prompted (Windows 11 handles this automatically). Restart if it asks. Launch
**Docker Desktop** and wait until the bottom-left status says **"Engine running"**.

*(Docker Desktop is free for personal and small-business use.)*

### 2. Build + start the routing server
Double-click **`start-osrm.bat`** (in this V5 folder).

On the **first** run it will:
1. download the Hungary map extract (~250 MB) from Geofabrik, then
2. build the routing graph in three steps (extract → partition → customize),
   ~5–10 minutes, one time only.

It saves everything to a shared **`osrm-data`** folder at the project root
(`HU Pharma Map\osrm-data`), so you only build once even if a later dashboard
version reuses it.

When you see **`running and waiting for requests`**, the server is up. **Leave
that window open** while you use the dashboard.

### 3. Open the dashboard
Double-click **`start.bat`** (the normal V5 launcher, port 8767). The status line
should now read **● Local OSRM**. Enter **Logistics**, and as routes hydrate
you'll briefly see "computing real roads for N route(s)…", then the map lines and
the cost figures switch to real-road values.

---

## Everyday use
1. Start **Docker Desktop** (or leave it running).
2. Double-click **`start-osrm.bat`** → wait for "waiting for requests" (a few seconds — no rebuild).
3. Double-click **`start.bat`** → use the dashboard.

To **stop** the routing server, close its window (or press `Ctrl+C` in it). The
dashboard keeps working in offline/precomputed mode.

---

## Updating the map data (optional, occasional)
Geofabrik refreshes the Hungary extract regularly. To pull a newer map, delete
these from `HU Pharma Map\osrm-data` and re-run `start-osrm.bat`:
- `hungary-latest.osm.pbf`
- `_built.ok`

(It will re-download and rebuild.)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `start-osrm.bat` says *Docker was not found* | Install Docker Desktop (step 1). |
| *engine is not running* | Open Docker Desktop, wait for "Engine running", retry. |
| Build fails / killed | Give Docker more memory: Docker Desktop → Settings → Resources (4 GB+). Then delete `_built.ok` and re-run. |
| Download fails | Re-run, or download the `.pbf` manually from the URL the script prints into `osrm-data`. |
| Dashboard still says **OSRM offline** | Is the `start-osrm.bat` window open and showing "waiting for requests"? Is it on port 5000? Reload the dashboard. |
| Port 5000 already in use | Something else uses 5000. Stop it, or change the port in **both** `start-osrm.bat` (`-p 5000:5000`) and `index.html` (`OSRM_LOCAL`). |

---

## What this changes vs. V4 (technical)
- New: `OSRM_LOCAL` / `OSRM_PUBLIC` endpoints + `detectOsrm()` (local → public → off).
- New: `hydrateRoads()` fetches real road geometry + time for **all** routes in the
  current network (only the uncached ones), cancelable per scenario.
- Cost model now prefers **real OSRM minutes** (`realRouteMin`/`networkRealMin`) for
  both the baseline and the current network, so the "is it worth it?" travel term is
  road-exact when a local OSRM is available; otherwise it degrades to the V4 estimate.
- Everything else (routing heuristic, precomputed `routes_roads.json`, on-demand
  single-route roads, the whole UI) is unchanged from V4.

> **Note on the alternative image:** the script uses
> `ghcr.io/project-osrm/osrm-backend`. If that ever fails to pull, the classic
> Docker Hub image `osrm/osrm-backend` is a drop-in replacement — change the
> `IMAGE=` line in `start-osrm.bat`.
