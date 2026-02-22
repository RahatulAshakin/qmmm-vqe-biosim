def test_import_package():
    import qmmm_vqe_biosim  # noqa: F401


def test_paths():
    from qmmm_vqe_biosim.paths import ensure_project_dirs

    dirs = ensure_project_dirs()
    assert dirs["data"].exists()
    assert dirs["raw"].exists()
