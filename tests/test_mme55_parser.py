import json
from pathlib import Path

from qmmm_vqe_biosim.datasets.mme55 import parse_mme55_structures


def test_parse_mme55_structures(tmp_path: Path):
    # mimic real layout: raw_dir/repo/<case>/struc.xyz
    raw = tmp_path / "mme55_raw"
    case = raw / "repo" / "CDO_5D"
    case.mkdir(parents=True)

    (case / "struc.xyz").write_text(
        "2\ncomment\nH 0 0 0\nH 0 0 1\n",
        encoding="utf-8",
    )
    (case / ".CHRG").write_text("0\n", encoding="utf-8")
    (case / ".UHF").write_text("1\n", encoding="utf-8")  # -> multiplicity 2

    out = tmp_path / "processed" / "mme55" / "structures.jsonl"
    parse_mme55_structures(raw_dir=raw, out_path=out, limit=None)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])

    assert rec["dataset"] == "mme55"
    assert rec["record_id"] == "CDO_5D"
    assert rec["charge"] == 0
    assert rec["multiplicity"] == 2
