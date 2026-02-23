import pytest

from qmmm_vqe_biosim.chem.active_space import choose_conservative_active_space


def test_choose_active_space_closed_shell_within_limit():
    a, b, orbitals = choose_conservative_active_space(
        num_spatial_orbitals=10,
        num_alpha=5,
        num_beta=5,
        max_qubits=12,
    )
    assert (a, b, orbitals) == (5, 5, 6)


def test_choose_active_space_preserves_spin_difference_when_possible():
    a, b, orbitals = choose_conservative_active_space(
        num_spatial_orbitals=20,
        num_alpha=10,
        num_beta=8,
        max_qubits=8,
    )
    assert orbitals == 4
    assert (a - b) == 2
    assert 2 * orbitals <= 8


def test_choose_active_space_fallback_when_spin_difference_too_large():
    a, b, orbitals = choose_conservative_active_space(
        num_spatial_orbitals=20,
        num_alpha=10,
        num_beta=0,
        max_qubits=8,
    )
    assert (a, b, orbitals) == (4, 0, 4)


def test_choose_active_space_rejects_too_small_qubit_budget():
    with pytest.raises(ValueError):
        choose_conservative_active_space(
            num_spatial_orbitals=6,
            num_alpha=3,
            num_beta=3,
            max_qubits=1,
        )
