"""Build an uploadable skill ZIP without repository or research-run files."""

from pathlib import Path
import argparse
import zipfile


def package_skill(output: Path) -> int:
    source = Path(__file__).resolve().parents[1] / "skills" / "research-council"
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError("Missing research-council/SKILL.md")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("The ZIP output must be outside the skill folder")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            name = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1] / "dist" / "research-council.zip",
    )
    args = parser.parse_args()
    count = package_skill(args.output)
    print(f"Packaged {count} files: {args.output.resolve()}")
