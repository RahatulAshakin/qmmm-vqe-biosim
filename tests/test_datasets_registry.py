from qmmm_vqe_biosim.datasets.registry import get_dataset_specs


def test_dataset_specs_present():
    specs = get_dataset_specs()
    assert "mor41" in specs
    assert "rost61" in specs
    assert "mme55" in specs
