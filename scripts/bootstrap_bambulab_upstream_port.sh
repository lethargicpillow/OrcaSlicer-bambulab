#!/usr/bin/env bash
# Create a CLEAN Orca 2.6 porting worktree from upstream, with bridge-only sources.
# Does not patch production integration files and does not claim working BambuNetwork.
set -euo pipefail

UPSTREAM_URL="https://github.com/OrcaSlicer/OrcaSlicer.git"
BRIDGE_URL="https://github.com/lethargicpillow/OrcaSlicer-bambulab.git"
UPSTREAM_SHA="49b84637eea5ad27905786756c039ecb5d12f09f"
BRIDGE_SHA="1b556d73f80e69f512881eab3331e6e9f70e5bf5"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-}"
if [[ -z "$DEST" ]]; then
  echo "usage: $0 /path/to/new/workspace" >&2
  exit 2
fi

for command in git python3 cp mkdir; do
  command -v "$command" >/dev/null || { echo "missing tool: $command" >&2; exit 2; }
done

DEST="$(realpath -m -- "$DEST")"
if [[ -e "$DEST" ]]; then
  echo "refusing to overwrite existing path: $DEST" >&2
  exit 2
fi
mkdir -p "$DEST"
# If either clone fails, preserve the directory for diagnosis, but never
# remove user files or existing working trees.
git clone --no-checkout "$UPSTREAM_URL" "$DEST/upstream"
git -C "$DEST/upstream" checkout --detach "$UPSTREAM_SHA"
git -C "$DEST/upstream" switch -c port/bambulab-network-orca-2.6

git clone --no-checkout "$BRIDGE_URL" "$DEST/legacy-source"
git -C "$DEST/legacy-source" checkout --detach "$BRIDGE_SHA"

# Deliberately copied only bridge-specific sources, never the old Orca main
# code, BBLNetworkPlugin.cpp, GUI_App.cpp or dynamic plugin ABI headers.
COPY_PATHS=(
  "src/slic3r/Utils/PJarczakLinuxBridge"
  "tools/pjarczak_bambu_linux_host"
  "tools/pjarczak_bambu_macos_linux_wrapper"
  "tools/pjarczak_bambu_runtime"
)
for p in "${COPY_PATHS[@]}"; do
  [[ -d "$DEST/legacy-source/$p" ]] || { echo "missing bridge sources: $p" >&2; exit 1; }
  mkdir -p "$DEST/upstream/$(dirname "$p")"
  cp -a -- "$DEST/legacy-source/$p" "$DEST/upstream/$p"
done

# Build caches should never be transferred into source control.
rm -rf -- "$DEST/upstream/tools/pjarczak_bambu_linux_host/.build-linux-host"

# Documentation/test script from this preparatory branch, not the legacy
# script that rewrites entire functions.
mkdir -p "$DEST/upstream/docs" "$DEST/upstream/scripts"
cp -- "$SCRIPT_DIR/../docs/BAMBUNETWORK_UPSTREAM_PORT_2_6.md" "$DEST/upstream/docs/"
cp -- "$SCRIPT_DIR/audit_bambulab_bridge_api.py" "$DEST/upstream/scripts/"
chmod +x "$DEST/upstream/scripts/audit_bambulab_bridge_api.py"

echo
echo "Staging complete: $DEST/upstream"
echo "The bridge is NOT integrated or buildable yet."
echo "Running static API audit (expected to FAIL until newer APIs are ported):"
set +e
python3 "$DEST/upstream/scripts/audit_bambulab_bridge_api.py" "$DEST/upstream"
audit_rc=$?
set -e
echo "Audit exit status: $audit_rc"
echo
echo "Next: implement the version-aware bridge adapter and host RPC handlers,"
echo "integrate targets in CMake, build/test; do not run the old patching script."
