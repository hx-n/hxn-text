#!/usr/bin/env python3
"""Run the font/atlas fixture as a test executable on a simulator or Android."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=["ios-sim","android"])
    parser.add_argument("runtime", choices=["hl","cpp"])
    parser.add_argument("--device", required=True)
    parser.add_argument("--cli", default="hxn")
    parser.add_argument("--ash", default="ash")
    parser.add_argument("--hxn", type=Path, default=ROOT.parent/"hxn")
    parser.add_argument("--assets-source", type=Path, help="Run the annotated font-asset fixture with this hxn-assets repository")
    args=parser.parse_args()
    ios=args.platform=="ios-sim"
    main_class="FontAssetsCheck" if args.assets_source else "Main"
    triple=("aarch64-apple-ios-sim" if args.runtime=="hl" else "x86_64-apple-ios") if ios else "aarch64-linux-android"
    work=ROOT/"target/mobile"/(args.platform+"-"+args.runtime)
    work.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    sdk=Path(env.get("ANDROID_HOME", str(Path.home()/"Library/Android/sdk")))
    ndk=Path(env.get("ANDROID_NDK_ROOT", str(sdk/"ndk/27.0.12077973")))
    tools=ndk/"toolchains/llvm/prebuilt/darwin-x86_64/bin"
    env.update(IPHONEOS_DEPLOYMENT_TARGET="12.0",ANDROID_NDK_ROOT=str(ndk),ANDROID_NDK_HOME=str(ndk),NDK_ROOT=str(ndk))
    if not ios:
        env.update(CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=str(tools/"aarch64-linux-android26-clang"), CC_aarch64_linux_android=str(tools/"aarch64-linux-android26-clang"), AR_aarch64_linux_android=str(tools/"llvm-ar"), ASH_ANDROID_API="26")
    log=(work/"build.log").open("w")
    def run(command,cwd=ROOT,extra=None,capture=False,timeout=900):
        actual=dict(env);actual.update(extra or {})
        command=list(map(str,command)); log.write("RUN "+repr(command)+"\n");log.flush()
        result=subprocess.run(command,cwd=cwd,env=actual,text=True,stdout=subprocess.PIPE if capture else log,stderr=subprocess.STDOUT,timeout=timeout)
        if capture:log.write(result.stdout);log.flush()
        if result.returncode:raise RuntimeError(f"command failed ({result.returncode}): see {work/'build.log'}")
        return result.stdout if capture else ""
    package=work/"package"
    run([args.cli,"package",args.runtime,"--target",triple,"--release","--out",package])
    out=work/"out";out.mkdir(exist_ok=True)
    nonce=uuid.uuid4().hex
    (work/"nonce.txt").write_text(nonce)
    flags=["haxe","-cp",args.hxn/"haxe","-cp",package,package/"extraParams.hxml","-cp",ROOT/"examples/check","-main",main_class,"-D","hxn_triple="+triple,"-resource",str(work/"nonce.txt")+"@hxn-text-test-nonce"]
    for name,file in [("latin","NotoSans-Regular.ttf"),("arabic","arabic.ttf"),("devanagari","devanagari.ttf")]:
        flags += ["-resource",str(ROOT/"tests/fixtures"/file)+"@"+name]
    if args.assets_source:
        flags += ["-D","hxn_assets","-cp",args.assets_source.resolve()/"packages/hxn-assets/src","-lib","format:3.8.0","-cp",ROOT/"examples/assets","-cp",ROOT/"tests/assets","-D","hxn_assets_dir="+str(ROOT/"tests/fixtures")]
    frameworks=["-framework","CoreText","-framework","CoreGraphics","-framework","CoreFoundation","-framework","QuartzCore","-liconv","-lobjc"]
    if args.runtime=="hl":
        run([*flags,"-hl",out/"main.hl"])
        extra={"ASH_LINK_ARGS":" ".join(frameworks)} if ios else {"ASH_LINK_ARGS":"--target=aarch64-linux-android26"}
        run([args.ash,"--build",out/"program","--target",triple,"--native-lib",out/"libtext.a",out/"main.hl"],cwd=out,extra=extra)
    else:
        if ios:
            xml=ET.parse(package/"native"/triple/"link.xml")
            for element in xml.getroot().iter():
                if element.tag=="lib" and element.get("name","").startswith("-l"):
                    element.tag="flag";element.attrib={"value":"-ref-"+element.get("name")[1:]}
                elif element.tag=="flag" and element.get("value")=="-framework":element.set("value","-ref-framework")
            deferred=work/"archive-link.xml";xml.write(deferred,encoding="unicode")
            flags += ["--macro","haxe.macro.Compiler.define(\"TEXT_LINK\", "+json.dumps(str(deferred))+")"]
            defines=["-D","iphonesim","-D","HXCPP_M64","-D","HXCPP_IOS_MIN_VERSION=12.0"]
        else:
            defines=["-D","android","-D","HXCPP_ARM64","-D","HXCPP_DEBUG_LINK","-D","ANDROID_HOST=darwin-x86_64","-D","HXCPP_ANDROID_PLATFORM=26"]
        run([*flags,"-cpp",out,*defines])
        if ios:
            libraries=list(out.glob("lib"+main_class+"*.a"));assert len(libraries)==1,libraries
            run(["xcrun","--sdk","iphonesimulator","clang++","-arch","x86_64","-mios-simulator-version-min=12.0",ROOT/"tests/mobile/main.cpp",libraries[0],*frameworks,"-o",out/"program"])
        else:
            run([tools/"aarch64-linux-android26-clang",ROOT/"tests/mobile/main.c","-L"+str(out),"-l"+main_class+"-64","-o",out/"program"])
    if ios:
        output=run(["xcrun","simctl","spawn",args.device,out/"program"],capture=True,timeout=120)
    else:
        adb=[sdk/"platform-tools/adb","-s",args.device]
        remote="/data/local/tmp/hxn-text-"+nonce
        run([*adb,"shell","mkdir",remote],timeout=30)
        try:
            files=[out/"program"]+([out/("lib"+main_class+"-64.so")] if args.runtime=="cpp" else [])
            run([*adb,"push",*files,remote+"/"],timeout=60)
            output=run([*adb,"shell",f"cd {remote} && LD_LIBRARY_PATH=. ./program"],capture=True,timeout=120)
            if args.runtime=="cpp":output += run([*adb,"logcat","-d","-v","raw","-s","trace"],capture=True,timeout=30)
        finally:run([*adb,"shell","rm","-rf",remote],timeout=30)
    assert "hxn-text-test:"+nonce in output,output[-3000:]
    marker="PASS: annotated font assets" if args.assets_source else "PASS: owned fonts"
    assert marker in output,output[-3000:]
    print(f"PASS: {args.platform} {args.runtime} " + ("annotated font assets" if args.assets_source else "fonts, shaping, masks and atlas updates"))

if __name__=="__main__":main()
