from __future__ import annotations

from typing import Any

from qiskit_algorithms.minimum_eigensolvers import NumPyMinimumEigensolver
from qiskit_nature.second_q.algorithms import GroundStateEigensolver
from qiskit_nature.second_q.drivers import PySCFDriver
from qiskit_nature.second_q.mappers import JordanWignerMapper
from qiskit_nature.units import DistanceUnit


def record_to_atom_string(record: dict[str, Any]) -> str:
    atoms = record["atoms"]
    coords = record["coords_angstrom"]
    if len(atoms) != len(coords):
        raise ValueError("Geometry record has mismatched atoms and coords_angstrom lengths")
    return "; ".join(f"{sym} {x} {y} {z}" for sym, (x, y, z) in zip(atoms, coords, strict=True))


def build_electronic_structure_problem(record: dict[str, Any], basis: str = "sto3g"):
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
    return driver.run()


def solve_ground_state_energy(record: dict[str, Any], basis: str = "sto3g") -> float:
    problem = build_electronic_structure_problem(record=record, basis=basis)
    mapper = JordanWignerMapper()
    solver = NumPyMinimumEigensolver()
    solver.filter_criterion = problem.get_default_filter_criterion()
    gse = GroundStateEigensolver(mapper, solver)
    result = gse.solve(problem)
    return float(result.total_energies[0].real)
