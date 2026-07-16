import os
import platform
import subprocess
import sys


def compile_mac_helper() -> None:
    """Compile the native macOS SMC helper utility if building on Darwin."""
    if platform.system() != "Darwin":
        print("[INFO] Non-macOS build detected, skipping SMC C helper compilation.")
        return

    current_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(
        current_dir, "src", "pc_diagnostic", "providers", "smc_helper.c"
    )
    binary_path = os.path.join(
        current_dir, "src", "pc_diagnostic", "providers", "smc_helper"
    )

    print(f"[INFO] Compiling native SMC helper tool: {source_path}")
    compile_cmd = [
        "clang",
        "-O3",
        "-framework",
        "IOKit",
        "-framework",
        "CoreFoundation",
        source_path,
        "-o",
        binary_path,
    ]

    try:
        subprocess.run(compile_cmd, check=True)
        print("[SUCCESS] Successfully compiled native macOS SMC helper.")
    except Exception as e:
        print(f"[ERROR] Failed to compile native macOS SMC helper: {e}")
        sys.exit(1)


def build_pyinstaller_binary() -> None:
    """Run PyInstaller using the spec configuration."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    spec_path = os.path.join(current_dir, "pc_diagnostic.spec")

    print(f"[INFO] Launching PyInstaller build with spec: {spec_path}")
    build_cmd = ["pyinstaller", "--clean", spec_path]

    try:
        subprocess.run(build_cmd, check=True)
        print("[SUCCESS] PyInstaller build execution completed.")
    except Exception as e:
        print(f"[ERROR] PyInstaller compilation failed: {e}")
        sys.exit(1)


def verify_build_output() -> None:
    """Verify that the packaged binary has been generated inside the dist folder."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    executable_name = (
        "pc_diagnostic.exe" if platform.system() == "Windows" else "pc_diagnostic"
    )
    target_path = os.path.join(current_dir, "dist", executable_name)

    if os.path.exists(target_path):
        print(
            "[SUCCESS] Standalone PC Diagnostic binary compiled "
            f"successfully: {target_path}"
        )
    else:
        print(f"[ERROR] Packaged binary not found at target location: {target_path}")
        sys.exit(1)


if __name__ == "__main__":
    print("=== PC Diagnostic Standalone Compiler ===")
    compile_mac_helper()
    build_pyinstaller_binary()
    verify_build_output()
    print("=========================================")
