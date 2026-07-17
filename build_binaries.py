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


def sign_binary(target_path: str, description: str) -> None:
    """Perform code signing on macOS for a specific binary."""
    if platform.system() != "Darwin":
        return
    if not os.path.exists(target_path):
        return

    # Determine signature identity: default to ad-hoc "-" if not specified
    identity = os.environ.get("CODESIGN_IDENTITY", "-")
    print(f"[INFO] Signing {description} with identity: {identity}")

    if identity == "-":
        # For local ad-hoc signing, do not enforce hardened runtime to allow
        # loading Python shared libraries from different Team IDs.
        sign_cmd = [
            "codesign",
            "--force",
            "--sign",
            identity,
            target_path,
        ]
    else:
        # For production Developer ID distribution, use entitlements file
        # with library validation disabled.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        entitlements_path = os.path.join(current_dir, "entitlements.plist")

        # Write entitlements plist dynamically if missing
        if not os.path.exists(entitlements_path):
            plist_content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0">\n'
                "<dict>\n"
                "    <key>com.apple.security.cs.disable-library-validation</key>\n"
                "    <true/>\n"
                "</dict>\n"
                "</plist>\n"
            )
            with open(entitlements_path, "w") as f:
                f.write(plist_content)

        sign_cmd = [
            "codesign",
            "--force",
            "--options",
            "runtime",
            "--entitlements",
            entitlements_path,
            "--sign",
            identity,
            target_path,
        ]

    try:
        subprocess.run(sign_cmd, check=True)
        print(f"[SUCCESS] Signed {description} at {target_path}")
    except Exception as e:
        print(f"[WARNING] Failed to sign {description}: {e}")


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

    # 1. Compile native helper on macOS
    compile_mac_helper()

    # 2. Code-sign nested helper binary (macOS specific) before packaging
    current_dir = os.path.dirname(os.path.abspath(__file__))
    helper_path = os.path.join(
        current_dir, "src", "pc_diagnostic", "providers", "smc_helper"
    )
    sign_binary(helper_path, "SMC Helper C tool")

    # 3. Build standalone executable
    build_pyinstaller_binary()

    # 4. Code-sign the final application bundle (macOS specific)
    executable_name = "pc_diagnostic"
    exe_path = os.path.join(current_dir, "dist", executable_name)
    sign_binary(exe_path, "Main Application Bundle")

    # 5. Verify build output
    verify_build_output()
    print("=========================================")
