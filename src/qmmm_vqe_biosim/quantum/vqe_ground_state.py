from __future__ import annotations

from time import perf_counter
from typing import Any

import numpy as np
from qiskit import transpile
from qiskit.circuit.library import EfficientSU2
from qiskit_algorithms import VQE, AdaptVQE
from qiskit_algorithms.optimizers import COBYLA, SLSQP, SPSA
from qiskit_nature.second_q.algorithms import GroundStateEigensolver
from qiskit_nature.second_q.algorithms.initial_points import HFInitialPoint
from qiskit_nature.second_q.circuit.library import UCC, UCCSD, HartreeFock
from qiskit_nature.second_q.mappers import BravyiKitaevMapper, JordanWignerMapper, ParityMapper

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import build_electronic_structure_problem
from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.quantum.backend import get_estimator


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


def _remap_initial_point(orig_ansatz, new_ansatz, initial_point: np.ndarray) -> np.ndarray:
    orig_params = list(orig_ansatz.parameters)
    if len(initial_point) != len(orig_params):
        return initial_point

    value_by_param = {
        param: float(val) for param, val in zip(orig_params, initial_point, strict=True)
    }
    value_by_name = {
        param.name: float(val) for param, val in zip(orig_params, initial_point, strict=True)
    }

    mapped: list[float] = []
    for param in new_ansatz.parameters:
        if param in value_by_param:
            mapped.append(value_by_param[param])
        else:
            mapped.append(value_by_name.get(param.name, 0.0))
    return np.asarray(mapped, dtype=float)


def _prepare_isa_inputs(
    ansatz, qubit_op, initial_point: np.ndarray, backend_obj, optimization_level: int | None
):
    level = 1 if optimization_level is None else int(optimization_level)
    ansatz_isa = transpile(ansatz, backend=backend_obj, optimization_level=level)
    initial_point_isa = _remap_initial_point(ansatz, ansatz_isa, initial_point)
    qubit_op_isa = qubit_op
    if hasattr(qubit_op, "apply_layout"):
        qubit_op_isa = qubit_op.apply_layout(ansatz_isa.layout, num_qubits=ansatz_isa.num_qubits)
    return ansatz_isa, qubit_op_isa, initial_point_isa


def _extract_runtime_metadata(raw_result: Any) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {}
    for attr in ("optimizer_time", "optimizer_evals", "cost_function_evals"):
        val = getattr(raw_result, attr, None)
        if val is not None:
            metadata[attr] = val

    optimizer_result = getattr(raw_result, "optimizer_result", None)
    if optimizer_result is not None:
        for attr in ("nfev", "nit", "njev", "fun"):
            val = getattr(optimizer_result, attr, None)
            if val is not None:
                metadata[f"optimizer_result_{attr}"] = val

    return metadata or None


def _problem_dimensions(problem) -> tuple[tuple[int, int], int]:
    num_alpha, num_beta = problem.num_particles
    return (int(num_alpha), int(num_beta)), int(problem.num_spatial_orbitals)


def _build_hf_state(problem, mapper):
    num_particles, num_spatial_orbitals = _problem_dimensions(problem)
    return HartreeFock(
        num_spatial_orbitals=num_spatial_orbitals,
        num_particles=num_particles,
        qubit_mapper=mapper,
    )


def _build_uccsd_ansatz(problem, mapper):
    num_particles, num_spatial_orbitals = _problem_dimensions(problem)
    ansatz = UCCSD(
        num_spatial_orbitals=num_spatial_orbitals,
        num_particles=num_particles,
        qubit_mapper=mapper,
        initial_state=_build_hf_state(problem=problem, mapper=mapper),
    )
    initial_point = HFInitialPoint()
    initial_point.ansatz = ansatz
    initial_point.problem = problem
    return ansatz, np.asarray(initial_point.to_numpy_array(), dtype=float), "uccsd"


def _build_ucc_sd_ansatz(problem, mapper):
    num_particles, num_spatial_orbitals = _problem_dimensions(problem)
    ansatz = UCC(
        num_spatial_orbitals=num_spatial_orbitals,
        num_particles=num_particles,
        excitations=[1, 2],
        qubit_mapper=mapper,
        initial_state=_build_hf_state(problem=problem, mapper=mapper),
    )
    initial_point = HFInitialPoint()
    initial_point.ansatz = ansatz
    initial_point.problem = problem
    return ansatz, np.asarray(initial_point.to_numpy_array(), dtype=float), "ucc"


def _adapt_ansatz_failure(
    *,
    record: str,
    problem,
    active_electrons: int | tuple[int, int] | None,
    active_orbitals: int | list[int] | None,
    uccsd_error: Exception,
    ucc_error: Exception,
) -> RuntimeError:
    num_particles, num_spatial_orbitals = _problem_dimensions(problem)
    return RuntimeError(
        "Failed to construct an ADAPT-compatible UCC ansatz "
        f"(record={record}, num_particles={num_particles}, "
        f"num_spatial_orbitals={num_spatial_orbitals}, "
        f"active_electrons={active_electrons}, active_orbitals={active_orbitals}). "
        f"UCCSD error: {uccsd_error}. "
        f"UCC(singles+doubles) error: {ucc_error}."
    )


def _build_ansatz(
    *,
    problem,
    mapper,
    method: str,
    record: str,
    active_electrons: int | tuple[int, int] | None,
    active_orbitals: int | list[int] | None,
):
    try:
        return _build_uccsd_ansatz(problem=problem, mapper=mapper)
    except Exception as uccsd_exc:
        if method == "adapt_vqe":
            try:
                return _build_ucc_sd_ansatz(problem=problem, mapper=mapper)
            except Exception as ucc_exc:
                raise _adapt_ansatz_failure(
                    record=record,
                    problem=problem,
                    active_electrons=active_electrons,
                    active_orbitals=active_orbitals,
                    uccsd_error=uccsd_exc,
                    ucc_error=ucc_exc,
                ) from ucc_exc

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
    method: str = "vqe",
    mm_charges_path: str | None = None,
    backend: str = "local",
    ibm_backend_name: str | None = None,
    shots: int | None = None,
    resilience_level: int | None = None,
    optimization_level: int | None = None,
    mapper: str = "parity",
    optimizer: str = "slsqp",
    maxiter: int = 200,
    seed: int = 7,
) -> dict[str, Any]:
    np.random.seed(seed)

    geometry = get_structure_record(dataset=dataset, record_id=record)
    problem = build_electronic_structure_problem(
        record=geometry,
        basis=basis,
        mm_charges_path=mm_charges_path,
    )
    return run_vqe_for_problem(
        problem=problem,
        dataset=dataset,
        record=record,
        basis=basis,
        method=method,
        backend=backend,
        ibm_backend_name=ibm_backend_name,
        shots=shots,
        resilience_level=resilience_level,
        optimization_level=optimization_level,
        mapper=mapper,
        optimizer=optimizer,
        maxiter=maxiter,
        seed=seed,
    )


def run_vqe_for_problem(
    problem,
    dataset: str,
    record: str,
    basis: str,
    method: str = "vqe",
    backend: str = "local",
    ibm_backend_name: str | None = None,
    shots: int | None = None,
    resilience_level: int | None = None,
    optimization_level: int | None = None,
    mapper: str = "parity",
    optimizer: str = "slsqp",
    maxiter: int = 200,
    seed: int = 7,
    active_electrons: int | tuple[int, int] | None = None,
    active_orbitals: int | list[int] | None = None,
) -> dict[str, Any]:
    np.random.seed(seed)
    method_key = method.strip().lower()
    if method_key not in {"vqe", "adapt_vqe"}:
        raise ValueError(f"Unsupported method: {method}")

    mapper_obj, mapper_name = _make_mapper(mapper, problem=problem)
    qubit_op = mapper_obj.map(problem.hamiltonian.second_q_op())
    optimizer_obj, optimizer_name = _make_optimizer(optimizer, maxiter=maxiter)
    ansatz, initial_point, ansatz_name = _build_ansatz(
        problem=problem,
        mapper=mapper_obj,
        method=method_key,
        record=record,
        active_electrons=active_electrons,
        active_orbitals=active_orbitals,
    )
    if method_key == "adapt_vqe" and ansatz_name not in {"uccsd", "ucc"}:
        raise RuntimeError("ADAPT-VQE requires a UCC-style ansatz; UCCSD construction failed.")

    estimator_handle = get_estimator(
        backend=backend,
        ibm_backend_name=ibm_backend_name,
        seed=seed,
        shots=shots,
        resilience_level=resilience_level,
        optimization_level=optimization_level,
    )

    try:
        runtime_metadata: dict[str, Any] | None = None

        if estimator_handle.backend_kind == "ibm":
            if estimator_handle.backend_obj is None:
                raise RuntimeError("IBM backend selected but backend object was not initialized.")

            ansatz_isa, qubit_op_isa, initial_point_isa = _prepare_isa_inputs(
                ansatz=ansatz,
                qubit_op=qubit_op,
                initial_point=initial_point,
                backend_obj=estimator_handle.backend_obj,
                optimization_level=optimization_level,
            )

            vqe_solver = VQE(
                estimator=estimator_handle.estimator,
                ansatz=ansatz_isa,
                optimizer=optimizer_obj,
                initial_point=initial_point_isa,
            )
            solver = (
                vqe_solver
                if method_key == "vqe"
                else AdaptVQE(solver=vqe_solver, max_iterations=maxiter)
            )

            start = perf_counter()
            raw_result = solver.compute_minimum_eigenvalue(qubit_op_isa)
            runtime_sec = perf_counter() - start
            energy = float(
                raw_result.eigenvalue.real + problem.hamiltonian.nuclear_repulsion_energy
            )
            runtime_metadata = _extract_runtime_metadata(raw_result)
        else:
            vqe_solver = VQE(
                estimator=estimator_handle.estimator,
                ansatz=ansatz,
                optimizer=optimizer_obj,
                initial_point=initial_point,
            )
            solver = (
                vqe_solver
                if method_key == "vqe"
                else AdaptVQE(solver=vqe_solver, max_iterations=maxiter)
            )

            start = perf_counter()
            gse = GroundStateEigensolver(mapper_obj, solver)
            result = gse.solve(problem)
            runtime_sec = perf_counter() - start
            energy = float(result.total_energies[0].real)
            runtime_metadata = _extract_runtime_metadata(result.raw_result)
    finally:
        estimator_handle.close()

    return {
        "dataset": dataset,
        "record": record,
        "basis": basis,
        "method": method_key,
        "algorithm": method_key,
        "backend": estimator_handle.backend_kind,
        "ibm_backend_name": estimator_handle.ibm_backend_name,
        "shots": shots,
        "resilience_level": resilience_level,
        "optimization_level": optimization_level,
        "runtime_metadata": runtime_metadata,
        "energy": energy,
        "runtime_sec": runtime_sec,
        "ansatz": ansatz_name,
        "optimizer": optimizer_name,
        "mapper": mapper_name,
        "num_qubits": qubit_op.num_qubits,
        "maxiter": maxiter,
        "seed": seed,
    }
