#!/usr/bin/env python3
"""Reject SDKs that lose native binaries, leak producer code or mix API generations."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
import zipfile
from package import ROOT, SHARED, assemble, validate_archive


def rejected(operation, message):
    try:
        operation()
    except ValueError as error:
        if message not in str(error):
            raise
    else:
        raise AssertionError("invalid release artifact was accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    archives = [args.archive] if args.archive else list((ROOT / "target/release-dist").glob("hxn-text-*.zip"))
    assert len(archives) == 1, archives
    archive = archives[0]
    validate_archive(archive, partial=args.allow_partial)
    with tempfile.TemporaryDirectory(prefix="hxn-sdk-reject-") as temporary:
        work = Path(temporary)
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            binary = next(n for n in names if n.startswith("native/") and n.endswith((".hdll", ".a", ".lib")))
            broken = work / "missing.zip"
            with zipfile.ZipFile(broken, "w", zipfile.ZIP_DEFLATED) as output:
                for name in names:
                    if name != binary:
                        output.writestr(name, source.read(name))
            rejected(lambda: validate_archive(broken, partial=True), "missing native binary")
            leaked = work / "source.zip"
            shutil.copy2(archive, leaked)
            with zipfile.ZipFile(leaked, "a") as output:
                output.writestr("src/lib.rs", "producer implementation")
            rejected(lambda: validate_archive(leaked, partial=args.allow_partial), "producer sources")
            if args.allow_partial:
                rejected(lambda: validate_archive(archive), "incomplete prebuilt target matrix")
            else:
                target = binary.split("/")[1]
                missing = work / "target.zip"
                with zipfile.ZipFile(missing, "w", zipfile.ZIP_DEFLATED) as output:
                    for name in names:
                        if not name.startswith("native/" + target + "/"):
                            output.writestr(name, source.read(name))
                rejected(lambda: validate_archive(missing), "incomplete prebuilt target matrix")
            parts = work / "parts"; parts.mkdir()
            for index in range(2):
                part = parts / str(index); part.mkdir()
                for name in names:
                    if name.split("/")[0] in SHARED or name in SHARED or name.startswith("native/"):
                        path = part / name; path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(source.read(name))
            first = work / "first.zip"
            second = work / "second.zip"
            assemble(parts, work / "assembled", first, partial=args.allow_partial)
            assemble(parts, work / "assembled", second, partial=args.allow_partial)
            assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
            with (parts / "1/binding/hxn/text/Font.hx").open("a") as output:
                output.write("\n// differing API generation\n")
            rejected(lambda: assemble(parts, work / "assembled", work / "mixed.zip", partial=args.allow_partial), "generated bindings or metadata differ")
    print("PASS: missing binaries/targets, mixed API generations and producer-code leaks reject; ZIP assembly is reproducible")


if __name__ == "__main__":
    main()
