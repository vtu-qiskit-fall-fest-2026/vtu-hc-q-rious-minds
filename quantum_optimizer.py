"""Small Qiskit QAOA demo for CarbonWise.

This deliberately solves a tractable 4-decision subproblem: select exactly two
of four candidate evening time slots for a fixed battery discharge. The energy
inputs are illustrative, not measured VTU data. The QAOA circuit is evaluated
with Qiskit's local statevector simulator; no quantum hardware is used.
"""
from __future__ import annotations

from typing import Any

import numpy as np


GRID_EMISSIONS_KG_PER_KWH = 0.70  # illustrative assumption; replace with a verified factor
DISCHARGE_LIMIT_KWH = 5.0
NUM_SELECTED_SLOTS = 2


def _bits_from_integer(index: int, n: int) -> np.ndarray:
    """Return binary decisions in Qiskit little-endian qubit order."""
    return np.asarray([(index >> qubit) & 1 for qubit in range(n)], dtype=int)


def run_qaoa_optimization(
    energy_data: dict[str, Any] | None = None,
    *,
    shots: int = 4096,
    seed: int = 21,
    maxiter: int = 60,
) -> dict[str, Any]:
    """Run a real small QAOA circuit and return a JSON-serializable result.

    The selected periods are the final four time slots with positive grid import.
    For each selected slot, the model can discharge up to 5 kWh (capped by that
    slot's grid import). Exactly two slots are selected; the objective minimizes
    grid-purchase cost over those four periods. A classical exhaustive search
    over the 16 bitstrings supplies an exact tiny-instance benchmark.
    """
    try:
        from qiskit import QuantumCircuit
        from qiskit.circuit.library import DiagonalGate
        from qiskit.quantum_info import Statevector
        from scipy.optimize import minimize
    except ImportError as exc:
        raise RuntimeError(
            "Qiskit or SciPy is not installed. In the active VS Code terminal, "
            "run: python -m pip install -r requirements.txt"
        ) from exc

    if energy_data is None:
        from energy_data import get_energy_data
        energy_data = get_energy_data()

    hours = list(energy_data["hours"])
    prices = np.asarray(energy_data["price"], dtype=float)
    grid = np.asarray(energy_data["grid"], dtype=float)
    if not (len(hours) == len(prices) == len(grid)):
        raise ValueError("Energy hours, prices, and grid arrays must have equal lengths.")

    # Use the final four periods with positive grid import, so discharge actions
    # represent avoided grid purchases instead of unsupported exports.
    candidates = [i for i, value in enumerate(grid) if value > 0]
    candidates = candidates[-4:]
    if len(candidates) < 4:
        # If the input is sparse, use the final four periods and let the model
        # cap each discharge by the import available in that period.
        candidates = list(range(max(0, len(hours) - 4), len(hours)))
    if len(candidates) != 4:
        raise ValueError("QAOA demo requires at least four hourly energy records.")

    slot_hours = [str(hours[i]) for i in candidates]
    slot_prices = prices[candidates]
    slot_grid = np.maximum(grid[candidates], 0.0)
    discharge_kwh = np.minimum(DISCHARGE_LIMIT_KWH, slot_grid)
    savings = slot_prices * discharge_kwh

    if not np.any(savings > 0):
        raise ValueError("No positive grid-import savings are available in the selected slots.")

    n = len(candidates)
    all_indices = list(range(2**n))
    assignments = {idx: _bits_from_integer(idx, n) for idx in all_indices}

    # QUBO objective: maximize avoided energy cost, with a large penalty for
    # anything other than exactly two selected discharge slots.
    penalty = float(max(10.0 * np.sum(np.abs(savings)), 100.0))
    raw_costs = np.asarray([
        -float(np.dot(savings, assignments[idx]))
        + penalty * (int(np.sum(assignments[idx])) - NUM_SELECTED_SLOTS) ** 2
        for idx in all_indices
    ], dtype=float)
    scale = max(float(np.max(np.abs(raw_costs))), 1.0)
    scaled_costs = raw_costs / scale

    def probabilities_for(parameters: np.ndarray) -> np.ndarray:
        qc = QuantumCircuit(n)
        qc.h(range(n))
        gamma = float(parameters[0])
        beta = float(parameters[1])
        # Phase separator for the diagonal QUBO cost Hamiltonian.
        diagonal = np.exp(-1j * gamma * scaled_costs)
        qc.append(DiagonalGate(diagonal.tolist()), list(range(n)))
        # Standard QAOA X-mixer layer.
        for qubit in range(n):
            qc.rx(2.0 * beta, qubit)
        state = Statevector.from_instruction(qc)
        return np.asarray(state.probabilities(), dtype=float)

    def expected_energy(parameters: np.ndarray) -> float:
        return float(np.dot(probabilities_for(parameters), scaled_costs))

    fit = minimize(
        expected_energy,
        x0=np.asarray([0.65, 0.45], dtype=float),
        method="COBYLA",
        options={"maxiter": int(maxiter), "rhobeg": 0.45, "tol": 1e-3},
    )
    probs = probabilities_for(fit.x)
    probs = np.clip(probs, 0.0, None)
    probs /= probs.sum()

    # Simulate finite shots from the QAOA statevector, then post-process observed
    # samples. Report the best feasible measured bitstring, not an asserted
    # quantum advantage. The exact classical optimum is calculated separately.
    rng = np.random.default_rng(seed)
    sampled = rng.choice(len(probs), size=max(100, int(shots)), p=probs)
    counts = np.bincount(sampled, minlength=len(probs))
    feasible = [
        idx for idx in all_indices
        if int(np.sum(assignments[idx])) == NUM_SELECTED_SLOTS and counts[idx] > 0
    ]
    if feasible:
        qaoa_idx = min(feasible, key=lambda idx: (raw_costs[idx], -int(counts[idx])))
        observed_feasible = True
    else:
        feasible_all = [
            idx for idx in all_indices
            if int(np.sum(assignments[idx])) == NUM_SELECTED_SLOTS
        ]
        qaoa_idx = max(feasible_all, key=lambda idx: probs[idx])
        observed_feasible = False

    classical_feasible = [
        idx for idx in all_indices
        if int(np.sum(assignments[idx])) == NUM_SELECTED_SLOTS
    ]
    classical_idx = min(classical_feasible, key=lambda idx: raw_costs[idx])
    qaoa_bits = assignments[qaoa_idx]
    classical_bits = assignments[classical_idx]

    baseline_cost = float(np.dot(slot_grid, slot_prices))
    baseline_grid_total = float(np.sum(slot_grid))
    baseline_emissions = baseline_grid_total * GRID_EMISSIONS_KG_PER_KWH

    def metrics(bits: np.ndarray) -> dict[str, Any]:
        discharged = discharge_kwh * bits
        remaining_grid = np.maximum(slot_grid - discharged, 0.0)
        cost = float(np.dot(remaining_grid, slot_prices))
        grid_total = float(np.sum(remaining_grid))
        emissions = grid_total * GRID_EMISSIONS_KG_PER_KWH
        reduction = (100.0 * (baseline_cost - cost) / baseline_cost) if baseline_cost else 0.0
        return {
            "cost_inr": round(cost, 2),
            "grid_kwh": round(grid_total, 2),
            "emissions_kg": round(emissions, 2),
            "cost_saving_pct": round(reduction, 2),
            "selected_hours": [slot_hours[i] for i, bit in enumerate(bits) if bit],
        }

    qaoa_metrics = metrics(qaoa_bits)
    classical_metrics = metrics(classical_bits)
    optimized_grid_profile = grid.copy()
    for j, index in enumerate(candidates):
        if qaoa_bits[j]:
            optimized_grid_profile[index] = max(0.0, grid[index] - discharge_kwh[j])

    rows = []
    for j, index in enumerate(candidates):
        rows.append({
            "hour": slot_hours[j],
            "grid_price_inr_per_kwh": round(float(slot_prices[j]), 2),
            "grid_before_kwh": round(float(slot_grid[j]), 2),
            "planned_discharge_kwh": round(float(discharge_kwh[j]), 2),
            "qaoa_selected": bool(qaoa_bits[j]),
            "classical_selected": bool(classical_bits[j]),
            "grid_after_qaoa_kwh": round(float(optimized_grid_profile[index]), 2),
            "qaoa_candidate_sample_count": int(counts[qaoa_idx]),
        })

    return {
        "success": True,
        "method": "QAOA (Qiskit QuantumCircuit + local Statevector simulation)",
        "model": "4 binary decisions; choose exactly 2 discharge slots; up to 5 kWh per selected slot, limited by grid import.",
        "n_qubits": n,
        "qaoa_layers": 1,
        "shots": max(100, int(shots)),
        "optimizer_success": bool(fit.success),
        "observed_feasible_sample": observed_feasible,
        "baseline": {
            "cost_inr": round(baseline_cost, 2),
            "grid_kwh": round(baseline_grid_total, 2),
            "emissions_kg": round(baseline_emissions, 2),
        },
        "qaoa": qaoa_metrics,
        "classical_exact": classical_metrics,
        "qaoa_matches_classical_optimum": bool(qaoa_metrics["selected_hours"] == classical_metrics["selected_hours"]),
        "schedule": rows,
        "optimized_grid_profile": [round(float(v), 3) for v in optimized_grid_profile],
        "data_note": "Simulated energy data; emissions use an illustrative 0.70 kg CO2/kWh factor. Local statevector simulation, not quantum hardware.",
    }

