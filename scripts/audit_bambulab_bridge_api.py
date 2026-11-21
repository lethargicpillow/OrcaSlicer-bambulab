#!/usr/bin/env python3
"""Audit exported BambuNetwork symbols in an OrcaSlicer worktree.

This is a static export-inventory check, NOT a binary-ABI or real-printer test.
Exits nonzero when a symbol dynamically requested by Orca is not exported by
the transplanted bridge.  No source code or repository state is modified.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLUGIN = Path("src/slic3r/Utils/BBLNetworkPlugin.cpp")
FORWARDER = Path(
    "src/slic3r/Utils/PJarczakLinuxBridge/"
    "PJarczakBambuNetworkForwarderExports.cpp"
)
ABI_HEADER = Path("src/slic3r/Utils/bambu_networking.hpp")

# The code uses get_function("...") to import symbols dynamically.
DYNAMIC_IMPORT = re.compile(
    r'\bget_function\s*\(\s*"(?P<symbol>bambu_network_[A-Za-z0-9_]+)"\s*\)'
)
# The bridge forwarder defines functions with PJBRIDGE_EXPORT at the beginning
# of the C++ signature (usually one line per export).
BRIDGE_EXPORT = re.compile(
    r'\bPJBRIDGE_EXPORT\b[^\n]*?\b(?P<symbol>bambu_network_[A-Za-z0-9_]+)\s*\('
)

# Functions present in current Orca, absent from the original May 2026 bridge:
KNOWN_NEW_FUNCTIONS = frozenset({
    "bambu_network_get_filament_spools",
    "bambu_network_create_filament_spool",
    "bambu_network_update_filament_spool",
    "bambu_network_delete_filament_spools",
    "bambu_network_get_filament_config",
    "bambu_network_sync_ams_filaments",
})


def load(root: Path, relative: Path) -> str:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"required source does not exist: {path}")
    return path.read_text(encoding="utf-8")


def check(root: Path) -> int:
    plugin_source = load(root, PLUGIN)
    bridge_source = load(root, FORWARDER)
    abi_source = load(root, ABI_HEADER)
    imported = {m.group("symbol") for m in DYNAMIC_IMPORT.finditer(plugin_source)}
    exported = {m.group("symbol") for m in BRIDGE_EXPORT.finditer(bridge_source)}

    if not imported:
        print(f"ERROR: no dynamic Bambu imports parsed from {PLUGIN}", file=sys.stderr)
        return 2
    if not exported:
        print(f"ERROR: no Bambu exports parsed from {FORWARDER}", file=sys.stderr)
        return 2

    missing = sorted(imported - exported)
    extra = sorted(exported - imported)

    print(f"Source root: {root}")
    print(f"Orca imports: {len(imported)}")
    print(f"Bridge exports: {len(exported)}")
    print(f"Missing bridge symbols: {len(missing)}")
    for symbol in missing:
        suffix = " [KNOWN NEW API]" if symbol in KNOWN_NEW_FUNCTIONS else ""
        print(f"  MISSING {symbol}{suffix}")

    print(f"Other bridge exports: {len(extra)}")
    for symbol in extra:
        print(f"  EXTRA   {symbol}")

    generations = ("enum class NetworkAbi", "Legacy", "V0203", "Current", "Unsupported")
    if all(part in abi_source for part in generations):
        print("Orca ABI generation guards: present")
    else:
        print("WARNING: Orca ABI generation guards absent or changed")
        return 1

    if missing:
        print(
            "FAIL: bridge missing entry points. Do not deploy or claim full "
            "BambuNetwork support. This audit does NOT validate function ABI."
        )
        return 1

    print(
        "PASS: symbol-name inventory complete. "
        "Still verify C++ ABI layouts/signatures, JSON/RPC handlers and hardware."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="upstream worktree with bridge sources")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    try:
        return check(root)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
