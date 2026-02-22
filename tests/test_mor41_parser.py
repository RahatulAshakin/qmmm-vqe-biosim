import json
from pathlib import Path

from qmmm_vqe_biosim.datasets.mor41 import parse_mor41_structures


def test_parse_mor41_structures(tmp_path: Path):
    raw = tmp_path / "mor41"
    (raw / "ED26").mkdir(parents=True)
    (raw / "ED26" / "mol.xyz").write_text(
        "2\nx\nH 0 0 0\nH 0 0 1\n",
        encoding="utf-8",
    )

    out = tmp_path / "processed" / "mor41" / "structures.jsonl"
    parse_mor41_structures(raw_dir=raw, out_path=out, limit=None)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["dataset"] == "mor41"
    assert rec["record_id"] == "ED26"
    assert rec["atoms"] == ["H", "H"]
