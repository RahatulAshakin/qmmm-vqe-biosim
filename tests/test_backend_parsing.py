import pytest

from qmmm_vqe_biosim.quantum.backend import build_backend_config


def test_parse_backend_local():
    cfg = build_backend_config("local")
    assert cfg.backend == "local"
    assert cfg.ibm_backend_name is None


def test_build_backend_ibm_with_flag_pair():
    cfg = build_backend_config("ibm", "ibm_kyoto")
    assert cfg.backend == "ibm"
    assert cfg.ibm_backend_name == "ibm_kyoto"


def test_build_backend_backward_compat_ibm_colon_spec():
    cfg = build_backend_config("ibm:ibm_kyoto")
    assert cfg.backend == "ibm"
    assert cfg.ibm_backend_name == "ibm_kyoto"


def test_parse_backend_invalid():
    with pytest.raises(ValueError):
        build_backend_config("ibm:")
    with pytest.raises(ValueError):
        build_backend_config("foo")
    with pytest.raises(ValueError):
        build_backend_config("ibm")
