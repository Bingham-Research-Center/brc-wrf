# BRC research builds

## Canonical source and build provenance

Gigawatts configuration, decisions, status and results live only in the [ub-wx gigawatts handoff](../../ub-wx/experiments/drainage-canyons-gigawatts/handoff/README.md) (ADR-10).

### P2 compile release, 23 October UTC

Job `16434828` completed `0:0` on owned `notch137` in `00:36:56`
(16 CPUs, 64 GiB). Source is `b76fe00b4b0b2997a2a72625dc2da0640a21c4b4`;
release tag: `john/build/wrf-4.8.0-tracers12-20261023`.
The independent build is
`lawson-group6/jrlawson/wrf_build/WRF-4.8.0-tracers12-b76fe00b4b0b-20261023T025123Z`.
Evidence is
`lawson-group6/jrlawson/wrf_build_logs/brc-wrf/tracers12_20261023T025123Z_b76fe00b4b0b`.
Source and generated metadata both confirm exactly `tr17_1..12` in
`tracer_opt=2`. The compiler error scan and tracked source diff are empty;
all four executables exist, and `wrf.exe`/`real.exe` libraries resolve.
The manifest pins executables, configuration, Registry and 90 runtime entries.
`wrf.exe` SHA-256 is
`dc7f1c28c49ad04f3777d0aecd1e1d0f7701e34f87b88b32fc2bd82a9a25066a`.
This record establishes compile provenance only; model acceptance belongs to the experiment entry.

Maintain `john/wrf` as the research source line on the frozen WRF 4.8.0
baseline. Experiment case files coexist on that line. Use short-lived
`john/*` branches for changes that need review, and immutable tags plus
build manifests to identify experiments; a moving branch name is not build
provenance. Upstream ports still follow `BRC_WRF_PORTING_POLICY.md`.
GitHub's default branch is `john/wrf` after the approved 6 October
consolidation. Source tags identify build releases; separate experiment tags
can pin later case/control changes that reuse the same executable build.

A build is a fresh, detached copy of a full source commit and its exact
submodule commits in a unique John-owned directory under
`lawson-group6/jrlawson/wrf_build/`. The maintained compile wrapper is
`brc-cases/build_research_wrf.slurm`. It uses the June-validated Intel
2021.4.0 / MPI 2021.1.1 / HDF5 1.14.3 / netCDF C 4.9.2 and Fortran 4.6.1
stack, legacy configure option 15, basic nesting 1, and eight build CPUs on
notch392. It requires explicit build approval and runs only through Slurm.
Supply `SOURCE SHA BUILD EVIDENCE PROJECT` as its five positional arguments;
`PROJECT` is passed to `write_research_build_manifest.py --project`.

Retain source/submodule identities, configure transcript and file, compiler
and module versions, compile log, generated tracer metadata, linked-library
paths, executable and runtime SHA-256 manifests, and terminal scheduler
state. Compilation is distinct from a successful `real.exe`, restart,
nesting, conservation, stability, or science test.

Every experiment's rendered control must pin the build directory and
manifest, WPS identity, case and namelist, forcing contracts, terrain/lake
edits, tracer seed mapping and script commit, and analysis commit. Copy
the build manifest into its durable control packet. Never silently replace
the build behind an older case's `paths.wrf_build` or overwrite historical
executables. Existing manifests that point at the development checkout
still identify the June binaries there until explicitly migrated.

## 2026-10-06 branch audit

Local and live origin heads were checked. All seven local `john/*` tips
belong to one linear history ending at `5bbcdb705ba7f76f3da8bd2ae7f473c66ffd3bb6`.
`john/wrf` was fast-forwarded 25 commits to that tip for the approved build.
No upstream history was imported. The retired tips are:

| Branch | Local tip | Live origin tip |
| --- | --- | --- |
| `john/ashley-drainage-120m` | `fcd28db7` | same |
| `john/ashley-seiche-case` | `e97b1e15` | absent |
| `john/ashley-storm-600m` | `bbe87c97` | `3c522589` |
| `john/fix-end-to-end-workflow` | `2a7aa9ae` | same |
| `john/green-river-600m` | `5bbcdb70` | absent |
| `john/wrf-no-run-report` | `1244fb3a` | same |

JRL approved consolidation on `john/wrf`. Eight annotated
`archive/john/*/20261006*` tags preserve every listed tip plus the original
`john/wrf` tip `6051d58b`; all were published and their peeled commits checked
on origin before deletion. The six absorbed local branches and four absorbed
remote branches were removed, with explicit expected-tip leases for remote
deletion. Both local and origin now have only `john/wrf` and frozen `master`
(`06d4240a`). No experiment source history was lost.

## Historical 24-scalar build implementation

The October 6 patch extends `Registry/Registry.EM` from eight to 24 `tr17_*`
scalars in `tracer_opt=2`, preserving the I/O, restart, nesting and boundary
flags. The older eight-scalar executables and the released 24-scalar build
remain distinct from the later twelve-scalar release. Use
`check_tracer_registry.py --count 24` for the 24-scalar source or build,
adding `--generated` when auditing compiled allocation metadata.

The first clean parallel attempt, job `16071250` at source `062aa22a`, exposed
a missing dependency: `physics_mmm/bl_shinhong.F90` uses `ccpp_kind_types`,
but only its wrapper declared that prerequisite. The implementation could
compile first, causing Intel error 7002 and cascading PBL errors that make
ignored. It was cancelled and retained as failed evidence. Commit `5a68435c`
adds the implementation prerequisite and rejects ignored compiler errors in
the build wrapper. This is a local build-order fix, with no physics source
change or upstream port. Job `16071302` is the fresh retry, with no object
reuse; it passed the compile acceptance checks below.

## Verified compile release: 6 October 2026

| Item | Verified value |
| --- | --- |
| Release tag (published) | `john/build/wrf-4.8.0-tracers24-20261006` |
| Compiled source | `5a68435cbf6383c717e1492193b771ade99c517c` |
| Job | `16071302`, `COMPLETED`, `0:0`, `00:30:44`, notch392, eight CPUs |
| Build root | `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build/WRF-4.8.0-tracers24-5a68435cbf63-20261006T071850Z` |
| Evidence root | `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/tracers24_20261006T071850Z_5a68435cbf63` |
| Manifest | `build_manifest.json` in the evidence root |
| Executables | `main/wrf.exe`, `main/real.exe`, `main/ndown.exe`, `main/tc.exe` in the build root |

`wrf.exe` SHA-256:
`94b0952fef5e866c2c03a4e9e2543496cc40aaec5415969d75932c89de92c256`.
`real.exe` SHA-256:
`524e6104793080089eca84c2e970d01305fb76771fc642368344bf5b0d3b0d65`.
The evidence contains the other executable/configuration hashes and 90 runtime
file hashes. `configure.wrf` byte-matches the June build's configuration.
All eight submodules are pinned, the source was clean before compilation,
and `post_build_source.diff` is empty. Both source and generated allocation
checks pass for the exact 24-member package. The compiler-error scan is empty,
and `ldd` resolves all libraries for WRF and real. The generated commit
declaration records the full compiled source SHA.

This is compile evidence only. Model acceptance belongs to the experiment
entry. Each new rendered control must adopt an explicit build root and
manifest; historical manifests and binaries retain their recorded paths.
