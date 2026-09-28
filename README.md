# Logistics & Sales Mapping Overview — Hungary

An interactive dashboard for **pharmaceutical distribution across Hungary**: warehouse
logistics, delivery routing, and sales-territory planning over ~5,200 clients and 9
warehouses. Single-file web app (Tailwind + MapLibre GL + SheetJS, all vendored — no
build step, no CDN).

## ▶ Live demo

**https://pkis344.github.io/hu-pharma-map/**

Opens straight to the dashboard. It reads the bundled Excel data on load, so nothing to
install. Real-road routing uses the public OSRM demo server where available and otherwise
falls back to precomputed road geometry + straight-line estimates.

## What it does

- **Dashboard** — all clients & warehouses on the map, filterable by revenue and type.
- **Logistics** — open/close warehouses (incl. 2 potential sites), live delivery-route
  planning, a road-based cost model, and a one-click network optimizer.
- **Sales** — territory design over independent pharmacies: office- and home-office-based
  reps, drive-time travel costs, per-client reassignment, clustering, and an
  auto-optimizer that minimizes travel + salary cost.

## Run it locally

The app fetches its Excel data, so it needs a local web server (not a `file://` open):

```
cd "Dashboards/Dashboard V5"
start.bat          # serves the project on http://localhost:8767 and opens the dashboard
```

Optional real-road routing for **every** route in **every** scenario, via a self-hosted
OSRM engine (Docker, one-time ~30 min setup) — see
[`Dashboards/Dashboard V5/SETUP.md`](Dashboards/Dashboard%20V5/SETUP.md):

```
start-osrm.bat     # builds/serves the Hungary road graph on localhost:5000
```

## Layout

```
index.html                         # redirect to the dashboard (for GitHub Pages)
Dashboards/Dashboard V5/           # the app (index.html), vendored libs, precomputed roads
Dashboard Input/                   # clients & warehouses workbook (read live)
Route planner/                     # Python scripts + drive-time matrix (OSRM)
```

## Data note

`Dashboard Input/Clients and warehouses - Populated.xlsx` holds the client and warehouse
records the dashboard visualizes. It is a recreation of a professional logistics project
for demonstration purposes.
