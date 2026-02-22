from __future__ import annotations

import argparse

from qmmm_vqe_biosim.paths import ensure_project_dirs


def main() -> None:
    parser = argparse.ArgumentParser(prog="qmmm-vqe-biosim")
    parser.add_argument("--show-env", action="store_true", help="Print environment + paths info")
    args = parser.parse_args()

    if args.show_env:
        dirs = ensure_project_dirs()
        print("Project directories:")
        for k, v in dirs.items():
            print(f"  {k:10s} -> {v}")

        # Imports here so '--help' stays fast even if heavy deps are missing
        import pyscf
        import qiskit
        import qiskit_ibm_runtime
        import qiskit_nature

        print("\nVersions:")
        print("  qiskit         ", qiskit.__version__)
        print("  qiskit-nature  ", qiskit_nature.__version__)
        print("  pyscf          ", pyscf.__version__)
        print("  ibm-runtime    ", qiskit_ibm_runtime.__version__)


if __name__ == "__main__":
    main()
