# BRC research builds

## Canonical source and experiment identity

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

## Drainage canyons in gigawatts: accepted build scope

Request source: `ub-wx` commit `9a6c78ac1dafc74611809b2e3a0fdb628cdddc7e`,
`experiments/drainage-canyons-gigawatts/handoff/README.md`, following JRL's
3 and 5 October decisions. On 6 October JRL approved the 24-tracer rebuild.
This approval covers compilation and its checks. Model pre-flight submissions
and the 48-hour experiment remain separate decisions.

The patch extends `Registry/Registry.EM` from eight to 24 `tr17_*` scalars in
`tracer_opt=2`, preserving their existing I/O, restart, nesting and boundary
flags. It supplies eleven concentration / concentration-times-initial-theta
pairs and one held pair. Region definitions and seeding remain experiment
configuration. The old eight-tracer executables are retained.

The first clean parallel attempt, job `16071250` at source `062aa22a`, exposed
a missing dependency: `physics_mmm/bl_shinhong.F90` uses `ccpp_kind_types`,
but only its wrapper declared that prerequisite. The implementation could
compile first, causing Intel error 7002 and cascading PBL errors that make
ignored. It was cancelled and retained as failed evidence. Commit `5a68435c`
adds the implementation prerequisite and rejects ignored compiler errors in
the build wrapper. This is a local build-order fix, with no physics source
change or upstream port. Job `16071302` is the fresh retry, with no object
reuse; it passed the compile acceptance checks below.

### Review findings that must survive handoff

- Iteration 6 is a design/theory report with geogrid and preparatory evidence;
  its numerical predictions and 5.4-day runtime estimate are not WRF results.
  The measured pre-flight half is still pending.
- At the compile review, brc-tools PRs 66/68 were still open. The later
  preparation audit confirms both merged with review fixes 69; theory was
  regenerated on `11eccf1`. Live brc-tools main is `c223bcc` (explicit mean
  reference support), with the published nocolons reader fix `49817aa` in PR 72 (21 tests passed). Keep
  theory and execution/diagnostic pins distinct. Current preparation and
  report policy: `../ub-wx/experiments/drainage-canyons-gigawatts/README.md`.
- The handoff says its patch `--check` already passes. On the unmodified
  `5bbcdb70` tree it exits 1 with eight tracers. Its checker also only counts
  declarations, without validating exact package membership. The maintained
  `check_tracer_registry.py` checks both and, after compile, generated metadata.
- `tracer_opt` selects a Registry package, not a scalar count. After this patch
  `tracer_opt=2` advances 24 scalars. Setting twelve to zero with `--fallback6`
  does not produce a twelve-scalar cost benchmark. An eight-scalar comparison
  or twelve-scalar fallback needs a separately pinned build or a reviewed
  package selector; the latter is not part of this build.
- A concentration-weighted initial-theta tag is a useful source-history
  diagnostic. Its ratio minus local theta is not automatically an exact
  parcel cooling or closed heat budget after mixing with other or untagged
  air. Treat closure, tracer transport/mixing, boundary dilution, and the
  low-concentration ratio threshold as scientific validation requirements.
- `real.exe` retains WRF's stock central blob in tracers 1--4. Sunset seeding
  must overwrite all 24 fields on both domains, including the held pair;
  the imported seeder intends this but has not been proven on a restart.
  Pair-temperature fields inherit generic "Dimensionless" Registry metadata;
  the experiment's mapping must declare that even-numbered fields have units K.
- JRL accepted the H2 flux trigger during closure: Lodore below 10% of
  matched truth, with pool depth supporting evidence; carved first if met.
  H7 retains 1 K with continuous effect/supply sensitivity; H8/H9 are exploratory.
- Native MODIS alignment audit 16101184 supports the unshifted grid (99.97%
  category agreement). Shoreline differences and uncertain non-Flaming-Gorge
  ice remain scientific sensitivities. Terrain predictors do not prove night
  stability, and spawning a nest from a restart remains untested here.
- The September domain draft was preserved under the durable closure
  control before adopting the October `brc-cases/specs/gigawatts_600m.domain.toml`.

The reference design is one HRRR 18Z 26 January 2025 forecast through +48 h;
3 km / 600 m, enlarged d01 to the divides, one-way nesting, 100 levels, 9/3 s;
MYNN2, Thompson and Noah; GFS soil only, HRRR snow/skin temperature; observed
26 January lake ice with open cells at 274.15 K; plan-D output and 128 sites.
The carved-terrain run, corridor nest and frozen-lake twin are follow-ups.

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

This is a **compile release**, ready for separately approved model pre-flight
tests. No WPS, real, WRF integration, restart seeding or nest test was run in
this build session. The next case/control packet must adopt this explicit
build root and manifest; historical manifests and the June binaries retain
their existing paths. The stale untracked September gigawatts spec was left
untouched.

## Gigawatts control acceptance: 6 October closure

JRL requested autonomous closure and bounded pre-flight preparation. The new
control is `$WRF_ARCHIVE/gigawatts_600m/control/closure_20261006`; case manifest
`brc-cases/gigawatts_600m.case.yaml` pins this compiled build explicitly.
Audit 16101154 rehashed all six build entries and 90 runtime entries successfully,
rechecked generated tracer metadata, and copied the release manifest into control.
WPS is separately pinned at source `335c76a111f84503e8b963abaf273ea8053645bb`
with executable/configuration hashes. The September domain draft and inherited
documentation edits were saved before adopting the October domain.

`prepare_gigawatts.py` renders geometry through domain_calc and patches the
accepted Green River namelist with declared October settings. Its generated
GFS Vtable excludes SKINTEMP, SNOW and SNOWH; eight soil fields and LANDSEA remain.
Model tests and initial-field checks retain their distinct evidence gates. The
48-hour science run remains unapproved pending measured costs and stability.

Forcing job 16101170 passed the 99-file manifest and 49-hour coverage checks;
WPS job 16101416 consumes the pinned source and rechecks product/time coverage
and every hash. `gigawatts_real.slurm` applies the lake state only to local
copies and refuses failed metgrid or initial-field checks. Eight ranks fit
initialization into the available node slot; the smoke comparisons remain at
56 ranks on notch392. `gigawatts_smoke.slurm` prepares one bounded test at a
time, with a six-hour backstop and no automatic resubmission. It checks actual
output clocks, all-rank logs, and records integration/writing costs. The seeded
variant runs two 15-minute segments and checks transported pair ratios, held
tags, partition sum and dilution separately from initialization. Regression
job 16101447 passed 28 controller, clock and transport tests. These synthetic
checks are not substitutes for the pending model evidence.
