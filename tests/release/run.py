#!/usr/bin/env python3
"""Compile installed Haxe consumers while Rust tooling is disabled."""
import argparse
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from package import validate_archive

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["native", "wasm", "wasm-threads", "emcc", "emcc-threads"])
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--package", type=Path, help="Local haxelib root instead of a ZIP")
    parser.add_argument("--allow-partial", action="store_true", help="Local validation of only the available native targets")
    parser.add_argument("--ash", default="ash")
    parser.add_argument("--chrome", default="google-chrome")
    parser.add_argument("--hl", help="Also run stock HashLink")
    parser.add_argument("--assets-package", type=Path)
    parser.add_argument("--file-package", type=Path)
    args = parser.parse_args()
    if bool(args.assets_package) != bool(args.file_package):
        parser.error("provide both asset/file package overrides")
    work = ROOT / "target/release-consumer" / args.mode
    work.mkdir(parents=True, exist_ok=True)
    log = (work / "consumer.log").open("w")
    environment = os.environ.copy()
    if args.mode.startswith("emcc"):
        environment.pop("CC", None)
        environment.pop("CXX", None)

    def run(command, *, cwd=ROOT, timeout=600, marker=None):
        command = list(map(str, command))
        log.write("RUN " + repr(command) + "\n"); log.flush()
        result = subprocess.run(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=timeout)
        log.write(result.stdout); log.flush()
        if result.returncode or (marker is not None and marker not in result.stdout):
            raise RuntimeError(f"consumer failed; see {work / 'consumer.log'}\n{result.stdout[-6000:]}")
        return result.stdout.strip()

    hxcpp = run(["haxelib", "libpath", "hxcpp"])
    # An isolated repository prevents source checkouts or a global dev override from supplying bindings.
    repository = work / "haxelib"
    if repository.exists():
        shutil.rmtree(repository)
    repository.mkdir()
    environment["HAXELIB_PATH"] = str(repository)
    if args.package:
        sdk = args.package.resolve()
        meta = json.loads((sdk / "haxelib.json").read_text())
        run(["haxelib", "dev", "hxn-text", sdk])
    else:
        archives = [args.archive.resolve()] if args.archive else list((ROOT / "target/release-dist").glob("hxn-text-*.zip"))
        if len(archives) != 1:
            raise ValueError("expected exactly one release ZIP")
        meta, _ = validate_archive(archives[0], partial=args.allow_partial)
        run(["haxelib", "install", archives[0], "--always", "--quiet", "--skip-dependencies"])
        sdk = Path(run(["haxelib", "libpath", "hxn-text"]))
        if not sdk.resolve().is_relative_to(repository.resolve()):
            raise ValueError("Haxelib resolved a source override instead of the installed ZIP")
    run(["haxelib", "install", "hxn", meta["dependencies"]["hxn"], "--always", "--quiet"])
    run(["haxelib", "dev", "hxcpp", hxcpp])
    # The published file SDK currently provides the threaded Ash wasm target.
    # Text-only applications also exercise Ash's threadless target without that dependency.
    assets = args.mode != "wasm"
    if assets:
        if args.assets_package:
            run(["haxelib", "dev", "hxn-assets", args.assets_package.resolve()])
            run(["haxelib", "dev", "hxn-file", args.file_package.resolve()])
            run(["haxelib", "install", "format", "3.8.0", "--always", "--quiet"])
        else:
            run(["haxelib", "install", "hxn-assets", "0.1.0", "--always", "--quiet"])

    environment.update(RUSTUP_TOOLCHAIN="hxn-consumer-must-not-build-rust", CARGO="hxn-consumer-no-cargo", RUSTC="hxn-consumer-no-rustc")
    guards = work / "no-rust"; guards.mkdir(exist_ok=True)
    attempted = guards / "attempted"
    attempted.unlink(missing_ok=True)
    for tool in ("cargo", "rustc", "rustup"):
        if os.name == "nt":
            (guards / (tool + ".cmd")).write_text('@echo off\necho Rust invocation is forbidden>"' + str(attempted) + '"\nexit /b 86\n')
        else:
            path = guards / tool
            path.write_text("#!" + sys.executable + "\nfrom pathlib import Path\nPath(" + repr(str(attempted)) + ").write_text('Rust invocation is forbidden')\nraise SystemExit(86)\n")
            path.chmod(0o755)
    environment["PATH"] = str(guards) + os.pathsep + environment["PATH"]

    resources = []
    for name, filename in [("latin", "NotoSans-Regular.ttf"), ("arabic", "arabic.ttf"), ("devanagari", "devanagari.ttf")]:
        resources += ["-resource", str(ROOT / "tests/fixtures" / filename) + "@" + name]
    cases = [("core", ["-lib", "hxn-text", "-cp", ROOT / "examples/check", *resources], "Main", "PASS: owned fonts")]
    if assets:
        cases += [
            ("assets", ["-lib", "hxn-text", "-lib", "hxn-assets", "-cp", ROOT / "tests/assets",
                        "-cp", sdk / "examples/assets", "-D", "hxn_assets_dir=" + str(ROOT / "tests/fixtures"), *resources],
             "FontAssetsCheck", "PASS: annotated font assets"),
            ("bundle", ["-lib", "hxn-text", "-lib", "hxn-assets", "-cp", sdk / "examples/assets",
                        "-D", "hxn_assets_dir=" + str(sdk / "examples/assets/assets")],
             "Main", "PASS: content-addressed font asset"),
        ]
    for label, flags, main_class, marker in cases:
        directory = work / label; directory.mkdir(exist_ok=True)
        common = ["haxe", *flags]
        if args.mode in ("native", "wasm", "wasm-threads"):
            bytecode = directory / "main.hl"
            defines = [] if args.mode == "native" else ["-D", "wasm"] + (["-D", "hxn_threads"] if args.mode.endswith("threads") else [])
            run([*common, "-main", main_class, *defines, "-hl", bytecode])
            if args.mode == "native":
                for options in ([], ["--mode", "jit"], ["--mode", "interp"]):
                    run([args.ash, *options, bytecode], cwd=directory, timeout=120, marker=marker)
                if args.hl:
                    run([args.hl, bytecode], cwd=directory, timeout=120, marker=marker)
            else:
                target = "wasm32-wasip1-threads" if args.mode.endswith("threads") else "wasm32-wasip1"
                libraries = [item for library in sorted(directory.glob("lib*.a")) for item in ["--native-lib", library]]
                run([args.ash, "--build", directory / "main.wasm", "--target", target, *libraries, bytecode], cwd=directory)
                run(["node", ROOT / "tests/release/ash_page.mjs", args.ash, directory, args.chrome], timeout=180, marker=marker)
        if args.mode == "native" or args.mode.startswith("emcc"):
            target = directory / "cpp"
            defines = [] if args.mode == "native" else ["-D", "emscripten", "-D", "wasm", "-D", "HXCPP_LINK_EMSCRIPTEN_EXT=.html",
                                                      "-D", "HXCPP_LINK_EMRUN", "-D", "HXCPP_LINK_MEMORY_GROWTH"]
            if args.mode == "emcc-threads":
                defines += ["-D", "hxn_threads"]
            run([*common, "-main", main_class, *defines, "-cpp", target])
            if args.mode == "native":
                run([target / (main_class + (".exe" if os.name == "nt" else ""))], cwd=target, timeout=120, marker=marker)
                if label != "bundle":
                    host = directory / "host"
                    exported = directory / "host.info"
                    run([*common, "-cp", ROOT / "tests/release", "-main", "Host", "-D", "scriptable", "-dce", "no",
                         "-D", "dll_export=" + str(exported), "--macro", "include('hxn')", "-cpp", host], cwd=directory)
                    script = directory / "main.cppia"
                    run([*common, "-main", main_class, "-D", "dll_import=" + str(exported), "-cppia", script], cwd=directory)
                    run([host / ("Host.exe" if os.name == "nt" else "Host"), script], cwd=directory, timeout=120, marker=marker)
            else:
                stdout, stderr = directory / "stdout.txt", directory / "stderr.txt"
                stdout.unlink(missing_ok=True); stderr.unlink(missing_ok=True)
                with tempfile.TemporaryDirectory(prefix="hxn-text-browser-", ignore_cleanup_errors=True) as profile:
                    run(["emrun", "--browser", args.chrome,
                         "--browser_args=--headless=new --no-first-run --no-default-browser-check --user-data-dir=" + profile,
                         "--kill_exit", "--timeout", "120", "--timeout-returncode", "1", "--log-stdout", stdout,
                         "--log-stderr", stderr, target / (main_class + ".html")], timeout=180)
                if marker not in stdout.read_text() + stderr.read_text():
                    raise RuntimeError(f"missing browser pass marker: {directory}")
        if label == "bundle":
            staged = directory / ("cpp/assets" if args.mode.startswith("emcc") else "assets") / "NotoSans-OFL.txt"
            if staged.read_bytes() != (sdk / "examples/assets/assets/NotoSans-OFL.txt").read_bytes():
                raise ValueError("font license was not staged unchanged")
        print(f"PASS: installed {label} consumer on {args.mode} with Rust disabled", flush=True)
    if attempted.exists():
        raise RuntimeError("a consumer attempted to invoke Rust tooling")


if __name__ == "__main__":
    main()
