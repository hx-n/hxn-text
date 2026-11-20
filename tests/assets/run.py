#!/usr/bin/env python3
"""Run the annotated font example and asset regressions with generated bindings."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODES = {
    "hl": ["hl"], "cpp": ["cpp"], "cppia": ["cppia"],
    "wasm": ["hl", "--wasm"], "wasm-threads": ["hl", "--wasm", "--threads"],
    "wasm-page": ["hl", "--wasm", "--browser"],
    "wasm-threads-page": ["hl", "--wasm", "--threads", "--browser"],
    "emcc": ["cpp", "--wasm"], "emcc-threads": ["cpp", "--wasm", "--threads"],
    "emcc-page": ["cpp", "--wasm", "--browser"],
    "emcc-threads-page": ["cpp", "--wasm", "--threads", "--browser"],
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default="hxn")
    parser.add_argument("--vm", default="ash")
    parser.add_argument("--assets", type=Path, default=ROOT.parent / "hxn-assets")
    parser.add_argument("--mode", action="append", choices=MODES)
    parser.add_argument("--assets-package", type=Path, help="Complete prepared assets SDK; required for the CPPIA host")
    parser.add_argument("--example", action="store_true", help="Run the file-backed example instead of the in-memory regressions")
    parser.add_argument("--file-package", type=Path, help="Prepared hxn-file package for the file-backed example")
    args = parser.parse_args()
    if args.example and args.file_package is None:
        parser.error("--example requires --file-package")
    modes = args.mode or ["hl", "cpp"]
    if "cppia" in modes and (args.assets_package is None or args.file_package is None):
        parser.error("cppia requires --assets-package and --file-package prepared SDKs")
    assets = args.assets_package.resolve() / "src" if args.assets_package else args.assets.resolve() / "packages/hxn-assets/src"
    if not (assets / "hxn/assets/Assets.hx").is_file():
        parser.error("--assets must name the hxn-assets source repository")
    work = ROOT / "target" / ("font-assets-example" if args.example else "font-assets-project")
    work.mkdir(parents=True, exist_ok=True)
    for name in ("src", "sources", "tests", "text.hxn.json"):
        link = work / name
        if not link.exists():
            link.symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
    shutil.copy2(ROOT / "Cargo.lock", work / "Cargo.lock")
    directory = ROOT / ("examples/assets/assets" if args.example else "tests/fixtures")
    flags = ["-D", "HXCPP_LINK_MEMORY_GROWTH", "-D", "hxn_assets", "-cp", str(assets), "-lib", "format:3.8.0", "-cp", str(ROOT / "examples/assets"),
             "-D", "hxn_assets_dir=" + str(directory)]
    if args.assets_package:
        package = args.assets_package.resolve()
        flags += ["-cp", str(package), str(package / "extraParams.hxml")]
    if args.file_package:
        package = args.file_package.resolve()
        flags += ["-cp", str(package), str(package / "extraParams.hxml"), "--macro", "hxn.assets.Build.register()"]
    if not args.example:
        flags += ["-resource", str(ROOT / "tests/fixtures/NotoSans-Regular.ttf") + "@latin",
                  "-resource", str(ROOT / "tests/fixtures/arabic.ttf") + "@arabic"]
    manifest = (ROOT / "Cargo.toml").read_text().split("[package.metadata.hxn]")[0]
    manifest += '[package.metadata.hxn]\nlibrary = "text"\n'
    manifest += "haxe = " + json.dumps(str(ROOT / ("examples/assets" if args.example else "tests/assets"))) + "\n"
    manifest += "main = " + json.dumps("Main" if args.example else "FontAssetsCheck") + "\n"
    manifest += 'init = ["hxn.text.NativeNames.register()"]\n'
    manifest += "haxe-flags = " + json.dumps(flags) + "\n"
    (work / "Cargo.toml").write_text(manifest)
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(ROOT / "target")
    marker = "PASS: content-addressed font asset" if args.example else "PASS: annotated font assets"
    for mode in modes:
        if mode.startswith("emcc"):
            # hxcpp can reuse a link when only application memory flags change.
            variant = "cpp-wasm-threads" if "threads" in mode else "cpp-wasm"
            output = ROOT / "target/hxn/text" / variant / "out"
            for suffix in (".js", ".wasm", ".html"):
                (output / (("Main" if args.example else "FontAssetsCheck") + suffix)).unlink(missing_ok=True)
        command = [args.cli, "check", *MODES[mode]]
        if MODES[mode][0] == "hl":
            command += ["--vm", args.vm]
        result = subprocess.run(command, cwd=work, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=1200)
        (work / (mode + ".log")).write_text(result.stdout)
        if result.returncode or marker not in result.stdout:
            raise RuntimeError(f"{mode} failed; see {work / (mode + '.log')}")
        print(f"PASS: {'file-backed example' if args.example else 'font asset regressions'} on {mode}", flush=True)

if __name__ == "__main__":
    main()
