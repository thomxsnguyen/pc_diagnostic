from __future__ import annotations

import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from build_binaries import sign_binary

APP_NAME = "PC Diagnostic"
BUNDLE_ID = "com.diagnostic.pc-diagnostic"
VERSION = "0.1.0"


def app_plist() -> dict[str, object]:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": "pc_diagnostic",
        "CFBundleIconFile": "AppIcon",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    }


def _paint_icon(path: Path, size: int) -> None:
    from PySide6.QtCore import QPointF, QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#101826"))
    painter.setPen(QColor("#00E5FF"))
    margin = max(1, size // 24)
    painter.drawRoundedRect(
        QRect(margin, margin, size - 2 * margin, size - 2 * margin),
        size // 5,
        size // 5,
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#F0F6FC"))
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(size * 0.55, size * 0.16),
                QPointF(size * 0.28, size * 0.55),
                QPointF(size * 0.47, size * 0.55),
                QPointF(size * 0.38, size * 0.84),
                QPointF(size * 0.72, size * 0.43),
                QPointF(size * 0.52, size * 0.43),
            ]
        )
    )
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not create icon image: {path}")


def create_app_icon(resources_dir: Path, work_dir: Path) -> Path:
    """Generate a complete macOS iconset and compile it into AppIcon.icns."""
    iconset = work_dir / "AppIcon.iconset"
    iconset.mkdir(parents=True)
    variants = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for filename, size in variants.items():
        _paint_icon(iconset / filename, size)
    output = resources_dir / "AppIcon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True
    )
    return output


def create_app_bundle(project_dir: Path) -> Path:
    dist_dir = project_dir / "dist"
    source_binary = dist_dir / "pc_diagnostic"
    if not source_binary.is_file():
        raise FileNotFoundError(
            "dist/pc_diagnostic was not found; run build_binaries.py first"
        )

    app_dir = dist_dir / f"{APP_NAME}.app"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    macos_dir = app_dir / "Contents" / "MacOS"
    resources_dir = app_dir / "Contents" / "Resources"
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    destination = macos_dir / "pc_diagnostic"
    shutil.copy2(source_binary, destination)
    destination.chmod(0o755)
    with (app_dir / "Contents" / "Info.plist").open("wb") as plist_file:
        plistlib.dump(app_plist(), plist_file, fmt=plistlib.FMT_XML)

    with tempfile.TemporaryDirectory(prefix="pc-diagnostic-icon-") as temp_dir:
        create_app_icon(resources_dir, Path(temp_dir))

    sign_binary(str(app_dir), "PC Diagnostic application bundle")
    return app_dir


def create_dmg(project_dir: Path, app_dir: Path) -> Path:
    create_dmg_tool = shutil.which("create-dmg")
    if create_dmg_tool is None:
        raise RuntimeError(
            "create-dmg is required. Install it with: brew install create-dmg"
        )

    output = project_dir / "dist" / "PC-Diagnostic-Installer.dmg"
    if output.exists():
        output.unlink()
    with tempfile.TemporaryDirectory(prefix="pc-diagnostic-dmg-") as temp_dir:
        staging = Path(temp_dir)
        shutil.copytree(app_dir, staging / app_dir.name)
        subprocess.run(
            [
                create_dmg_tool,
                "--volname",
                "PC Diagnostic Installer",
                "--window-size",
                "500",
                "350",
                "--icon-size",
                "100",
                "--icon",
                app_dir.name,
                "130",
                "175",
                "--app-drop-link",
                "370",
                "175",
                str(output),
                str(staging),
            ],
            check=True,
        )
    return output


def build_dmg() -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("macOS packaging must run on macOS")
    project_dir = Path(__file__).resolve().parent
    app_dir = create_app_bundle(project_dir)
    output = create_dmg(project_dir, app_dir)
    print(f"[SUCCESS] macOS installer created: {output}")
    return output


if __name__ == "__main__":
    try:
        build_dmg()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
