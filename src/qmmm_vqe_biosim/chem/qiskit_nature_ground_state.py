from __future__ import annotations

from pathlib import Path
from typing import Any

from qiskit_algorithms.minimum_eigensolvers import NumPyMinimumEigensolver
from qiskit_nature.second_q.algorithms import GroundStateEigensolver
from qiskit_nature.second_q.drivers import PySCFDriver
from qiskit_nature.second_q.mappers import JordanWignerMapper
from qiskit_nature.units import DistanceUnit

from qmmm_vqe_biosim.qmmm.charges import load_mm_charges_csv


def record_to_atom_string(record: dict[str, Any]) -> str:
    atoms = record["atoms"]
    coords = record["coords_angstrom"]
    if len(atoms) != len(coords):
        raise ValueError("Geometry record has mismatched atoms and coords_angstrom lengths")
    return "; ".join(f"{sym} {x} {y} {z}" for sym, (x, y, z) in zip(atoms, coords, strict=True))


def _run_pyscf_with_mm_charges(
    driver: PySCFDriver, coords: list[list[float]], charges: list[float]
) -> None:
    # pylint: disable=import-error
    from pyscf import dft, qmmm, scf

    driver._build_molecule()  # type: ignore[attr-defined]
    method_name = driver.method.value.upper()
    method_cls = getattr(scf, method_name)
    driver._calc = method_cls(driver._mol)  # type: ignore[attr-defined]

    if method_name in ("RKS", "ROKS", "UKS"):
        driver._calc._numint.libxc = getattr(dft, driver.xcf_library)  # type: ignore[attr-defined]
        driver._calc.xc = driver.xc_functional  # type: ignore[attr-defined]

    driver._calc = qmmm.mm_charge(  # type: ignore[attr-defined]
        driver._calc, coords, charges, unit="Angstrom"  # type: ignore[attr-defined]
    )
    driver._calc.conv_tol = driver._conv_tol  # type: ignore[attr-defined]
    driver._calc.max_cycle = driver._max_cycle  # type: ignore[attr-defined]
    driver._calc.init_guess = driver._init_guess  # type: ignore[attr-defined]
    driver._calc.kernel()  # type: ignore[attr-defined]


def build_electronic_structure_problem(
    record: dict[str, Any],
    basis: str = "sto3g",
    mm_charges_path: str | Path | None = None,
):
    charge = int(record.get("charge") or 0)
    multiplicity = int(record.get("multiplicity") or 1)
    spin = multiplicity - 1
    atom = record_to_atom_string(record)

    driver = PySCFDriver(
        atom=atom,
        basis=basis,
        charge=charge,
        spin=spin,
        unit=DistanceUnit.ANGSTROM,
    )
    if mm_charges_path is None:
        return driver.run()

    mm_coords, mm_charges = load_mm_charges_csv(mm_charges_path)
    _run_pyscf_with_mm_charges(driver, mm_coords, mm_charges)
    return driver.to_problem()


def solve_ground_state_energy(
    record: dict[str, Any],
    basis: str = "sto3g",
    mm_charges_path: str | Path | None = None,
) -> float:
    problem = build_electronic_structure_problem(
        record=record,
        basis=basis,
        mm_charges_path=mm_charges_path,
    )
    mapper = JordanWignerMapper()
    solver = NumPyMinimumEigensolver()
    solver.filter_criterion = problem.get_default_filter_criterion()
    gse = GroundStateEigensolver(mapper, solver)
    result = gse.solve(problem)
    return float(result.total_energies[0].real)
