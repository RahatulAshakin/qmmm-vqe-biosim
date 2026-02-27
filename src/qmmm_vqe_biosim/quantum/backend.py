from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class EstimatorHandle:
    estimator: Any
    backend_kind: str
    ibm_backend_name: str | None
    backend_obj: Any | None
    close: Callable[[], None]


@dataclass(frozen=True)
class BackendConfig:
    backend: str
    ibm_backend_name: str | None


def build_backend_config(
    backend: str = "local",
    ibm_backend_name: str | None = None,
) -> BackendConfig:
    key = backend.strip().lower()
    name = ibm_backend_name.strip() if ibm_backend_name is not None else None

    # Backward-compat path for existing programmatic callers.
    if key.startswith("ibm:"):
        parsed = key.split(":", 1)[1].strip()
        if not parsed:
            raise ValueError("Invalid backend spec: use --backend ibm --ibm-backend <name>")
        if name is not None and name != parsed:
            raise ValueError("Conflicting IBM backend names provided")
        key = "ibm"
        name = parsed

    if key not in {"local", "ibm"}:
        raise ValueError("Unsupported backend. Use 'local' or 'ibm'.")
    if key == "ibm" and not name:
        raise ValueError("IBM backend requested: provide --ibm-backend <backend_name>.")
    if key == "local":
        name = None
    return BackendConfig(backend=key, ibm_backend_name=name)


def _local_estimator(seed: int = 7) -> EstimatorHandle:
    from qiskit.primitives import BaseEstimatorV2, Estimator, StatevectorEstimator

    # Prefer the canonical Estimator where it is a V2 primitive.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            estimator = Estimator()
        if isinstance(estimator, BaseEstimatorV2):
            return EstimatorHandle(
                estimator=estimator,
                backend_kind="local",
                ibm_backend_name=None,
                backend_obj=None,
                close=lambda: None,
            )
    except Exception:
        pass

    # Qiskit 1.x compatibility path.
    estimator = StatevectorEstimator(seed=seed)
    return EstimatorHandle(
        estimator=estimator,
        backend_kind="local",
        ibm_backend_name=None,
        backend_obj=None,
        close=lambda: None,
    )


def _ibm_estimator(
    backend_name: str,
    shots: int | None,
    resilience_level: int | None,
    optimization_level: int | None,
) -> EstimatorHandle:
    try:
        from qiskit_ibm_runtime import Estimator, QiskitRuntimeService
    except Exception as exc:
        raise RuntimeError(
            "IBM backend requested, but qiskit-ibm-runtime is unavailable. "
            "Install it and configure IBM Quantum credentials."
        ) from exc

    options: dict[str, Any] = {}
    if shots is not None:
        options["default_shots"] = shots
    if resilience_level is not None:
        options["resilience_level"] = resilience_level
    if optimization_level is not None:
        options.setdefault("experimental", {})
        options["experimental"]["optimization_level"] = optimization_level

    try:
        service = QiskitRuntimeService()
        backend = service.backend(backend_name)
        # Job mode (no explicit Session required)
        estimator = Estimator(mode=backend, options=(options or None))
    except Exception as exc:
        raise RuntimeError(
            "IBM backend requested but IBM Runtime initialization failed. "
            "Configure credentials first, e.g. "
            "QiskitRuntimeService.save_account(channel='ibm_quantum', token='YOUR_TOKEN', overwrite=True)."
        ) from exc

    return EstimatorHandle(
        estimator=estimator,
        backend_kind="ibm",
        ibm_backend_name=backend_name,
        backend_obj=backend,
        close=lambda: None,
    )


def get_estimator(
    backend: str = "local",
    ibm_backend_name: str | None = None,
    *,
    seed: int = 7,
    shots: int | None = None,
    resilience_level: int | None = None,
    optimization_level: int | None = None,
) -> EstimatorHandle:
    cfg = build_backend_config(backend=backend, ibm_backend_name=ibm_backend_name)
    if cfg.backend == "local":
        return _local_estimator(seed=seed)
    assert cfg.ibm_backend_name is not None
    return _ibm_estimator(
        backend_name=cfg.ibm_backend_name,
        shots=shots,
        resilience_level=resilience_level,
        optimization_level=optimization_level,
    )
