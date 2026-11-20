#!/usr/bin/env python3
"""Assemble prebuilt platform parts into the Haxe-only release ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu", "aarch64-apple-darwin",
    "x86_64-apple-darwin", "x86_64-pc-windows-msvc", "aarch64-apple-ios",
    "aarch64-apple-ios-sim", "aarch64-linux-android", "wasm32-wasip1",
    "wasm32-wasip1-threads", "wasm32-unknown-emscripten", "wasm32-unknown-emscripten-threads",
}
SHARED = ("binding", "include", "sources", "text.hxn.json", "haxelib.json", "extraParams.hxml")


def native_requirements(triple):
    if triple.startswith("wasm32-wasip1"):
        return {"libtext.a"}
    if triple.startswith("wasm32-unknown-emscripten") or triple == "x86_64-apple-darwin":
        return {"libtext_cpp.a", "link.xml"}
    if "ios" in triple or "android" in triple:
        return {"libtext.a", "libtext_cpp.a", "link.xml"}
    if "windows" in triple:
        return {"text.hdll", "text_cpp.lib", "link.xml"}
    return {"text.hdll", "libtext_cpp.a", "link.xml"}


def shared_files(package, *, headers=True):
    result = {}
    for name in SHARED:
        source = package / name
        if name == "include" and not headers and not source.exists():
            continue
        if not source.exists():
            raise ValueError(f"missing shared package entry: {source}")
        paths = source.rglob("*") if source.is_dir() else [source]
        for path in paths:
            if path.is_file():
                result[path.relative_to(package).as_posix()] = path.read_bytes()
    return result


def validate_archive(path, *, partial=False):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("corrupt release ZIP")
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != len({n.casefold() for n in names}):
            raise ValueError("duplicate release ZIP paths")
        if any(n.startswith("/") or ".." in n.split("/") or "\\" in n for n in names):
            raise ValueError("non-portable release ZIP paths")
        required = {"haxelib.json", "extraParams.hxml", "text.hxn.json", "README.md", "LICENSE",
                    "binding/hxn/text/Font.hx", "binding/hxn/text/TextEngine.hx", "include/hxn.h",
                    "sources/hxn/text/NativeNames.hx", "sources/hxn/text/FontAssets.hx",
                    "third-party/NOTICES.md", "third-party/inventory.json", "skills/hxn-text/SKILL.md",
                    "examples/assets/example.hxml", "examples/assets/assets/NotoSans-Regular.ttf",
                    "examples/assets/assets/NotoSans-OFL.txt"}
        if not required <= set(names):
            raise ValueError(f"incomplete Haxe SDK: {sorted(required - set(names))}")
        if any(n.startswith(("src/", "tests/", "target/", ".git/")) or n.endswith((".rs", "Cargo.toml", "Cargo.lock")) for n in names):
            raise ValueError("release contains producer sources or test tooling")
        meta = json.loads(archive.read("haxelib.json"))
        if meta["name"] != "hxn-text" or not meta["dependencies"].get("hxn"):
            raise ValueError("invalid Haxelib metadata")
        targets = {n.split("/")[1] for n in names if n.startswith("native/")}
        if not targets or not targets <= TARGETS or (not partial and targets != TARGETS):
            raise ValueError(f"incomplete prebuilt target matrix: {sorted(TARGETS - targets)}")
        for target in targets:
            for filename in native_requirements(target):
                name = f"native/{target}/{filename}"
                if name not in names or archive.getinfo(name).file_size == 0:
                    raise ValueError(f"missing native binary or link metadata: {name}")
        inventory = json.loads(archive.read("third-party/inventory.json"))
        for package in inventory["packages"]:
            if package.get("license") == "NOASSERTION":
                raise ValueError(f"unresolved dependency license: {package['name']}")
            for name in package["files"]:
                if archive.getinfo("third-party/" + name).file_size == 0:
                    raise ValueError(f"empty dependency notice: {name}")
            if package.get("source_archive"):
                source = archive.read("third-party/" + package["source_archive"])
                if hashlib.sha256(source).hexdigest() != package["source_sha256"]:
                    raise ValueError("dependency source archive checksum differs")
        return meta, targets


def assemble(parts, destination, archive_path, *, partial=False):
    packages = sorted(p for p in parts.iterdir() if p.is_dir() and (p / "haxelib.json").is_file())
    if not packages:
        raise ValueError("no platform package parts")
    base = next((p for p in packages if (p / "include/hxn.h").is_file()), None)
    if base is None:
        raise ValueError("no platform part contains the generated C++ headers")
    expected = shared_files(base)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name, data in expected.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for package in packages:
        # HL-only platform parts have no C++ headers; their remaining common files must agree.
        cpp = any((package / "native").glob("*/libtext_cpp.a")) or any((package / "native").glob("*/text_cpp.lib"))
        actual = shared_files(package, headers=cpp)
        comparable = expected if cpp else {name: data for name, data in expected.items() if not name.startswith("include/")}
        actual = actual if cpp else {name: data for name, data in actual.items() if not name.startswith("include/")}
        if actual != comparable:
            raise ValueError(f"generated bindings or metadata differ: {package}")
        for path in sorted((package / "native").rglob("*")):
            if not path.is_file():
                continue
            into = destination / path.relative_to(package)
            if into.exists() and into.read_bytes() != path.read_bytes():
                raise ValueError(f"conflicting native artifacts: {into}")
            into.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, into)
    for name in ("README.md", "LICENSE"):
        shutil.copy2(ROOT / name, destination / name)
    for name in ("third-party", "skills", "docs"):
        shutil.copytree(ROOT / name, destination / name)
    shutil.copytree(ROOT / "examples/assets", destination / "examples/assets", ignore=shutil.ignore_patterns("out", "__pycache__"))
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    # Stable member order, timestamps and permissions make the ZIP reproducible for these inputs.
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(destination).as_posix(), (2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes())
    return validate_archive(archive_path, partial=partial)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", type=Path, default=ROOT / "target/release-parts")
    parser.add_argument("--out", type=Path, default=ROOT / "target/release-dist")
    parser.add_argument("--check-dist", action="store_true")
    parser.add_argument("--allow-partial", action="store_true", help="Local validation only; CI releases require every target")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/") and (ref != "refs/tags/v" + version or args.allow_partial):
        raise ValueError("tag, package version or complete release matrix differs")
    archive = args.out / f"hxn-text-{version}.zip"
    if args.check_dist:
        meta, targets = validate_archive(archive, partial=args.allow_partial)
    else:
        meta, targets = assemble(args.parts, ROOT / "target/release-assembled", archive, partial=args.allow_partial)
    if meta["version"] != version:
        raise ValueError("Cargo and Haxelib versions differ")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (args.out / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
    print(f"PASS: {archive.name}, {len(targets)} prebuilt targets, sha256:{digest}")


if __name__ == "__main__":
    main()
