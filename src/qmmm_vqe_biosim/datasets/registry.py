from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DatasetKind = Literal["tar_gz", "git"]


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    kind: DatasetKind
    description: str
    homepage: str
    archive_url: str | None = None
    git_url: str | None = None


def get_dataset_specs() -> dict[str, DatasetSpec]:
    """
    Canonical dataset specs.

    Notes:
    - tar_gz datasets are downloaded into data/raw/<name>/ and extracted there.
    - git datasets are cloned into data/raw/<name>/repo
    """
    specs = {
        "mor41": DatasetSpec(
            name="mor41",
            kind="tar_gz",
            description="Metal-organic reactions (MOR41) benchmark geometries (Grimme group).",
            homepage="https://www.chemie.uni-bonn.de/grimme/de/software/mor41",
            archive_url="https://www.chemie.uni-bonn.de/grimme/de/software/mor41/geometries-tar.gz",
        ),
        "rost61": DatasetSpec(
            name="rost61",
            kind="tar_gz",
            description="ROST61 open-shell organometallic reactions benchmark (Grimme group).",
            homepage="https://www.chemie.uni-bonn.de/grimme/de/software/rost61",
            archive_url="https://www.chemie.uni-bonn.de/grimme/de/software/rost61/rost61-tar.gz",
        ),
        "mme55": DatasetSpec(
            name="mme55",
            kind="git",
            description="MME55 metalloenzyme model reactions benchmark (dataset repo).",
            homepage="https://github.com/grimme-lab/benchmark-MME55",
            git_url="https://github.com/grimme-lab/benchmark-MME55.git",
        ),
        "tmqm": DatasetSpec(
            name="tmqm",
            kind="git",
            description="tmQM dataset files (transition metal complexes).",
            homepage="https://github.com/uiocompcat/tmQM",
            git_url="https://github.com/uiocompcat/tmQM.git",
        ),
    }
    return specs


def get_spec(name: str) -> DatasetSpec:
    specs = get_dataset_specs()
    key = name.strip().lower()
    if key not in specs:
        raise KeyError(f"Unknown dataset '{name}'. Available: {', '.join(sorted(specs))}")
    return specs[key]
