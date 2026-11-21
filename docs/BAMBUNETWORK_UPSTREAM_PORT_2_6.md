# BambuNetwork bridge migration — OrcaSlicer 2.6

**Status: preparation / API audit, not a completed or validated network port.**
**Base snapshot:** `OrcaSlicer/OrcaSlicer@49b84637eea5ad27905786756c039ecb5d12f09f` (21 November 2026, 2.6.0-dev).
**Legacy source:** `lethargicpillow/OrcaSlicer-bambulab@1b556d73f80e69f512881eab3331e6e9f70e5bf5` (12 May 2026, 2.4.0-dev).

## Objective

Keep the complete *current* OrcaSlicer source as the base, and restore Bambu Lab Device/Monitor, authentication, cloud/LAN connectivity, telemetry, camera, AMS/filament interactions and sending print jobs. Retain all current Orca features and printer-agent integrations. Do **not** replace Orca 2.6 with the older fork or merge the two unrelated repository roots.

## Repository facts

- The user's repository is a fork of `FULU-Foundation/OrcaSlicer-bambulab`; its main branch matches FULU's main. This snapshot has **no usable shared Git history with `OrcaSlicer/OrcaSlicer`** (the old fork contains a squashed initial import).
- The old network solution consists of a cross-platform `pjarczak_bambu_networking_bridge` shared library, a separate Linux host for the Bambu `.so`, an RPC protocol and event pump, and Linux runtime packaging. Windows launches Linux through WSL2; macOS uses Lima.
- The old script `scripts/apply_pjarczak_linux_bridge_orca.py` replaces whole Orca functions. **Never execute it against 2.6.** It would erase version-aware dynamic loading, agent teardown, error handling and plug-in lifecycle changes.
- In the current `src/slic3r/Utils/bambu_networking.hpp`, `NetworkAbi` has **Legacy / V0203 / Current / Unsupported**. Supported network library series include `02.08.04`, `02.03.00`, plus exact legacy. In particular `02.08.01` is intentionally *not* safe to call. Dispatch is implemented by `BBLPrinterAgent.cpp`.
- The May 2026 bridge does not implement the following newer exports requested by Orca 2.6:

  `bambu_network_get_filament_spools`
  `bambu_network_create_filament_spool`
  `bambu_network_update_filament_spool`
  `bambu_network_delete_filament_spools`
  `bambu_network_get_filament_config`
  `bambu_network_sync_ams_filaments`

- Old host `LinuxPluginHost.cpp` calls Linux plug-in `dlopen/dlsym` using the older `PrintParams` layout, and bridge `PJarczakBambuNetworkForwarderExports.cpp` exposes the older signatures. Current `PrintParams` and `bind` signatures are different. Passing either directly is **undefined behavior / possible memory corruption**, not a harmless missing feature.
- The old bridge hard-codes a forced client version `02.05.02.51`. Never equate `SLIC3R_VERSION`, the plugin version, and the RPC compatibility version; they serve distinct purposes.

## Migration strategy

1. **Rebase by new checkout, not git merge.** Clone the official Orca main at the pinned SHA into a separate working directory and create an integration branch there. Use `scripts/bootstrap_bambulab_upstream_port.sh` to copy bridge-specific code only; this is a *scaffold*, not a working patch.
2. **Freeze the RPC contract.** Keep request/response and callback names from the legacy bridge; define a protocol version and an explicit `network_abi` handshake field. Reject incompatible host/bridge combinations before calling a function pointer.
3. **Separate host ABI from Orca ABI.** Keep old Bambu API structs and typedefs in a host-private compatibility header (e.g. `LegacyBambuNetworking.hpp`). Current GUI bridge exports must be compiled with *current* Orca's definitions and convert `PrintParams`, `bind` etc. to versioned, validated JSON. Host deserializes into the exact ABI for its loaded plugin. Do not `reinterpret_cast` incompatible function signatures.
4. **Integrate minimally with current Orca.** Add the bridge CMake target/sources, a side-effect-free capability check, and an opt-in bridge selection at `BBLNetworkPlugin::initialize()`; preserve `resolve_library_path()`, fallback behavior, error localization, `destroy_agent()` before `dlclose/FreeLibrary`, ABI whitelist, and modern `NetworkAgentFactory`. Avoid wholesale replacements of `GUI_App.cpp`.
5. **Implement complete API coverage.** Extend the forwarder, JSON marshalling and Linux host for the six new filament/AMS exports. For any unsupported feature, return a documented error/capability `false`, never fabricated success. Enumerate every imported/forwarded symbol in the audit, and verify signatures separately.
6. **Plug-in download and provenance.** When using the Linux host on non-Linux systems, download an appropriate Linux payload without global HTTP header mutation, validate archive paths against traversal/symlink escapes, verify the payload hash/version manifest before execution, and retain the normal platform plug-in flow outside bridge mode. Never commit proprietary Bambu binaries, credentials, certificates with private keys or generated runtime images.
7. **Runtime packaging.** Linux: host + matching `libbambu_networking.so` and associated `BambuSource` libs. Windows: preserve existing WSL2 bootstrap and clean error messages; assess native Windows backend from FULU PR #40 separately. macOS: verify Lima/QEMU startup, cert trust and host shutdown using fixes from FULU PRs #18 and #49. Do not include checked-in `.build-linux-host` cache or downloaded binary artifacts.
8. **Testing.** Before printing, verify configure/build, exported symbol coverage, ABI compatibility, RPC ping/handshake, process lifecycle/restart, credential isolation, login/logout, cloud connection, LAN discovery, device list, real-time statuses, camera, AMS/filament operations and real printer upload. Include success/error/cancel paths and ensure ordinary non-Bambu agents and slicing are unaffected.

## Acceptance gates

- `python3 scripts/audit_bambulab_bridge_api.py <upstream-worktree>` completes without missing exports.
- The bridge rejects an unsupported plug-in ABI and avoids direct execution of foreign ABI structs.
- Linux build and host integration tests pass with sanitized mock RPC payloads.
- Windows WSL2 and macOS Lima packages contain every required helper/runtime file and pass startup/teardown tests.
- Real printer smoke tests pass: LAN discovery and print; cloud login, device listing/status and cloud print; camera; AMS/filament; reconnect.
- Main branch of the user's existing fork remains unchanged until a separately reviewed, tested change is ready.

## Prior fixes and related work to consider, but not blindly cherry-pick

- FULU [PR #40](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/40): rebase to an intermediate upstream and in-process Windows signed-binary approach; unmerged, huge unrelated diff.
- FULU [PR #18](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/18): macOS RPC deadlocks, media source loading, QEMU/Lima and certificates.
- FULU [PR #49](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/49): ARM macOS Lima runtime/build fixes.
- FULU [PR #64](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/64): Linux ARM64 host via FEX/muvm; opt-in.
- FULU [PR #61](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/61): host stdout socket issue.
- FULU [PR #79](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/79) and [#80](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/80): export manifest parity and `start_publish` host handler.
- FULU [PR #86](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/86) and [#88](https://github.com/FULU-Foundation/OrcaSlicer-bambulab/pull/88): dead runtime arguments, duplicated ABI version literals.

**Do not treat a successful compile, bridge handshake or GitHub Actions green check as proof that a Bambu print works.** The final acceptance requires hardware-level tests.
