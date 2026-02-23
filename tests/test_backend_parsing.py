import pytest

from qmmm_vqe_biosim.quantum.backend import parse_backend_spec


def test_parse_backend_local():
    assert parse_backend_spec("local") == ("local", None)


def test_parse_backend_ibm_named():
    assert parse_backend_spec("ibm:ibm_kyoto") == ("ibm", "ibm_kyoto")


def test_parse_backend_invalid():
    with pytest.raises(ValueError):
        parse_backend_spec("ibm:")
    with pytest.raises(ValueError):
        parse_backend_spec("foo")
