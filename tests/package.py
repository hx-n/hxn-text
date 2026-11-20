#!/usr/bin/env python3
"""Build a complete local SDK and test direct Haxe consumers without Rust tooling."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli",default="hxn")
    parser.add_argument("--ash",default="ash")
    args=parser.parse_args()
    work=ROOT/"target/installed-consumer";work.mkdir(parents=True,exist_ok=True)
    package=work/"package"
    env=os.environ.copy()
    log=(work/"build.log").open("w")
    def run(argv,cwd=ROOT,consumer=False,capture=False):
        actual=dict(env)
        if consumer:actual["RUSTUP_TOOLCHAIN"]="hxn-consumer-must-not-build-rust"
        command=list(map(str,argv));log.write("RUN "+repr(command)+"\n");log.flush()
        result=subprocess.run(command,cwd=cwd,env=actual,stdout=subprocess.PIPE if capture else log,stderr=subprocess.STDOUT,text=True,timeout=1200)
        if capture:log.write(result.stdout);log.flush()
        if result.returncode:raise RuntimeError(f"command failed ({result.returncode}); see {work/'build.log'}")
        return result.stdout if capture else ""
    run([args.cli,"package","hl","cpp","--release","--out",package])
    for file in ("README.md","LICENSE"):shutil.copy2(ROOT/file,package/file)
    for folder in ("third-party","skills"):
        if not (ROOT/folder).is_dir():raise RuntimeError(f"missing redistribution directory: {folder}")
        shutil.copytree(ROOT/folder,package/folder,dirs_exist_ok=True)
    assert (package/"sources/hxn/text/NativeNames.hx").is_file()
    assert "NativeNames.register" in (package/"extraParams.hxml").read_text()
    hxcpp=run(["haxelib","libpath","hxcpp"],capture=True).strip()
    env["HAXELIB_PATH"]=str(work/"haxelib")
    Path(env["HAXELIB_PATH"]).mkdir(exist_ok=True)
    run(["haxelib","install","hxn","0.3.10","--quiet","--always"])
    run(["haxelib","dev","hxcpp",hxcpp])
    run(["haxelib","dev","hxn-text",package])
    out=work/"app";out.mkdir(exist_ok=True)
    common=["haxe","-lib","hxn-text","-cp",ROOT/"examples/check","-main","Main"]
    for name,file in [("latin","NotoSans-Regular.ttf"),("arabic","arabic.ttf"),("devanagari","devanagari.ttf")]:common += ["-resource",str(ROOT/"tests/fixtures"/file)+"@"+name]
    run([*common,"-hl",out/"main.hl"],consumer=True)
    marker="PASS: owned fonts"
    for options in [[],["--mode","jit"],["--mode","interp"]]:
        output=run([args.ash,*options,out/"main.hl"],cwd=out,consumer=True,capture=True)
        assert marker in output,output
    run([*common,"-cpp",out/"cpp"],consumer=True)
    executable=out/"cpp"/("Main.exe" if os.name=="nt" else "Main")
    output=run([executable],cwd=out,consumer=True,capture=True)
    assert marker in output,output
    print("PASS: installed hxn-text on Ash hybrid/JIT/interpreter and hxcpp with Rust tooling disabled")

if __name__=="__main__":main()
