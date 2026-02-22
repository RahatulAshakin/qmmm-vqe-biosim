from __future__ import annotations

from time import perf_counter
from typing import Any

import numpy as np
from qiskit.circuit.library import EfficientSU2
from qiskit.primitives import StatevectorEstimator
from qiskit_algorithms import VQE
from qiskit_algorithms.optimizers import COBYLA, SLSQP, SPSA
from qiskit_nature.second_q.algorithms import GroundStateEigensolver
from qiskit_nature.second_q.algorithms.initial_points import HFInitialPoint
from qiskit_nature.second_q.circuit.library import UCCSD, HartreeFock
from qiskit_nature.second_q.mappers import BravyiKitaevMapper, JordanWignerMapper, ParityMapper

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import build_electronic_structure_problem
from qmmm_vqe_biosim.datasets.io import get_structure_record


def _make_mapper(name: str, problem):
    key = name.strip().lower()
    if key in {"parity", "p"}:
        return ParityMapper(num_particles=problem.num_particles), "parity"
    if key in {"jw", "jordan_wigner", "jordan-wigner"}:
        return JordanWignerMapper(), "jordan_wigner"
    if key in {"bk", "bravyi_kitaev", "bravyi-kitaev"}:
        return BravyiKitaevMapper(), "bravyi_kitaev"
    raise ValueError(f"Unsupported mapper: {name}")


def _make_optimizer(name: str, maxiter: int):
    key = name.strip().lower()
    if key == "slsqp":
        return SLSQP(maxiter=maxiter), "slsqp"
    if key == "cobyla":
        return COBYLA(maxiter=maxiter), "cobyla"
    if key == "spsa":
        return SPSA(maxiter=maxiter, learning_rate=0.05, perturbation=0.1, last_avg=1), "spsa"
    raise ValueError(f"Unsupported optimizer: {name}")


def _build_ansatz(problem, mapper):
    try:
        hf_state = HartreeFock(
            num_spatial_orbitals=problem.num_spatial_orbitals,
            num_particles=problem.num_particles,
            qubit_mapper=mapper,
        )
        ansatz = UCCSD(
            num_spatial_orbitals=problem.num_spatial_orbitals,
            num_particles=problem.num_particles,
            qubit_mapper=mapper,
            initial_state=hf_state,
        )
        initial_point = HFInitialPoint()
        initial_point.ansatz = ansatz
        initial_point.problem = problem
        return ansatz, np.asarray(initial_point.to_numpy_array(), dtype=float), "uccsd"
    except Exception:
        qubit_op = mapper.map(problem.hamiltonian.second_q_op())
        ansatz = EfficientSU2(
            num_qubits=qubit_op.num_qubits,
            su2_gates=["ry", "rz"],
            entanglement="linear",
            reps=1,
        )
        initial_point = np.zeros(ansatz.num_parameters, dtype=float)
        return ansatz, initial_point, "efficient_su2"


def run_vqe_ground_state(
    dataset: str,
    record: str,
    basis: str,
    mapper: str = "parity",
    optimizer: str = "slsqp",
    maxiter: int = 200,
    seed: int = 7,
) -> dict[str, Any]:
    np.random.seed(seed)

    geometry = get_structure_record(dataset=dataset, record_id=record)
    problem = build_electronic_structure_problem(record=geometry, basis=basis)
    mapper_obj, mapper_name = _make_mapper(mapper, problem=problem)
    qubit_op = mapper_obj.map(problem.hamiltonian.second_q_op())
    optimizer_obj, optimizer_name = _make_optimizer(optimizer, maxiter=maxiter)
    ansatz, initial_point, ansatz_name = _build_ansatz(problem=problem, mapper=mapper_obj)

    estimator = StatevectorEstimator(seed=seed)
    vqe = VQE(
        estimator=estimator,
        ansatz=ansatz,
        optimizer=optimizer_obj,
        initial_point=initial_point,
    )
    vqe.filter_criterion = problem.get_default_filter_criterion()

    start = perf_counter()
    gse = GroundStateEigensolver(mapper_obj, vqe)
    result = gse.solve(problem)
    runtime_sec = perf_counter() - start
    energy = float(result.total_energies[0].real)

    return {
        "dataset": dataset,
        "record": record,
        "basis": basis,
        "method": "vqe",
        "energy": energy,
        "runtime_sec": runtime_sec,
        "ansatz": ansatz_name,
        "optimizer": optimizer_name,
        "mapper": mapper_name,
        "num_qubits": qubit_op.num_qubits,
        "maxiter": maxiter,
        "seed": seed,
    }
