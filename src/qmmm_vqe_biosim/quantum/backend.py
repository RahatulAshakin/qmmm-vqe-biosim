from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class EstimatorHandle:
    estimator: Any
    backend_label: str
    close: Callable[[], None]


def parse_backend_spec(spec: str) -> tuple[str, str | None]:
    key = spec.strip()
    if key == "local":
        return "local", None
    if key.startswith("ibm:"):
        name = key.split(":", 1)[1].strip()
        if not name:
            raise ValueError("Invalid backend spec: use ibm:<backend_name>")
        return "ibm", name
    raise ValueError("Unsupported backend spec. Use 'local' or 'ibm:<backend_name>'.")


def _local_estimator(seed: int = 7) -> EstimatorHandle:
    from qiskit.primitives import BaseEstimatorV2, Estimator, StatevectorEstimator

    # Prefer the canonical Estimator where it is a V2 primitive.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            estimator = Estimator()
        if isinstance(estimator, BaseEstimatorV2):
            return EstimatorHandle(estimator=estimator, backend_label="local", close=lambda: None)
    except Exception:
        pass

    # Qiskit 1.x compatibility path.
    estimator = StatevectorEstimator(seed=seed)
    return EstimatorHandle(estimator=estimator, backend_label="local", close=lambda: None)


def _ibm_estimator(
    backend_name: str,
    shots: int | None,
    resilience_level: int | None,
    optimization_level: int | None,
) -> EstimatorHandle:
    try:
        from qiskit_ibm_runtime import EstimatorV2, QiskitRuntimeService, Session
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
        session = Session(backend=backend)
        estimator = EstimatorV2(mode=session, options=(options or None))
    except Exception as exc:
        raise RuntimeError(
            "IBM backend requested but IBM Runtime initialization failed. "
            "Configure credentials first, e.g. "
            "QiskitRuntimeService.save_account(channel='ibm_quantum', token='YOUR_TOKEN', overwrite=True)."
        ) from exc

    return EstimatorHandle(
        estimator=estimator,
        backend_label=f"ibm:{backend_name}",
        close=session.close,
    )


def get_estimator(
    backend: str = "local",
    *,
    seed: int = 7,
    shots: int | None = None,
    resilience_level: int | None = None,
    optimization_level: int | None = None,
) -> EstimatorHandle:
    kind, name = parse_backend_spec(backend)
    if kind == "local":
        return _local_estimator(seed=seed)
    assert name is not None
    return _ibm_estimator(
        backend_name=name,
        shots=shots,
        resilience_level=resilience_level,
        optimization_level=optimization_level,
    )
