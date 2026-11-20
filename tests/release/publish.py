#!/usr/bin/env python3
"""Publish only a complete SDK whose package files match its public tag."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tomllib
import zipfile
from package import ROOT, validate_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dist", type=Path, default=ROOT / "target/release-dist")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.tag):
        raise ValueError("expected a release version tag")
    version = args.tag[1:]
    repository = os.environ.get("GITHUB_REPOSITORY", "hx-n/hxn-text")

    def output(command):
        return subprocess.check_output(command, cwd=ROOT, timeout=120)

    def tagged(path):
        return output(["git", "show", args.tag + ":" + path])

    cargo = tomllib.loads(tagged("Cargo.toml").decode())
    if cargo["package"]["version"] != version:
        raise ValueError("tag and package versions differ")
    core = cargo["dependencies"]["hxn"]["tag"].removeprefix("v")
    archive = args.dist / f"hxn-text-{version}.zip"

    def verify_local():
        validate_archive(archive)
        with zipfile.ZipFile(archive) as sdk:
            meta = json.loads(sdk.read("haxelib.json"))
            if meta != json.loads(tagged("haxelib.json")) or meta["dependencies"]["hxn"] != core:
                raise ValueError("archive metadata differs from the tag")
            names = output(["git", "ls-tree", "-r", "--name-only", args.tag, "binding", "include", "sources", "text.hxn.json", "extraParams.hxml"]).decode().splitlines()
            for name in names:
                if sdk.read(name) != tagged(name):
                    raise ValueError("archive API differs from the tag: " + name)
        checksums = {name.strip().removeprefix("*"): digest for digest, name in
                     (line.split(None, 1) for line in (args.dist / "SHA256SUMS").read_text().splitlines())}
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if checksums[archive.name] != digest:
            raise ValueError("release checksum mismatch")
        return digest

    digest = verify_local()
    revision = output(["git", "rev-parse", args.tag + "^{commit}"]).decode().strip()
    remote = json.loads(output(["gh", "api", f"repos/{repository}/commits/{args.tag}"]))
    if remote["sha"] != revision:
        raise ValueError("local and public release tags differ")
    exists = subprocess.run(["gh", "release", "view", args.tag], cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=120).returncode == 0
    password = os.environ.get("HAXELIB_PASSWORD")
    if not args.check_only and not password:
        raise SystemExit("Configure HAXELIB_PASSWORD before publishing")
    if not exists:
        if args.check_only:
            raise SystemExit("No published GitHub release to verify")
        subprocess.run(["gh", "release", "create", args.tag, "--verify-tag", "--title", "hxn-text " + version,
                        "--notes-file", str(ROOT / "tests/release/notes.md"), str(archive), str(args.dist / "SHA256SUMS")],
                       cwd=ROOT, check=True, timeout=180)
    else:
        # A retry uses the already published immutable ZIP rather than replacing it.
        subprocess.run(["gh", "release", "download", args.tag, "--clobber", "--pattern", archive.name,
                        "--pattern", "SHA256SUMS", "--dir", str(args.dist)], cwd=ROOT, check=True, timeout=180)
        digest = verify_local()
    release = json.loads(output(["gh", "api", f"repos/{repository}/releases/tags/{args.tag}"]))
    assets = {item["name"]: item for item in release["assets"]}
    if release["draft"] or release["tag_name"] != args.tag or assets[archive.name].get("digest") != "sha256:" + digest:
        raise ValueError("published release or asset digest differs")
    print("PASS: complete immutable SDK matches the public tag and GitHub asset")
    if args.check_only:
        return

    def published():
        result = subprocess.run(["haxelib", "info", "hxn-text"], capture_output=True, text=True, timeout=90)
        text = result.stdout + result.stderr
        if result.returncode and "No such Project" not in text:
            raise RuntimeError("Could not verify Haxelib publication")
        return any(line.strip() == "Version: " + version or re.match(r"^\s*\d{4}-\d{2}-\d{2}\s+\S+\s+" + re.escape(version) + r"\s*:", line) for line in text.splitlines())

    for attempt in range(3):
        if published():
            print("PASS: Haxelib already has hxn-text " + version)
            return
        try:
            result = subprocess.run(["haxelib", "submit", str(archive), password, "--never"], capture_output=True,
                                    text=True, timeout=600, stdin=subprocess.DEVNULL)
            text = (result.stdout + result.stderr).replace(password, "[redacted]")
        except subprocess.TimeoutExpired:
            text = "Haxelib upload timed out; checking whether the server accepted it"
        print("\n".join(line for line in text.splitlines() if not re.fullmatch(r"\d+%", line)))
        if "Invalid password" in text:
            raise SystemExit("Haxelib rejected HAXELIB_PASSWORD for darmie")
        if published():
            print("PASS: published hxn-text " + version)
            return
        if attempt < 2:
            time.sleep(5 * (attempt + 1))
    raise SystemExit("Haxelib did not accept hxn-text " + version)


if __name__ == "__main__":
    main()
