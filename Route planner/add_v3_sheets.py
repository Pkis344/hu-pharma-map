"""
V3 - add two sheets to the shared workbook WITHOUT disturbing V2.

Appends (at the end, after 'Warehouses' so V2's first-match sheet detection is
unaffected):
  - 'Warehouse Costs'      : annual fixed-cost breakdown for the 9 existing sites,
                             + total + avoidable-on-closure share and saving.
  - 'Potential Warehouses' : Zalaegerszeg & Dunafoldvar - coords + annual operating
                             cost breakdown + one-off setup cost.

All money is EUR/year (setup is one-off EUR). A timestamped backup of the workbook
is written first. Re-running replaces just these two sheets (idempotent).
"""
import shutil
from datetime import datetime
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
WB = ROOT / "Dashboard Input" / "Clients and warehouses - Populated.xlsx"
BACKUP = ROOT / "Dashboard Input" / f"_backup Populated (pre-V3) {datetime.now():%Y%m%d-%H%M%S}.xlsx"

COST_COLS = ["Facility (EUR/yr)", "Staff (EUR/yr)", "Utilities & energy (EUR/yr)",
             "Equipment & maintenance (EUR/yr)", "IT & security (EUR/yr)",
             "Insurance & compliance (EUR/yr)", "Other overhead (EUR/yr)"]

# existing 9: components (EUR/yr) + avoidable-on-closure %
EXISTING = {
    #              facility  staff    util    equip   it      ins     ovh     avoid%
    "Budapest":   (820000, 1650000, 300000, 360000, 150000, 130000, 210000, 0.65),
    "Debrecen":   (340000,  720000, 140000, 150000,  60000,  55000,  90000, 0.80),
    "Szeged":     (300000,  640000, 125000, 135000,  52000,  48000,  80000, 0.82),
    "Gyor":       (310000,  620000, 120000, 130000,  50000,  47000,  78000, 0.82),
    "Pecs":       (260000,  560000, 110000, 120000,  45000,  42000,  70000, 0.84),
    "Miskolc":    (250000,  540000, 108000, 115000,  44000,  40000,  68000, 0.84),
    "Nyiregyhaza":(190000,  420000,  86000,  92000,  35000,  32000,  54000, 0.88),
    "Szolnok":    (180000,  400000,  82000,  88000,  34000,  30000,  52000, 0.88),
    "Kaposvar":   (165000,  380000,  78000,  84000,  32000,  28000,  50000, 0.90),
}

# potential: name -> (lat, lon, facility, staff, util, equip, it, ins, ovh, setup_oneoff)
POTENTIAL = {
    "Zalaegerszeg (potential)": (46.8417, 16.8416, 175000, 390000, 80000, 86000, 33000, 30000, 52000, 650000),
    "Dunafoldvar (potential)":  (46.8017, 18.9278, 160000, 360000, 74000, 80000, 31000, 28000, 48000, 560000),
}


def main():
    if not WB.exists():
        raise SystemExit(f"Workbook not found: {WB}")
    shutil.copy2(WB, BACKUP)
    print("Backup ->", BACKUP.name)

    wb = openpyxl.load_workbook(WB)
    for s in ("Warehouse Costs", "Potential Warehouses"):
        if s in wb.sheetnames:
            del wb[s]

    # ---- Warehouse Costs ----
    ws = wb.create_sheet("Warehouse Costs")   # appended at end
    header = (["Warehouse"] + COST_COLS
              + ["Total annual fixed cost (EUR/yr)", "Avoidable if closed (%)",
                 "Avoidable saving (EUR/yr)"])
    ws.append(header)
    for name, v in EXISTING.items():
        comps = v[:7]
        avoid = v[7]
        total = sum(comps)
        ws.append([name, *comps, total, round(avoid * 100), round(total * avoid)])

    # ---- Potential Warehouses ----
    wp = wb.create_sheet("Potential Warehouses")
    ph = (["Warehouse", "Lat", "Long"] + COST_COLS
          + ["Annual operating cost (EUR/yr)", "One-off setup (EUR)"])
    wp.append(ph)
    for name, v in POTENTIAL.items():
        lat, lon = v[0], v[1]
        comps = v[2:9]
        setup = v[9]
        annual = sum(comps)
        wp.append([name, lat, lon, *comps, annual, setup])

    wb.save(WB)
    print("Saved. Sheet order now:", wb.sheetnames)


if __name__ == "__main__":
    main()
