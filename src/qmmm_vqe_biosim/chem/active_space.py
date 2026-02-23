from __future__ import annotations


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
