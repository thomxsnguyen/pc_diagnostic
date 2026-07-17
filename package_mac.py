import os
import subprocess
import sys


def build_dmg() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(current_dir, "dist")
    app_dir = os.path.join(dist_dir, "PC Diagnostic.app")
    macos_dir = os.path.join(app_dir, "Contents", "MacOS")
    resources_dir = os.path.join(app_dir, "Contents", "Resources")

    print("[1/6] Creating App Bundle directory structures...")
    os.makedirs(macos_dir, exist_ok=True)
    os.makedirs(resources_dir, exist_ok=True)

    print("[2/6] Writing launcher script...")
    launcher_path = os.path.join(macos_dir, "launcher")
    launcher_content = (
        "#!/bin/bash\n"
        'DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"\n'
        'osascript -e "tell application \\"Terminal\\" to do script '
        '\\"\'$DIR/pc_diagnostic\'\\"" -e "activate application \\"Terminal\\""\n'
    )
    with open(launcher_path, "w") as f:
        f.write(launcher_content)
    os.chmod(launcher_path, 0o755)

    print("[3/6] Copying binary and setting permissions...")
    src_binary = os.path.join(dist_dir, "pc_diagnostic")
    dest_binary = os.path.join(macos_dir, "pc_diagnostic")
    if not os.path.exists(src_binary):
        print("[ERROR] Source binary not found. Please run build_binaries.py first.")
        sys.exit(1)

    # Copy binary
    subprocess.run(["cp", src_binary, dest_binary], check=True)
    os.chmod(dest_binary, 0o755)

    print("[4/6] Writing Info.plist metadata...")
    plist_path = os.path.join(app_dir, "Contents", "Info.plist")
    plist_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>CFBundleExecutable</key>\n"
        "    <string>launcher</string>\n"
        "    <key>CFBundleIdentifier</key>\n"
        "    <string>com.diagnostic.pc-diagnostic</string>\n"
        "    <key>CFBundleName</key>\n"
        "    <string>PC Diagnostic</string>\n"
        "    <key>CFBundlePackageType</key>\n"
        "    <string>APPL</string>\n"
        "    <key>CFBundleShortVersionString</key>\n"
        "    <string>0.1.0</string>\n"
        "</dict>\n"
        "</plist>\n"
    )
    with open(plist_path, "w") as f:
        f.write(plist_content)

    print("[5/6] Creating ZIP archive...")
    zip_output = os.path.join(dist_dir, "pc_diagnostic_mac_arm64.zip")
    subprocess.run(["zip", "-j", zip_output, src_binary], check=True)
    print(f"[SUCCESS] Standalone ZIP built: {zip_output}")

    print("[6/6] Building Drag-and-Drop DMG Installer...")
    # Check if create-dmg is installed
    try:
        subprocess.run(["create-dmg", "--version"], capture_output=True, check=True)
    except Exception:
        print(
            "[INFO] 'create-dmg' utility is not installed. Installing via Homebrew..."
        )
        try:
            subprocess.run(["brew", "install", "create-dmg"], check=True)
        except Exception as e:
            print(
                "[ERROR] Failed to install 'create-dmg'. "
                f"Please run 'brew install create-dmg' manually. Error: {e}"
            )
            sys.exit(1)

    dmg_root = os.path.join(dist_dir, "dmg_root")
    os.makedirs(dmg_root, exist_ok=True)

    # Copy app bundle to dmg root
    subprocess.run(["cp", "-R", app_dir, dmg_root], check=True)

    # Link Applications
    apps_link = os.path.join(dmg_root, "Applications")
    if not os.path.exists(apps_link):
        os.symlink("/Applications", apps_link)

    output_dmg = os.path.join(dist_dir, "PC-Diagnostic-Installer.dmg")
    if os.path.exists(output_dmg):
        os.remove(output_dmg)

    dmg_cmd = [
        "create-dmg",
        "--volname",
        "PC Diagnostic Installer",
        "--window-pos",
        "200",
        "120",
        "--window-size",
        "500",
        "350",
        "--icon-size",
        "100",
        "--icon",
        "PC Diagnostic.app",
        "130",
        "175",
        "--icon",
        "Applications",
        "370",
        "175",
        output_dmg,
        dmg_root,
    ]
    try:
        subprocess.run(dmg_cmd, check=True)
        print(f"[SUCCESS] Drag-and-Drop DMG built successfully: {output_dmg}")
    except Exception as e:
        print(f"[ERROR] Failed to build DMG installer: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_dmg()
