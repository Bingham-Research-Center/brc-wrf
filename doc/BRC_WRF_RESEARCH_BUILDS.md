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
- Live GitHub checks on 6 October confirm brc-tools PRs
  [66](https://github.com/Bingham-Research-Center/brc-tools/pull/66) and
  [68](https://github.com/Bingham-Research-Center/brc-tools/pull/68) are both
  open; the latter is stacked on the former. The handoff's dependency merges
  are still outstanding. The live ub-wx experiment branch matches `9a6c78ac`.
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
- Hypothesis 2's pool-depth trigger does not distinguish terrain treatments;
  the report proposes a canyon-flux trigger. Hypotheses 8/9 remain placeholders.
  These require author decisions before treatment selection or paper claims.
- The lake's area/alignment mismatch and uncertain non-Flaming-Gorge ice state
  remain inputs to review. Terrain slope predictors do not prove night-time
  stability, and spawning a nest from a restart remains untested here.
- The September `brc-cases/specs/gigawatts_600m.domain.toml` is untracked and
  stale. It is preserved and excluded from this build. Adopt the October
  handoff spec during case preparation, with a saved copy of the old draft.

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
