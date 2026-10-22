"""
CarbonWise: quantum-assisted campus energy optimization (VTU Belagavi case study)
Run in VS Code:  python carbonwise_3d.py
Needs vtu_belagavi.jpg in the same folder as this file.
Install once:    pip install numpy pandas matplotlib imageio imageio-ffmpeg pillow

Note: "QAOA-inspired" is a classical heuristic, not an executed quantum circuit.
All energy, price and emissions values are simulated, not VTU's real data.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import imageio.v2 as imageio
from PIL import Image

BASE = Path(__file__).resolve().parent
CAMPUS_NAME = "VTU Belagavi"
OUTPUT_DIR = BASE / "carbonwise_output"
OUTPUT_DIR.mkdir(exist_ok=True)
VIDEO = OUTPUT_DIR / "CarbonWise_3D_Campus.mp4"
CSV = OUTPUT_DIR / "CarbonWise_Energy_Data.csv"
FRAMES = OUTPUT_DIR / "frames3d"
FRAMES.mkdir(exist_ok=True)

# ---------------- campus photo ----------------
IMG_PATH = BASE / "vtu_belagavi.jpg"
try:
    campus_img = imageio.imread(IMG_PATH)
except Exception:
    campus_img = None
    print(f"Photo not found at {IMG_PATH}, using placeholder.")

# ---------------- simulation ----------------
HOURS = np.arange(24)
BATTERY_CAPACITY, MAX_BATTERY_POWER, INITIAL_BATTERY = 100.0, 25.0, 25.0
GRID_PRICE = np.array([5, 5, 5, 5, 5, 6, 7, 8, 10, 10, 9, 8,
                       8, 8, 9, 10, 12, 14, 15, 14, 11, 8, 6, 5], dtype=float)
GRID_CARBON, SOLAR_CAPACITY = 0.70, 80.0

solar = SOLAR_CAPACITY * np.maximum(0, np.sin(np.pi * (HOURS - 6) / 12))
solar *= np.clip(0.92 + 0.08 * np.sin(HOURS * 1.7), 0.75, 1.0)
demand = (38 + 12 * np.sin((HOURS - 7) * np.pi / 12) ** 2
          + 14 * np.exp(-((HOURS - 19) / 3.0) ** 2))
demand += np.array([0, 0, 0, 0, 0, 1, 3, 7, 10, 8, 5, 4,
                    3, 4, 5, 7, 9, 12, 14, 11, 7, 4, 2, 1])


def simulate_dispatch(strategy):
    battery = INITIAL_BATTERY
    bat, grd, cst, emi = [], [], [], []
    for t in HOURS:
        load = demand[t]
        used = min(solar[t], load)
        remaining = load - used
        surplus = solar[t] - used
        charge = discharge = 0.0
        if strategy in ("classical", "quantum"):
            thr, reserve = (10, 10) if strategy == "classical" else (8, 8)
            if surplus > 0:
                charge = min(surplus, MAX_BATTERY_POWER, BATTERY_CAPACITY - battery)
            elif GRID_PRICE[t] >= thr and battery > reserve:
                discharge = min(remaining, MAX_BATTERY_POWER, battery - reserve)
        battery = min(BATTERY_CAPACITY, max(0.0, battery + charge - discharge))
        g = max(0.0, remaining - discharge)
        bat.append(battery)
        grd.append(g)
        cst.append(g * GRID_PRICE[t])
        emi.append(g * GRID_CARBON)
    return {"battery": np.array(bat), "grid": np.array(grd),
            "cost": np.array(cst), "emissions": np.array(emi)}


results = {
    "Baseline": simulate_dispatch("baseline"),
    "Classical": simulate_dispatch("classical"),
    "CarbonWise QAOA-inspired": simulate_dispatch("quantum"),
}
Q = results["CarbonWise QAOA-inspired"]

# CSV export
data = pd.DataFrame({"Hour": HOURS, "Solar_kW": solar,
                     "Demand_kW": demand, "Grid_Price": GRID_PRICE})
for name, r in results.items():
    p = name.replace(" ", "_").replace("-", "_")
    data[f"{p}_Grid_kWh"] = r["grid"]
    data[f"{p}_Battery_kWh"] = r["battery"]
    data[f"{p}_Cost"] = r["cost"]
    data[f"{p}_Emissions_kg"] = r["emissions"]
data.to_csv(CSV, index=False)

# Fair metrics: charge any battery energy used up vs the starting level
avg_price = GRID_PRICE.mean()
metrics = {}
for name, r in results.items():
    drained = INITIAL_BATTERY - r["battery"][-1]
    metrics[name] = {
        "grid": float(r["grid"].sum()),
        "cost": float(r["cost"].sum() + drained * avg_price),
        "emissions": float(r["emissions"].sum() + drained * GRID_CARBON),
        "final_battery": float(r["battery"][-1]),
    }
b, q = metrics["Baseline"], metrics["CarbonWise QAOA-inspired"]
cost_saving = 100 * (b["cost"] - q["cost"]) / b["cost"]
emission_saving = 100 * (b["emissions"] - q["emissions"]) / b["emissions"]

# ---------------- 3D video ----------------
if campus_img is not None:
    TEX = np.asarray(Image.fromarray(campus_img[:, :, :3]).resize((100, 58))) / 255.0
    aspect = campus_img.shape[1] / campus_img.shape[0]
else:
    TEX = np.full((58, 100, 3), [0.1, 0.4, 0.3])
    aspect = 1.7
ny, nx = TEX.shape[:2]
W = 4.4
H = W / aspect
PX = np.tile(np.linspace(-W / 2, W / 2, nx), (ny, 1))
PZ = np.tile(np.linspace(H + 0.1, 0.1, ny).reshape(-1, 1), (1, nx))
PY = np.zeros_like(PX)
th = np.linspace(0, 2 * np.pi, 120)

plt.rcParams.update({
    "figure.facecolor": "#101827", "axes.facecolor": "#182337",
    "axes.edgecolor": "#63718a", "axes.labelcolor": "white",
    "xtick.color": "white", "ytick.color": "white",
    "text.color": "white", "font.size": 9,
})

TOTAL = 72
frames = []
print("Rendering 3D frames (about 3-4 minutes)...")

for f in range(TOTAL):
    h = 1 + int(f * 23 / (TOTAL - 1))
    azim = -60 + 360 * f / TOTAL

    fig = plt.figure(figsize=(12.8, 7.2))
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 2.2, 1],
                          left=0.04, right=0.99, top=0.88,
                          bottom=0.08, hspace=0.4, wspace=0.18)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[1, 0])
    ax3d = fig.add_subplot(gs[:, 1], projection="3d")
    ax_c = fig.add_subplot(gs[0, 2])
    ax_d = fig.add_subplot(gs[1, 2])

    fig.suptitle(f"CARBONWISE | QUANTUM-ASSISTED ENERGY FOR {CAMPUS_NAME.upper()}",
                 fontsize=15, fontweight="bold", color="#64f4ac")

    # 3D centre: rotating campus panel with live bars around it
    ax3d.set_facecolor("#101827")
    ax3d.plot(4.0 * np.cos(th), 4.0 * np.sin(th), 0, color="#3b82f6", lw=2)
    ax3d.plot(1.0 * np.cos(th), 1.0 * np.sin(th), 0, color="#1f3b66", lw=1)
    ax3d.plot_surface(PX, PY, PZ, facecolors=TEX, shade=False,
                      rstride=1, cstride=1, antialiased=False)
    ax3d.plot_surface(PX, PY + 0.04, PZ, facecolors=TEX[:, ::-1], shade=False,
                      rstride=1, cstride=1, antialiased=False)

    vals = [
        ("Solar", solar[h - 1], SOLAR_CAPACITY, "kW", "#fbbf24"),
        ("Demand", demand[h - 1], 80.0, "kW", "#60a5fa"),
        ("Grid", Q["grid"][h - 1], 80.0, "kWh", "#fb7185"),
        ("Battery", Q["battery"][h - 1], BATTERY_CAPACITY, "kWh", "#64f4ac"),
    ]
    for i, (lab, v, vmax, unit, col) in enumerate(vals):
        ang = np.deg2rad(45 + 90 * i)
        bx, by = 3.4 * np.cos(ang), 3.4 * np.sin(ang)
        dz = max(0.08, 3.0 * v / vmax)
        ax3d.bar3d(bx - 0.28, by - 0.28, 0, 0.56, 0.56, dz, color=col, shade=True)
        ax3d.text(bx, by, dz + 0.3, f"{lab}\n{v:.0f} {unit}",
                  ha="center", color=col, fontsize=9, fontweight="bold")

    ax3d.set_xlim(-4, 4)
    ax3d.set_ylim(-4, 4)
    ax3d.set_zlim(0, 4.2)
    ax3d.set_box_aspect((1, 1, 0.6), zoom=1.3)
    ax3d.view_init(elev=22, azim=azim)
    ax3d.set_axis_off()
    ax3d.set_title(f"{CAMPUS_NAME}  |  {h - 1:02d}:00", color="#64f4ac", fontsize=12)

    # side panels
    ax_a.plot(HOURS, solar, color="#fbbf24", linewidth=2, label="Solar")
    ax_a.plot(HOURS, demand, color="#60a5fa", linewidth=2, label="Demand")
    ax_a.axvline(h - 1, color="white", linestyle="--", alpha=0.7)
    ax_a.set_title("Solar vs Campus Demand")
    ax_a.set_ylabel("kW")
    ax_a.legend(fontsize=7)
    ax_a.grid(alpha=0.2)

    for name, color in [("Baseline", "#fb7185"), ("Classical", "#60a5fa"),
                        ("CarbonWise QAOA-inspired", "#64f4ac")]:
        ax_b.plot(HOURS[:h], results[name]["grid"][:h],
                  label=name, color=color, linewidth=2)
    ax_b.set_xlim(0, 23)
    ax_b.set_title("Grid Electricity Consumption")
    ax_b.set_xlabel("Hour")
    ax_b.set_ylabel("kWh")
    ax_b.legend(fontsize=6)
    ax_b.grid(alpha=0.2)

    ax_c.plot(HOURS[:h], results["Classical"]["battery"][:h],
              color="#60a5fa", linewidth=2, label="Classical")
    ax_c.plot(HOURS[:h], Q["battery"][:h],
              color="#64f4ac", linewidth=2, label="QAOA-inspired")
    ax_c.axhline(BATTERY_CAPACITY, color="white", linestyle=":", alpha=0.6)
    ax_c.set_xlim(0, 23)
    ax_c.set_ylim(0, BATTERY_CAPACITY + 10)
    ax_c.set_title("Battery State of Charge")
    ax_c.set_xlabel("Hour")
    ax_c.set_ylabel("kWh")
    ax_c.legend(fontsize=7)
    ax_c.grid(alpha=0.2)

    ax_d.axis("off")
    ax_d.set_title("Live Dashboard", pad=8)
    ax_d.text(0.03, 0.97,
              f"Solar total: {solar[:h].sum():,.1f} kWh\n"
              f"Demand total: {demand[:h].sum():,.1f} kWh\n"
              f"Grid used: {Q['grid'][:h].sum():,.1f} kWh\n"
              f"Grid cost: {Q['cost'][:h].sum():,.1f} units\n"
              f"CO2: {Q['emissions'][:h].sum():,.1f} kg\n\n"
              "Engine: QAOA-inspired\n(classical simulation)",
              transform=ax_d.transAxes, va="top", fontsize=9,
              linespacing=1.5, color="#e5e7eb")

    path = FRAMES / f"f_{f:03d}.png"
    fig.savefig(path, dpi=100)
    plt.close(fig)
    frames.append(imageio.imread(path)[:, :, :3])
    print(f"  frame {f + 1}/{TOTAL}", end="\r")

imageio.mimsave(VIDEO, frames, fps=12, codec="libx264", pixelformat="yuv420p")

# ---------------- summary ----------------
print("\n" + "=" * 55)
print("CARBONWISE SIMULATION COMPLETED")
print("=" * 55)
for name, v in metrics.items():
    print(f"\n{name}")
    print(f"  Grid consumption : {v['grid']:.2f} kWh")
    print(f"  Adjusted cost    : {v['cost']:.2f} units")
    print(f"  Adjusted CO2     : {v['emissions']:.2f} kg")
    print(f"  Final battery    : {v['final_battery']:.1f} kWh")
print("\nQAOA-inspired vs baseline (battery-adjusted):")
print(f"  Cost reduction      : {cost_saving:.2f}%")
print(f"  Emissions reduction : {emission_saving:.2f}%")
print(f"\nVideo: {VIDEO}")
print(f"Data : {CSV}")
print("Note: QAOA-inspired is a classical heuristic, not a quantum circuit.")
print("All values are simulated, not VTU's real data.")

# open the video automatically on Windows
if sys.platform.startswith("win"):
    os.startfile(VIDEO)