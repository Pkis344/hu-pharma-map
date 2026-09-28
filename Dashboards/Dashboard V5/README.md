# Logistics & Sales mapping overview — Dashboard V5

Everything from **Dashboard V4** (interactive client/warehouse map, Logistics
coverage + live scenario cost model, Sales territories, heuristic delivery
routing, precomputed real-road geometry for the default network, and on-demand
real roads for a single selected route) **plus optional self-hosted OSRM for
real road routing in _every_ scenario.**

> V4 is left completely untouched. V5 is a separate copy on its own port (8767)
> and can be run side by side with V4 (8766).

## What's new in V5

**Real roads for every route, in every scenario — when a local OSRM is running.**

V4 could only show real road geometry for (a) the *default* network (precomputed
into `routes_roads.json`) and (b) one single route you click (fetched on demand
from the public OSRM demo server). Toggled scenarios fell back to straight-line
("beeline") estimates, and the cost model used a haversine estimate throughout.

V5 adds a routing-engine layer that automatically picks the best available OSRM:

1. **Local OSRM** (`http://localhost:5000`) — if you're running your own server
   (see **`SETUP.md`**), V5 fetches real road geometry **and drive times for all
   routes in the current network**, live, on every open/close. The
   "is it worth it?" **cost model then uses real minutes** for both the baseline
   and the scenario, so the travel term is road-exact.
2. **Public OSRM** — if there's no local server but the public demo server is
   reachable, V5 behaves like V4 (real roads for the default network + single
   routes; estimates elsewhere).
3. **Offline** — no OSRM at all: precomputed roads + straight-line estimates.

A status line under **Delivery routes** in the Scenario calculator shows which
mode is active (● Local OSRM / ● Public OSRM / ● OSRM offline).

Nothing else changed from V4 — same data, same routing heuristic, same UI.

## Running it

### Dashboard only (no setup)
Double-click **`start.bat`** — starts a local web server rooted at the project
folder and opens V5 on **port 8767**. Works immediately in offline/precomputed
mode. (A server is required so the browser can read the Excel + JSON files.)

> ⚠️ **Close the workbook in Excel/OneDrive before launching** or the data load
> 404s. Then hit **Reload data**.

### With real-road routing everywhere
Run your own OSRM first — see **`SETUP.md`** (one-time ~30–45 min, then seconds
each day). In short: install Docker Desktop, double-click **`start-osrm.bat`**,
then **`start.bat`**. The status line will read **● Local OSRM**.

## Inputs (read live)

| File | Used for |
|------|----------|
| `../../Dashboard Input/Clients and warehouses - Populated.xlsx` | clients, warehouses, sales, `Warehouse Costs`, `Potential Warehouses` |
| `../../Route planner/route_time_matrix_v3.xlsx` | client × warehouse drive-time matrix (incl. the 2 potential sites) |
| `routes_roads.json` | precomputed real-road geometry for the default network |

## Files

| File | Purpose |
|------|---------|
| `index.html` | The dashboard (Dashboard + Logistics + Sales + routing + cost model). |
| `start.bat` | Launches the local web server and opens V5 (port 8767). |
| `start-osrm.bat` | Builds + runs a local OSRM routing server (Docker). One-time build, then serves on :5000. |
| `SETUP.md` | Step-by-step guide to the self-hosted OSRM. |
| `routes_roads.json` | Precomputed real-road geometry for the default network. |
| `vendor/` | Tailwind, MapLibre GL JS, SheetJS (bundled, no CDN needed). |

## Sales assignment rules (live-editable)
The Sales view assigns clients to reps **dynamically** from two controls in the panel:
- **Min yearly revenue (€):** clients earning below this are dropped from rep
  assignment (default 0 — off; note every client already earns ≥ ~€11k, so the floor
  only bites above that).
- **Max clients / rep:** caps each rep's client load (default **45**). Each rep keeps
  its highest-revenue clients up to the cap; overflow is **reassigned to the nearest
  rep still under the cap** (cascading), and anything that can't be placed stays
  **unassigned** (shown as light-grey dots, excluded from every territory).

Territories (the convex-hull areas), per-rep client counts, and the encroachment
("other reps' clients in area") metric all recompute instantly when you change either
control. A note under the inputs shows how many clients are assigned vs. dropped.

> Note: the 45-cap is enforced by default, so the default Sales view shows capped
> territories. Raise "Max clients / rep" to see the uncapped assignment.

## Cost assumptions (live-editable)
The travel-cost side of the "is it worth it?" model uses a **fully-loaded cost per
driving hour**, built from live-editable components in the Scenario calculator:
- **Direct costs:** Labor (driver), Fuel, Maintenance & tyres, Depreciation / leasing
- **Overheads:** Insurance, Admin & other overhead

Their sum (default **€35/h**) is shown as "Cost per driving hour (fully loaded)" and
is what every route/scenario cost figure is priced on. Edit any component and the
total, the routes summary, and the net-impact verdict all update instantly.

## Caveats
- Costs and avoidable-% figures are realistic **placeholders**, tuned in the Excel
  (warehouse fixed costs) and the Scenario calculator (the €/h components + deliveries/yr).
- The routing is a good heuristic (sweep + nearest-neighbour + 2-opt), not a full
  capacitated VRP optimum. Local OSRM makes the *distances/times* real, but the
  *stop assignment and ordering* are still heuristic.
- The company/setting is fictional; the pharmacy locations and routes are real.
