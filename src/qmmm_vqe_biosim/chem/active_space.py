from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Any

import numpy as np


@dataclass(frozen=True)
class AutoActiveSpaceSelection:
    method: str
    active_electrons: int | tuple[int, int]
    active_orbitals: int | list[int]
    selected_orbitals: list[int] | None = None
    occupations: list[float] | None = None
    metadata: dict[str, Any] | None = None


def choose_conservative_active_space(
    num_spatial_orbitals: int,
    num_alpha: int,
    num_beta: int,
    max_qubits: int,
) -> tuple[int, int, int]:
    """
    Choose a conservative active space that fits the qubit budget.

    Returns:
      (active_num_alpha, active_num_beta, active_orbitals)

    Rule:
      2 * active_orbitals <= max_qubits
    """

    if num_spatial_orbitals < 1:
        raise ValueError("num_spatial_orbitals must be >= 1")
    if num_alpha < 0 or num_beta < 0:
        raise ValueError("num_alpha and num_beta must be >= 0")
    if max_qubits < 2:
        raise ValueError("max_qubits must be >= 2")

    max_active_orbitals = min(num_spatial_orbitals, max_qubits // 2)
    if max_active_orbitals < 1:
        raise ValueError("No active orbitals can fit within max_qubits")

    delta = num_alpha - num_beta
    total = num_alpha + num_beta

    # Preserve spin difference when possible.
    if abs(delta) <= max_active_orbitals:
        max_total_with_delta = 2 * max_active_orbitals - abs(delta)
        target_total = min(total, max_total_with_delta)

        # Ensure target_total has parity compatible with alpha-beta split.
        if (target_total - abs(delta)) % 2 != 0:
            target_total -= 1
        if target_total < abs(delta):
            target_total = abs(delta)

        active_alpha = (target_total + delta) // 2
        active_beta = target_total - active_alpha

        if 0 <= active_alpha <= max_active_orbitals and 0 <= active_beta <= max_active_orbitals:
            return active_alpha, active_beta, max_active_orbitals

    # Fallback when preserving spin difference is not possible.
    active_alpha = min(num_alpha, max_active_orbitals)
    active_beta = min(num_beta, max_active_orbitals)
    return active_alpha, active_beta, max_active_orbitals


def orbital_entropy_proxy(occupation: float) -> float:
    p = float(np.clip(occupation / 2.0, 0.0, 1.0))
    if p <= 1e-12 or p >= 1 - 1e-12:
        return 0.0
    return -(p * log(p) + (1.0 - p) * log(1.0 - p))


def orbital_entropy_scores(occupations: np.ndarray) -> np.ndarray:
    return np.asarray([orbital_entropy_proxy(val) for val in occupations], dtype=float)


def _bounded_max_orbitals(
    *,
    num_spatial_orbitals: int,
    max_qubits: int,
    max_orbitals: int | None,
) -> int:
    if max_qubits < 2:
        raise ValueError("max_qubits must be >= 2")
    qubit_limited = min(num_spatial_orbitals, max_qubits // 2)
    if qubit_limited < 1:
        raise ValueError("No active orbitals fit under max_qubits")
    if max_orbitals is None:
        return qubit_limited
    if max_orbitals < 1:
        raise ValueError("auto_active_space_max_orbitals must be >= 1 when provided")
    return min(qubit_limited, max_orbitals)


def _active_electrons_from_occupations(
    occupations: np.ndarray,
    selected_orbitals: list[int],
    *,
    require_even: bool,
) -> int:
    if not selected_orbitals:
        raise ValueError("selected_orbitals cannot be empty")

    total_occ = float(np.sum(occupations[selected_orbitals]))
    if require_even:
        electrons = int(2 * round(total_occ / 2.0))
    else:
        electrons = int(round(total_occ))

    max_electrons = 2 * len(selected_orbitals)
    electrons = max(0, min(max_electrons, electrons))
    if electrons == 0:
        electrons = min(2, max_electrons) if require_even else 1
    if require_even and electrons % 2 != 0:
        electrons = max(0, electrons - 1)
    return electrons


def select_uno_cas_orbitals(
    occupations: np.ndarray,
    *,
    occ_min: float = 0.02,
    occ_max: float = 1.98,
    max_orbitals: int | None = None,
) -> list[int]:
    if occ_min > occ_max:
        raise ValueError("occ_min must be <= occ_max")
    if max_orbitals is not None and max_orbitals < 1:
        raise ValueError("max_orbitals must be >= 1 when provided")

    selected = [
        idx for idx, occ in enumerate(occupations.tolist()) if occ_min <= float(occ) <= occ_max
    ]

    if max_orbitals is not None and len(selected) > max_orbitals:
        entropy = orbital_entropy_scores(occupations)
        selected = sorted(
            sorted(selected, key=lambda idx: (-float(entropy[idx]), idx))[:max_orbitals]
        )
    return selected


def select_occ_entropy_orbitals(occupations: np.ndarray, *, top_k: int) -> list[int]:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    top_k = min(top_k, occupations.size)
    entropy = orbital_entropy_scores(occupations)
    ranked = sorted(range(occupations.size), key=lambda idx: (-float(entropy[idx]), idx))
    return sorted(ranked[:top_k])


def _record_to_pyscf_atom(record: dict[str, Any]) -> list[tuple[str, tuple[float, float, float]]]:
    atoms = record.get("atoms")
    coords = record.get("coords_angstrom")
    if not isinstance(atoms, list) or not isinstance(coords, list):
        raise ValueError("record must contain atoms and coords_angstrom lists")
    if len(atoms) != len(coords):
        raise ValueError("record has mismatched atoms and coords_angstrom lengths")

    pairs: list[tuple[str, tuple[float, float, float]]] = []
    for symbol, xyz in zip(atoms, coords, strict=True):
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise ValueError("coords_angstrom entries must be [x, y, z]")
        pairs.append((str(symbol), (float(xyz[0]), float(xyz[1]), float(xyz[2]))))
    return pairs


def natural_occupations_uhf(
    record: dict[str, Any],
    basis: str,
    *,
    max_cycle: int = 100,
    conv_tol: float = 1e-9,
) -> np.ndarray:
    from pyscf import gto, scf

    charge = int(record.get("charge") or 0)
    multiplicity = int(record.get("multiplicity") or 1)
    spin = multiplicity - 1

    mol = gto.M(
        atom=_record_to_pyscf_atom(record),
        basis=basis,
        charge=charge,
        spin=spin,
        unit="Angstrom",
        verbose=0,
    )
    mf = scf.UHF(mol)
    mf.max_cycle = int(max_cycle)
    mf.conv_tol = float(conv_tol)
    mf.kernel()
    if not mf.converged:
        rec_id = record.get("record_id", "<unknown>")
        raise RuntimeError(f"UHF did not converge for record={rec_id}, basis={basis}")

    dm_alpha, dm_beta = mf.make_rdm1()
    overlap = mol.intor_symmetric("int1e_ovlp")
    eigvals, eigvecs = np.linalg.eigh(overlap)
    eigvals = np.clip(np.real_if_close(eigvals), 1e-12, None)
    s_half = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T

    density = s_half @ (dm_alpha + dm_beta) @ s_half
    density = 0.5 * (density + density.T)
    occupations, _ = np.linalg.eigh(density)
    occupations = np.asarray(np.real_if_close(occupations), dtype=float)
    occupations = np.clip(occupations, 0.0, 2.0)
    occupations = np.sort(occupations)[::-1]
    return occupations


def _default_valence_shells(symbol: str) -> list[str]:
    sym = symbol.capitalize()
    if sym in {"H", "He"}:
        return ["1s"]
    if sym in {"Li", "Be", "B", "C", "N", "O", "F", "Ne"}:
        return ["2s", "2p"]
    if sym in {"Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar"}:
        return ["3s", "3p"]
    return ["2s", "2p"]


def build_avas_ao_labels_from_atoms(record: dict[str, Any], atom_indices: list[int]) -> list[str]:
    atoms = record.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        raise ValueError("record must contain atoms for AVAS atom-based selection")
    labels: list[str] = []
    for idx in atom_indices:
        if idx < 0 or idx >= len(atoms):
            raise ValueError(f"AVAS atom index out of range: {idx}")
        symbol = str(atoms[idx])
        for shell in _default_valence_shells(symbol):
            labels.append(f"{idx} {symbol} {shell}")
    if not labels:
        raise ValueError("No AVAS AO labels were generated")
    return labels


def _avas_subspace_size(
    record: dict[str, Any],
    basis: str,
    *,
    ao_labels: list[str],
    max_cycle: int = 100,
    conv_tol: float = 1e-9,
) -> tuple[int, int]:
    from pyscf import gto, scf
    from pyscf.mcscf import avas

    charge = int(record.get("charge") or 0)
    multiplicity = int(record.get("multiplicity") or 1)
    spin = multiplicity - 1

    mol = gto.M(
        atom=_record_to_pyscf_atom(record),
        basis=basis,
        charge=charge,
        spin=spin,
        unit="Angstrom",
        verbose=0,
    )
    if spin == 0:
        mf = scf.RHF(mol)
    else:
        mf = scf.ROHF(mol)
    mf.max_cycle = int(max_cycle)
    mf.conv_tol = float(conv_tol)
    mf.kernel()
    if not mf.converged:
        rec_id = record.get("record_id", "<unknown>")
        raise RuntimeError(f"SCF did not converge for AVAS record={rec_id}, basis={basis}")

    ncas, nelecas, _ = avas.avas(mf, ao_labels)
    n_orbitals = int(ncas)
    if isinstance(nelecas, tuple):
        n_electrons = int(sum(int(v) for v in nelecas))
    else:
        n_electrons = int(nelecas)
    return n_orbitals, n_electrons


def choose_auto_active_space(
    *,
    problem,
    record: dict[str, Any],
    basis: str,
    max_qubits: int,
    method: str = "heuristic",
    max_orbitals: int | None = None,
    occ_min: float = 0.02,
    occ_max: float = 1.98,
    avas_ao_labels: list[str] | None = None,
    avas_atoms: list[int] | None = None,
) -> AutoActiveSpaceSelection:
    method_key = method.strip().lower()
    if method_key not in {"heuristic", "uno_cas", "occ_entropy", "avas"}:
        raise ValueError(f"Unsupported auto-active-space method: {method}")

    num_alpha, num_beta = problem.num_particles
    num_spatial_orbitals = int(problem.num_spatial_orbitals)
    orbital_budget = _bounded_max_orbitals(
        num_spatial_orbitals=num_spatial_orbitals,
        max_qubits=max_qubits,
        max_orbitals=max_orbitals,
    )

    if method_key == "heuristic":
        effective_max_qubits = 2 * orbital_budget
        a, b, norb = choose_conservative_active_space(
            num_spatial_orbitals=num_spatial_orbitals,
            num_alpha=int(num_alpha),
            num_beta=int(num_beta),
            max_qubits=effective_max_qubits,
        )
        return AutoActiveSpaceSelection(
            method="heuristic",
            active_electrons=(a, b),
            active_orbitals=norb,
            selected_orbitals=list(range(norb)),
        )

    if method_key in {"uno_cas", "occ_entropy"}:
        occupations = natural_occupations_uhf(record=record, basis=basis)
        if occupations.size != num_spatial_orbitals:
            raise RuntimeError(
                "Natural occupations size mismatch: "
                f"{occupations.size} != {num_spatial_orbitals}"
            )

        if method_key == "uno_cas":
            selected = select_uno_cas_orbitals(
                occupations,
                occ_min=occ_min,
                occ_max=occ_max,
                max_orbitals=orbital_budget,
            )
            if not selected:
                rec_id = record.get("record_id", "<unknown>")
                raise RuntimeError(
                    "UNO-CAS selected no orbitals. "
                    f"record={rec_id}, occ_min={occ_min}, occ_max={occ_max}, "
                    f"max_orbitals={orbital_budget}"
                )
            electrons = _active_electrons_from_occupations(
                occupations, selected, require_even=False
            )
            return AutoActiveSpaceSelection(
                method="uno_cas",
                active_electrons=electrons,
                active_orbitals=selected,
                selected_orbitals=selected,
                occupations=[float(v) for v in occupations.tolist()],
            )

        selected = select_occ_entropy_orbitals(occupations, top_k=orbital_budget)
        electrons = _active_electrons_from_occupations(occupations, selected, require_even=True)
        return AutoActiveSpaceSelection(
            method="occ_entropy",
            active_electrons=electrons,
            active_orbitals=selected,
            selected_orbitals=selected,
            occupations=[float(v) for v in occupations.tolist()],
        )

    labels = avas_ao_labels
    if labels is None:
        if avas_atoms is None:
            raise ValueError(
                "AVAS selection requires either avas_ao_labels or avas_atoms to be provided."
            )
        labels = build_avas_ao_labels_from_atoms(record, avas_atoms)
    if not labels:
        raise ValueError("AVAS AO labels cannot be empty.")

    n_orbitals, n_electrons = _avas_subspace_size(record=record, basis=basis, ao_labels=labels)
    n_orbitals = min(n_orbitals, orbital_budget)
    if n_orbitals < 1:
        raise RuntimeError("AVAS selected zero orbitals after applying orbital budget.")
    n_electrons = max(1, min(2 * n_orbitals, n_electrons))
    return AutoActiveSpaceSelection(
        method="avas",
        active_electrons=n_electrons,
        active_orbitals=n_orbitals,
        selected_orbitals=None,
        occupations=None,
        metadata={"ao_labels": labels},
    )
