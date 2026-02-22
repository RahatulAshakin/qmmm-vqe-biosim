from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import requests
from tqdm import tqdm

from qmmm_vqe_biosim.datasets.registry import get_dataset_specs, get_spec
from qmmm_vqe_biosim.paths import ensure_project_dirs


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def download_url(url: str, dest: Path, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest

    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()

    total = int(r.headers.get("content-length", 0)) or None
    tmp = dest.with_suffix(dest.suffix + ".part")

    with tmp.open("wb") as f, tqdm(
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=dest.name,
    ) as pbar:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            pbar.update(len(chunk))

    tmp.replace(dest)
    return dest


def _safe_extract_tar(tar: tarfile.TarFile, dest_dir: Path) -> None:
    dest_dir = dest_dir.resolve()
    for member in tar.getmembers():
        member_path = (dest_dir / member.name).resolve()
        if not str(member_path).startswith(str(dest_dir)):
            raise RuntimeError(f"Unsafe path in tar file: {member.name}")
    tar.extractall(dest_dir)


def extract_tar_gz(archive_path: Path, dest_dir: Path, force: bool = False) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    marker = dest_dir / f".extracted_{archive_path.name}.ok"
    if marker.exists() and not force:
        return dest_dir

    with tarfile.open(archive_path, mode="r:gz") as tar:
        _safe_extract_tar(tar, dest_dir)

    marker.write_text(f"extracted_at: {time.ctime()}\n")
    return dest_dir


def clone_repo(git_url: str, dest_dir: Path, force: bool = False) -> Path:
    if dest_dir.exists():
        if force:
            shutil.rmtree(dest_dir)
        else:
            # If it already looks like a repo, keep it
            if (dest_dir / ".git").exists():
                return dest_dir
            raise RuntimeError(f"Destination exists but is not a git repo: {dest_dir}")

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", git_url, str(dest_dir)], check=True)
    return dest_dir


def write_manifest(dataset: str, raw_dir: Path, artifacts: list[Path]) -> None:
    manifest = {
        "dataset": dataset,
        "raw_dir": str(raw_dir),
        "artifacts": [
            {
                "path": str(p),
                "sha256": sha256_file(p) if p.is_file() else None,
            }
            for p in artifacts
        ],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out = raw_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")


def download_dataset(name: str, force: bool = False) -> Path:
    dirs = ensure_project_dirs()
    spec = get_spec(name)

    raw_dir = dirs["raw"] / spec.name
    raw_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[Path] = []

    if spec.kind == "tar_gz":
        assert spec.archive_url is not None
        archive_name = Path(spec.archive_url).name
        archive_path = raw_dir / archive_name
        download_url(spec.archive_url, archive_path, force=force)
        artifacts.append(archive_path)
        extract_tar_gz(archive_path, raw_dir, force=force)

    elif spec.kind == "git":
        assert spec.git_url is not None
        repo_dir = raw_dir / "repo"
        clone_repo(spec.git_url, repo_dir, force=force)
        artifacts.append(repo_dir)

    else:
        raise ValueError(f"Unsupported dataset kind: {spec.kind}")

    write_manifest(spec.name, raw_dir, artifacts)
    return raw_dir


def main() -> None:
    specs = get_dataset_specs()

    parser = argparse.ArgumentParser(prog="qmmm-vqe-biosim.datasets.download")
    parser.add_argument("--list", action="store_true", help="List available datasets and exit")
    parser.add_argument("--dataset", type=str, help="Dataset name to download")
    parser.add_argument("--all", action="store_true", help="Download all datasets (excluding large ones by default)")
    parser.add_argument("--include-large", action="store_true", help="Include large datasets (e.g., tmqm) in --all")
    parser.add_argument("--force", action="store_true", help="Re-download / re-extract / re-clone")
    args = parser.parse_args()

    if args.list:
        print("Available datasets:")
        for k in sorted(specs):
            s = specs[k]
            print(f"  - {s.name:6s} [{s.kind}] {s.description}")
        return

    if args.all:
        names = sorted(specs.keys())
        if not args.include_large:
            names = [n for n in names if n not in {"tmqm"}]
        for n in names:
            print(f"\n==> Downloading {n}")
            out = download_dataset(n, force=args.force)
            print(f"Done: {out}")
        return

    if not args.dataset:
        raise SystemExit("Use --dataset <name> or --all or --list")

    out = download_dataset(args.dataset, force=args.force)
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
