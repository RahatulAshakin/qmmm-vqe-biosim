import json
from pathlib import Path

from qmmm_vqe_biosim.datasets.rost61 import parse_rost61_structures


def test_parse_rost61_structures(tmp_path: Path):
    # mimic real extract layout: raw_dir/rost61/m74/mol.xyz
    raw = tmp_path / "rost61_raw"
    case = raw / "rost61" / "m74"
    case.mkdir(parents=True)

    (case / "mol.xyz").write_text(
        "2\ncomment\nH 0 0 0\nH 0 0 1\n",
        encoding="utf-8",
    )
    (case / ".CHRG").write_text("0\n", encoding="utf-8")
    (case / ".UHF").write_text("1\n", encoding="utf-8")  # -> multiplicity 2

    out = tmp_path / "processed" / "rost61" / "structures.jsonl"
    parse_rost61_structures(raw_dir=raw, out_path=out, limit=None)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])

    assert rec["dataset"] == "rost61"
    assert rec["record_id"] == "m74"
    assert rec["charge"] == 0
    assert rec["multiplicity"] == 2
