# BRC WRF Microtask Handoff

This is the WRF-run-side control board for a Codex session picking up current
proof state, run-tuning, science-review, and documentation-refresh work.
`AGENTS.md` is only the router; keep the live queue and evidence here.

For the AI-optimized route to the overarching end-to-end goal, including
compiling John's fork for CHPC, pairing it with a John-owned WPS root, and using
Michael's proven path only as a yardstick, read
`doc/BRC_WRF_END_TO_END_AI_HANDOFF.md`.

It is intentionally a planning and routing artifact. It is not approval to run
DTN staging, WPS, `real.exe`, `wrf.exe`, Slurm submissions, scaling sweeps, or
large downloads.

## Active Goal For Next Session

Use `BRC_WRF_EXPERIMENT_TODO.md` for the current task and
`BRC_WRF_RESEARCH_BUILDS.md` for the 6 October gigawatts build and branch
consolidation. The Pelican evidence below is the previous completed goal.

## Previous Completed Goal: Pelican Feedback Suite

Current user-selected goal is closed: the default-terrain GFS one-way member
completed in preparation `13894268`, WRF `13894282`, and quicklooks `13896648`.
It reused the accepted X6 GFS `met_em` inputs, changed only
`feedback = 1 -> 0`, and did not rerun WPS. The four-run GFS/NAM by
one-/two-way factorial analysis `13896641` and full-figure/convergence jobs
`13896642`, `13896828`, and `13896871` also completed. The next step is
manuscript and human science review, not another default-terrain WRF run.

Read in this order after `AGENTS.md`:

1. `brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md`
2. `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md`
3. `brc-docs/BRC-WRF-PELICAN-RAP-FEASIBILITY.md` only if RAP is explicitly revived
4. `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md`
5. `../brc-tools/docs/WRF-INPUT-STAGING.md`
6. `../brc-tools/docs/nwp/NWP-SOURCE-MATRIX.md`

For any sibling `brc-tools` Python/Herbie/source-planning command, force the
maintained environment with `conda run -n brc-tools-2026 ...` or the absolute
`/uufs/chpc.utah.edu/common/home/u0737349/software/pkg/miniforge3/envs/brc-tools-2026/bin/python`.
Do not trust the inherited shell environment; recent Codex sessions inherited
`clyfar-nov2025`, which carries older Herbie and is not the WRF-staging env.

John approved the GFS end-to-end WRF-side hot-swap on 2026-06-30. It consumed
the staged `brc-tools` contract for `pelican2013_gfs_3_1_333m_75lev` and reused
the Pelican NAM namelists with `interval_seconds = 21600`.

| Run | Job | Result | Evidence |
| --- | --- | --- | --- |
| GFS analysis full6h | `13753673` | `COMPLETED`, `0:0`, elapsed `01:42:51`; `wrf.exe` step elapsed `01:41:14`; WPS, `real.exe`, `wrf.exe`, and archive phases all exited `0`. | Archive: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_gfs_3_1_333m_75lev/full6h/run_20260630T181555Z/`; debug: `.../debug/`; control: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_gfs_3_1_333m_75lev/control/run_20260630T181555Z/`. |
| NAM/GFS standardized quicklooks | `13755401` | `COMPLETED`, `0:0`, elapsed `00:01:38`; both quicklook checks returned `OK: no findings` and `brc-tools manifest: verify: 2/2 OK`. | Summary: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_gfs_compare/control/quicklooks_20260630T214000Z/quicklook_summary_13755401.tsv`; outputs: NAM and GFS each have 30 PNGs under `quicklooks/standardized_compare_20260630T214000Z/`, 10 per d01/d02/d03. |
| NAM one-way feedback full6h | `13788264` | `COMPLETED`, `0:0`, elapsed `02:12:32`; `wrf.exe` step elapsed `02:11:26`; `real.exe`, `wrf.exe`, success-marker, and archive phases all exited `0`. | Archive: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway/full6h/run_20260702T053120Z/`; debug: `.../debug/`; control: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway/control/run_20260702T053120Z/`. |
| NAM one-way feedback quicklooks | `13791045` | `COMPLETED`, `0:0`, elapsed `00:00:53`; rendered 30 PNGs, 10 per d01/d02/d03. First attempt `13791008` failed because `brc-tools-2026` lacked the xarray NetCDF backend; retry used the proven `clyfar-nov2025` NetCDF/render stack with `PYTHONPATH` pointed at `../brc-tools`. | Summary: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway/control/run_20260702T053120Z/quicklook_summary_retry_13791045.tsv`; outputs: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway/full6h/run_20260702T053120Z/quicklooks/dXX/`. |
| Supplemental Pelican quicklooks | `13792197` | Completed from log evidence on `notch392`; rendered 12 add-on PNGs per case, 4 per d01/d02/d03, for NAM, GFS, and NAM one-way. `sacct` accounting was unavailable after completion due to a transient SlurmDBD connection error, but the job log finished with all three case rows and `squeue` no longer listed the job. | Summary: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_gfs_compare/control/quicklooks_supplemental_20260702T082027Z/quicklook_supplemental_summary_13792197.tsv`; log: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/quicklook_pelican333_supplemental_13792197.out`; outputs: `_600hPa/01_600hPa_height_rh_wind_barbs.png` at 1-hour lead plus `_4h/{01_t2_10m_wind.png,04_10m_wind_speed.png,06_snow_depth.png}` at 4-hour lead under each domain directory. |

The matched GFS one-way row is now accepted WRF-side evidence. Preparation
`13894268` reused six verified X6 `met_em` files; WRF `13894282` completed with
21 hourly files and an empty error scan; quicklooks `13896648` wrote 54 PNGs.
The exact archive is
`/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_gfs_3_1_333m_75lev_oneway/full6h/run_20260710T234000Z/`.
Manuscript analysis `13896641`, publication jobs `13896642`/`13896828`, and
exact-config convergence `13896871` completed outside this repo; X10 has 63
publication PNGs and the study compare root has 247.

GFS acceptance facts:

```text
Vtable.GFS, fg_name GFS, interval_seconds 21600
num_metgrid_levels = 27
NUM_METGRID_SOIL_LEVELS = 4
SUCCESS COMPLETE REAL_EM INIT
SUCCESS COMPLETE WRF
21 archived wrfout files: d01/d02/d03 hourly 12Z through 18Z
```

NAM one-way feedback acceptance facts:

```text
source/forcing unchanged from NAM baseline: Vtable.NAM, fg_name NAM, interval_seconds 21600
namelist.input diff: feedback = 1 -> feedback = 0 only; smooth_option retained at 0
num_metgrid_levels = 40
num_metgrid_soil_levels = 4
SUCCESS COMPLETE REAL_EM INIT
SUCCESS COMPLETE WRF
21 archived wrfout files: d01/d02/d03 hourly 12Z through 18Z
```

Terrain-fidelity rerun constraint:

```text
reference run: 13788264, NAM one-way feedback=0
coarse terrain comparison run: 13847980, case pelican2013_nam_3_1_333m_75lev_oneway_terrain5m
control: /uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain5m/control/run_20260707T182414Z/
archive: /uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain5m/full6h/run_20260707T182414Z/
WPS HGT_M source: gmted2010_5m via topo_gmted2010_5m overlay; this is 5 arc-minutes, not 5 metres
namelist carry-forward: feedback = 0; smooth_option = 0
WRF proof: completed 0:0, SUCCESS COMPLETE WRF, 21 archived wrfout files, no fatal/CFL/NaN markers
quicklook proof: job 13848733 completed 0:0, 42 PNGs under quicklooks/dXX/
next run: custom 3s HGT_M, same NAM one-way conveyor, fresh terrain3s wrappers, geogrid-only proof before WRF
```

John approved the end-to-end RAP sensitivity attempt on 2026-06-30, with the
condition that the run stop before unsafe WRF startup. Two approved WPS-only
Slurm proofs were run on `notch392`; both stopped before `real.exe`, `wrf.exe`,
quicklooks, or the full conveyor.

| Proof | Job | Vtable | Result | Disposition |
| --- | --- | --- | --- | --- |
| Hybrid RAP | `13744756` | `Vtable.RAP.hybrid.ncep` | `ungrib.exe` and `metgrid.exe` completed and wrote 21 `met_em` files, but the sample header had no `num_metgrid_levels` dimension and no real-ready 3D atmospheric stack. | Not safe for `real.exe`. |
| Pressure RAP | `13745030` | `Vtable.RAP.pressure.ncep` | `ungrib.exe` and `metgrid.exe` completed and wrote 21 `met_em` files with `num_metgrid_levels = 38`; 3D `PRES`, `GHT`, `RH`, `UU`, `VV`, and `TT` are present. | Still not safe for `real.exe`: no layered soil temperature/moisture fields and `NUM_METGRID_SOIL_LEVELS = 0`. |

Key evidence:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/wps_pelican2013_rap_3_1_333m_75lev_13744756.out
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/wps_pelican2013_rap_3_1_333m_75lev_13745030.out
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_rap_3_1_333m_75lev/wps_field_proof/wps_field_proof_13744756_20260630T054317Z/debug/
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_rap_3_1_333m_75lev/wps_field_proof/wps_field_proof_13745030_20260630T054748Z/debug/
```

The adjacent `brc-tools` repo staged and verified only this single source bundle:
`/scratch/general/vast/$USER/wrf_inputs/pelican2013_rap_3_1_333m_75lev/` with
7 hourly NCEI `rap_130` files, `rap_analysis`, `wps_fg_name = ["RAP"]`, and
`interval_seconds = 3600`. That contract is useful but incomplete for WRF
startup as currently staged.

If RAP is explicitly revived, the next useful RAP work is one of:

1. Fix source/product staging in `brc-tools` so RAP supplies both the pressure
   atmospheric stack and usable land-state/soil layers.
2. Design an explicit RAP atmosphere plus NAM (or other) filler stream, clearly
   labeling it as not RAP-only.

For the current poor man's ensemble goal, do not spend the next session on
unchanged RAP or repeat GFS source-support. NAM and GFS now exist, and the
paired standardized quicklooks are rendered; the next default is side-by-side
science review.

Do not run `real.exe` against either RAP-only WPS output above. The
pre-existing packet renderer remains available for reproducing WPS-only proofs
with adjusted source products:

```bash
python brc-cases/wrf_case.py render-wps-field-proof \
  brc-cases/pelican2013_rap_3_1_333m_75lev.case.yaml \
  --output-dir /uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_rap_3_1_333m_75lev/control/wps_field_proof_<UTC>
```

The generated packet already exists at
`/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_rap_3_1_333m_75lev/control/wps_field_proof_20260630T052737Z/`.
It has already been submitted and failed field adequacy, so do not rerun it
unchanged. The next useful WPS-only proof should use either a corrected RAP
source product that contains land-state/soil layers or an explicitly approved
filler-stream design. The proof currently reuses the NAM 333 m baseline
`geo_em` files from scratch; if they have expired, restore them or explicitly
approve a geogrid rerun before continuing.

## Rot Guard And Single-Truth Rules

- `AGENTS.md` stays short: ownership, cold-start order, approval boundaries, and
  durable gotchas only.
- This file owns current queue state, task counts, remaining approvals, and
  operational evidence pointers.
- Workflow SOPs own procedures: use `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` for
  staged WRF runs and quicklook placement, and `brc-cases/README.md` for case
  helpers.
- `brc-tools` owns reusable staging and visualization primitives. `brc-wrf`
  adapts WRF files to those helpers.
- Do not create a new handoff, priority menu, or roadmap when an existing slot
  above can be updated.
- Prefer one short pointer in secondary docs over copied tables that will drift.

## Current Gate State

As of 2026-06-18, Roadmap Gates 0-11 have passed for the John-owned WRF/WPS
proof, fresh NAM-only `brc-tools` contract, NAM-only WPS/`real.exe`/`wrf.exe`
rerun, archive, quicklooks, and a maintained render-only practical-test
harness. Scaling and memory sweeps remain separate approval-gated runs.

As of 2026-06-27, Pelican comparison quicklooks are standardized through
`brc-cases/wrf_quicklook.py`: it discovers the case domains, consumes raw WRF
outputs, and renders 10 PNGs per domain under per-domain subdirectories below
`<archive-run>/quicklooks/`. Generic pcolormesh/vector/cross-section plotting
lives in `../brc-tools/brc_tools/visualize/grid.py`; do not duplicate those
plotting primitives in this repo.

As of 2026-06-30, RAP-only field adequacy is blocked before `real.exe`.
Hybrid-Vtable RAP did not produce a real-ready vertical atmosphere, and
pressure-Vtable RAP produced a 38-level atmosphere but no layered soil
temperature/moisture fields. Treat this as a source-product or filler-design
problem outside the WRF run conveyor.

As of 2026-06-30, GFS analysis completed the WRF-side hot-swap that RAP could
not: WPS produced `num_metgrid_levels = 27` and `NUM_METGRID_SOIL_LEVELS = 4`,
`real.exe` and `wrf.exe` completed, and the archive contains 21 hourly WRF
outputs for d01/d02/d03 from 12Z through 18Z.

As of 2026-06-30, NAM/GFS comparison quicklooks are rendered under the same
stamp, `standardized_compare_20260630T214000Z`. Slurm job `13755401` completed
with `0:0`; each forcing has 30 PNGs, 10 per d01/d02/d03, using matching
product names for like-for-like review.

As of 2026-07-02, the NAM one-way-feedback sensitivity is complete. It reused
the proven NAM WPS/metgrid artifacts and John-owned WRF build, changed only
`feedback = 1` to `feedback = 0` in `namelist.input`, retained
`smooth_option = 0`, completed WRF job `13788264`, archived 21 hourly WRF
outputs, and rendered 30 quicklook PNGs in retry job `13791045`.

As of 2026-07-02, supplemental Pelican quicklooks are rendered for all three
completed 333 m runs: NAM two-way, GFS, and NAM one-way. Job `13792197` added
four nested products per domain without deleting parent quicklooks: one
`_600hPa` product from 2013-02-02 13Z and three `_4h` surface products from
2013-02-02 16Z.

As of 2026-07-10, the matched GFS one-way feedback run and its post-processing
are complete. This closes the default-terrain GFS/NAM by one-/two-way matrix;
the five-hour analysis shows the GFS--NAM stability and transport-wind
separation under both feedback modes, with a much smaller source-conditioned
feedback interaction.

As of 2026-06-30, ERA5 is not ready for immediate staging in local evidence:
`brc-tools` has no `era5` source, `cdsapi`/`ecmwfapi` are absent even in
`brc-tools-2026`, and no CDS credentials are configured. WPS-side support is
plausible via John's `Vtable.ECMWF`, but ERA5 needs a CDS-backed pressure-level
plus single-level/land request path before any WPS proof. FNL remains an
optional third-source path if John wants another independent NWP run before
solving ERA5 access.

The file includes `brc-tools` tasks because WRF cannot safely consume staged
forcing until the manifest/contract side is trustworthy. Keep implementation
batches repo-clean:

| Repo | Owns | Do not do there |
| --- | --- | --- |
| `brc-wrf` | WRF source, WPS/WRF consumption docs, case manifests, validators, run templates, benchmark plans, and WRF-output quicklook adapters. | NWP downloader, GRIB staging logic, or reusable plotting primitives. |
| `brc-tools` | GRIB download/staging, manifests, contracts, token checks, input quicklooks, and reusable visualization helpers. | WPS, `real.exe`, `wrf.exe`, or WRF run Slurm profiles. |
| `brc-knowledge` | Canonical CHPC node, storage, scheduler, proxy, and validated script facts. | Repo-local code or case manifests. |

Hot-swap rule for the current Pelican work: add and test one forcing source at
a time in `brc-tools`, then consume its contract in `brc-wrf`. NAM and GFS now
form the first comparison pair. The older GEFS+NAM two-stream idea is parked
and should not be treated as the default next proof. The NAM one-way-feedback
run is a WRF-side feedback sensitivity, not a new `brc-tools` forcing source.

## Codex Cold Start

Start in `~/gits/brc-wrf` and keep the first pass small:

1. `git status --short --branch --untracked-files=no`
2. `sed -n '1,180p' AGENTS.md`
3. `sed -n '1,220p' doc/BRC_WRF_EXPERIMENT_TODO.md`
4. `sed -n '1,220p' brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md`
5. `sed -n '1,140p' brc-docs/BRC-WRF-STATE-PLAYBOOK.md`
6. `sed -n '1,180p' brc-docs/BRC-WRF-FIRST-CASE.md`
7. `sed -n '1,130p' ../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md`

This file is now the detailed evidence ledger. Read it only when the shorter
todo or a task-specific owner doc points here. Do not broad-scan WRF source or
load high-token scripts until `rg` points to a specific function, test, or doc
section.

Login-node-safe checks from this repo:

```bash
python brc-cases/wrf_case.py validate \
  brc-cases/jan2013_basin_nam.case.yaml

git diff --check
```

Off-login no-run practical checks include manifest verification, strict case
validation that reads staged/archive paths, quicklook checks/renders, NetCDF
reads, and archive inventories. Run those only inside an approved Slurm batch or
interactive compute context.

Do not run WPS, `real.exe`, `wrf.exe`, `sbatch`, scaling sweeps, or large
download/stage commands without explicit human approval. Do not run practical
WRF checks on login nodes. If a command reads manifests, staged GRIBs, WPS/WRF
NetCDF files, archives, or renders quicklooks, it belongs in an approved
interactive/batch compute context.

## 2026-06-17 Practical No-Run Test Pass Retrospective

This pass was executed from `notchpeak1` login at about 2026-06-17 14:56 MDT.
It was not a Slurm job. No `salloc`, `sbatch`, WPS, `real.exe`, or `wrf.exe`
execution was started. This is now a lesson learned, not a pattern to repeat:
future practical tests must not run on login nodes.

Why it was fast: the commands reused existing proof artifacts. They rehashed
the staged GRIB files, validated case metadata/contracts, rendered Slurm text,
read existing `met_em`/`wrfout` NetCDF files, and wrote PNGs. They did not
download new data, run ungrib/metgrid, integrate WRF, or transfer a new archive.

Data locations from this pass:

| Data | Path | Persistence |
| --- | --- | --- |
| Source and docs | `~/gits/brc-wrf`, `~/gits/brc-tools` | Git-tracked, small only. |
| Staged forcing read by checks | `/scratch/general/vast/$USER/wrf_inputs/jan2013_basin_gefs/` | Scratch; 60-day atime purge. |
| Existing WPS/WRF run artifacts read by checks | `/scratch/general/vast/$USER/wrf_runs/jan2013_basin_gefs/` | Scratch; active/reproducible run I/O. |
| Durable proof archive read by quicklooks | `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/jan2013_basin_gefs/run_20260613T044846Z/` | Durable group archive. |
| Quicklook PNGs generated by this pass | moved to `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/jan2013_basin_gefs/run_20260613T044846Z/quicklooks/`; future default is `<archive-run>/quicklooks/dXX/` | Durable archive location; repo-local PNG output is disallowed. |

Observed results:

| Check | Result |
| --- | --- |
| `brc-tools` focused tests | `39 passed, 2 skipped`. |
| `python -m py_compile brc-cases/wrf_case.py brc-cases/wrf_quicklook.py` | Passed. |
| Existing manifest verification | `28/28 OK`. |
| Case validation and strict validation | `OK: no findings`. |
| Slurm render | Text only; confirmed `lawson-np`, `notch392`, 56 tasks, `900G`, `srun --mpi=pmi2`. |
| Quicklook check/render | Wrote five PNGs from existing WPS/WRF artifacts. |
| No-download staging plans | NAM plan: 7 files, at least 840 MB; GEFS c00 plan: 21 variable-level files, sizes unknown offline. |

What can improve next:

| Improvement | Why | Stop point |
| --- | --- | --- |
| Add a one-command no-run report wrapper. | Done in `wrf_case.py render-no-run-report`; reduces manual copy/paste and captures command, result, hostname, commit, and artifact paths. | Wrapper writes under `/tmp` by default; no WPS/WRF, strict artifact reads, or quicklooks. |
| Add quicklook summary stats beside PNGs. | Helps discuss min/max fields and catch blank or unit-broken plots without eyeballing only. | Print/table stats from existing NetCDF files. |
| Add Basin/obs overlays to WRF-output quicklooks. | Makes plots more useful for John/Michael meteorological review. | Existing artifacts only; no network unless explicitly approved. |
| Validate a fresh NAM contract sidecar. | Retires the reconstructed legacy fallback only after current `brc-tools` output proves clean. | `wrf_case.py validate --strict-files` passes against fresh `contract_<case>.json`. |
| Run live S3 token preflight once. | Confirms the new `brc-tools` token preflight against the real GEFSv12 S3 listing. | One metadata request; no GRIB download. |
| Benchmark tasks and memory. | Current `900G`/56-task profile is safe and high-power, not proven efficient. | Human-approved Slurm sweep with timing/memory/archive evidence. |

Static Slurm alignment check:

| Item | Current rendered setting | CHPC guidance |
| --- | --- | --- |
| Account/partition | `lawson-np` / `lawson-np` | Matches owned Notchpeak WRF default. |
| Node | `notch392` | Matches preferred big-memory WRF workhorse. |
| Shape | one node, 56 tasks, `900G` | Matches `wrf-on-chpc-quickstart.md` validated template. |
| Launcher | `real.exe` direct; `wrf.exe` via `srun --mpi=pmi2` | Matches the Intel MPI fix. |
| Live I/O | scratch run directory | Matches CHPC scratch policy for WRF I/O. |
| Archive | `lawson-group6/.../wrf_archive/<case>/run_<UTC>/` | Matches durable archive policy and preferred group volume. |
| Colon-safe wrfout copy | `rsync -av ./wrfout_d0* ...` | Matches the confirmed WRF filename gotcha. |

Before a real rerun, render the script inside the next session and compare it to
`../brc-knowledge/scholarium/reference-base/resources/wrf-on-chpc-quickstart.md`
and `run_wrf_feb05.slurm`. Do not render or run it from a login node if the
render path performs practical checks.

## Progress Survey

| Area | Current state | Evidence or next check |
| --- | --- | --- |
| NAM-only Jan-2013 proof | Fresh proof passed through WPS, `real.exe`, `wrf.exe`, archive, and quicklooks on 2026-06-18. | Gates 5-10 evidence under `/scratch/general/vast/u0737349/wrf_inputs/jan2013_basin_gefs/` and `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/`. |
| Input contract handshake | Fresh `brc-tools` NAM-only sidecars now exist on scratch and verify `7/7 OK`; strict `brc-wrf` validation passed off-login. The tracked reconstructed contract remains a fallback until retirement is explicit. | Manifest and contract under `/scratch/general/vast/u0737349/wrf_inputs/jan2013_basin_gefs/`; Gate 5 logs `gate5_nam_contract_13539969.out` and `gate5_validate_13539980.out`. |
| Parked GEFS+NAM two-stream | Not proven and not current. Treat only as an explicitly revived WPS/field-coverage design task. | `../brc-tools/docs/WRF-GEFS-NAM-FIELD-MAP.md`; stop before `real.exe`. |
| WRF run tuning | Not benchmarked. Current max owned-node profile is a safe high-power default, not the efficiency knee. | Prepare 16/28/56 task and memory tables; no `sbatch` without approval. |
| CHPC settings | Rechecked 2026-06-17 against `brc-knowledge`: WRF default remains single-node `notch392` on `lawson-np`; avoid multi-node for Basin-scale cases unless memory/size proves it. | `../brc-knowledge/scholarium/reference-base/resources/chpc-team-resource-inventory.md`; `wrf-on-chpc-quickstart.md`; `chpc-slurm-job-examples.md`. |
| John-owned WPS proof | Passed 2026-06-18 from official WPS v4.6.0 source. | `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/gate3_20260618T054456Z_13539773/`; WPS root `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build/WPS`. |
| Case-root metadata review | Passed 2026-06-18. | `/tmp/jan2013_basin_nam.gate4.20260618T054655Z.report.txt`; rendered review `/tmp/jan2013_basin_nam.gate4.20260618T054655Z.rendered.slurm`; not submitted. |
| Docs/router state | `doc/BRC_WRF_EXPERIMENT_TODO.md` is the active todo; this file is the detailed evidence ledger; `AGENTS.md` and `README.md` should stay short. | Update the owner doc, then leave only pointers in router docs. |

## Current Countdown

Tracked remaining microtasks from the `brc-tools` handoff and WRF run side: 11.
The 2026-06-16 `brc-tools` hygiene pass closed #4, #5, #6, #11, #12, and
#31 upstream. This `brc-wrf` caretaker pass closes #32 by keeping current
staging-doc and scratch-layout references wired here.

| Bucket | Count | Tasks | Meaning |
| --- | ---: | --- | --- |
| Codex can do, then human reviews | 3 | #7, #10, #13 | Remaining `brc-tools` staging design/test work. Real staging or large transfer proof stays approval-gated. |
| Parked optional legacy work | 1 | #16 | GEFS+NAM two-stream design only if John explicitly revives that experiment. |
| Human-only or human-led | 5 | #17, #21, #23, #24, #33 | WPS inspection, domain/geog judgment, DTN submission, helpdesk/proxy answer, retention/promotion decision. |
| brc-wrf run-tuning, approval-gated | 2 | #26, #27 | Codex can draft scripts/tables, but actual WRF benchmark runs need approval. |

Practical-test countdown:

| Step | Gate | Can a Codex session advance it now? | Stop point |
| --- | --- | --- | --- |
| 1 | Keep NAM-only baseline truth clean in docs and validators. | Yes. | No WPS/WRF claims beyond current evidence. |
| 2 | Keep the merged `brc-tools` hygiene reflected in run-side docs. | Yes, docs/checks only. | No WRF-side change needed for additive manifest schema v2. |
| 3 | Prove a fresh NAM-only `contract_<case>.json` validates in `brc-wrf`. | Done on 2026-06-18. | Gate 5: `verify: 7/7 OK`; strict validation `OK: no findings`. |
| 4 | Keep the successful NAM-only rerun and quicklooks wired into docs. | Done for Gates 6-10 evidence; continue only for maintained templates. | Do not overstate this as GEFS+NAM proof. |
| 5 | Build the maintained practical-test harness. | Done on 2026-06-18. | `wrf_case.py render-practical-harness` renders wrapper/checklist/result tables; no new WRF submission unless approved. |
| 6 | Park GEFS+NAM two-stream unless explicitly revived. | No current action; RAP/source hot-swap work goes through `brc-tools` first. | Do not run WPS yet. |
| 7 | Run practical WRF setting tests: scaling and memory on `notch392`. | First 28-task row passed; Codex can render scripts and result tables. | No additional benchmark `sbatch` without explicit approval. |

Practical-test status: the first approved `scaling_t028` chain exposed two
setup bugs and then passed after fixes. Live diagnosis on 2026-06-18 showed the
original scenario `real.exe` and `wrf.exe` symlinked through scratch to Michael
Davies' `lawson-group6/u6060939/wrf_build/WRF/main/` binaries instead of
John's `~/gits/brc-wrf/main/` binaries. Follow-up job `13550021` proved John's
WRF `V4.8.0` binaries were used and then failed because the clean scenario run
directory lacked `CAMtr_volume_mixing_ratio`; default `ghg_input=1` with RRTMG
needs that file from John's `run/` directory. Prep job `13550104` and
`scaling_t028` job `13550110` passed after the wrapper sourced executables and
runtime physics files from John's `paths.wrf_build/{main,run}`. Evidence:
`/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/jan2013_basin_gefs/practical_tests/scaling_t028/run_20260618T230858Z/debug/`.
The next attempted row, `scaling_t016` job `13550555`, failed before WRF
runtime evidence because the fresh Gate 11 packet was submitted from node-local
`/tmp`; Slurm recorded `/tmp/..._gate11_packet` as `WorkDir`, stdout, and
stderr. Accounting: `FAILED`, exit `2:0`, elapsed `00:00:04` on `notch392`.
No `rsl.*`, archive, or debug evidence was produced. Treat this as a
submission/log-path issue, not a WRF benchmark result. Rerendered retry job
`13550909` fixed the shared Slurm log path and failed in `00:00:04` before
`real.exe`; stdout at
`/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/wrf_jan2013_nam_t016_13550909.out`
reported missing `CAMtr_volume_mixing_ratio`, and compact metadata showed all
required runtime physics/table files from John's `run/` directory were absent
from the `scaling_t016` `WRF_RUN`. It produced no `rsl.*`, archive, or debug
evidence and is not a benchmark result.

## Older General No-Run Queue

The `brc-tools` hygiene batch is merged upstream, Roadmap Gates 3-11 are
complete for the NAM-only baseline and maintained harness, and `scaling_t028`
has one successful 28-task row. This queue is still valid when John explicitly
switches back to practical/scaling or general WRF-roadmap work, but it is not
the current default Pelican alternate-forcing goal. Keep that older work on
science review:
have John/Michael accept or reject
`brc-docs/BRC-WRF-GATE10-QUICKLOOK-REVIEW.md`, approve exactly one additional
benchmark row, or do domain/geog review. Keep GEFS+NAM design work out of the
queue unless that legacy path is explicitly revived. If another benchmark is
approved, the recommended next row is `scaling_t016` because `scaling_t028` has
already passed. Prepare that row-specific `WRF_RUN` first with John's
`main/{real.exe,wrf.exe}` and runtime files from John's `run/` directory, then
rerender the Gate 11 packet so generated practical scripts capture all missing
preflight inputs and set shared Slurm `--chdir` plus stdout/stderr under
`lawson-group6/.../wrf_build_logs/brc-wrf`. Do not reuse the raw-submit
patterns from jobs `13550555` or `13550909`.

The current John/Michael no-run handout is
`brc-docs/BRC-WRF-MICHAEL-PRACTICAL-PACKET.md`. It packages the first contract
validation checklist, settings map, approval gates, and blank result tables for
pair-programming without WPS/WRF execution.

The current AI end-to-end handoff is
`doc/BRC_WRF_END_TO_END_AI_HANDOFF.md`. Use it when the next session is about
build architecture, WRF/WPS ownership, or progressing toward a real submitted
run rather than general planning cleanup.

### Lane 1: Bang Out Here In `brc-wrf`

| Order | Task | Why first | Evidence to leave |
| ---: | --- | --- | --- |
| 1 | Render a no-run report for the current case. | One command now captures SHA, dirty state, metadata validation, Gate 11 packet paths, and shell syntax. | `/tmp` report from `wrf_case.py render-no-run-report`; no artifact reads or compute. |
| 2 | #26/#27 benchmark table rows. | Prepares scaling/memory work without consuming allocation time. | Empty or evidence-filled result table with tasks, memory, wall time, status, archive, and recommendation columns. |
| 3 | Parked #16 GEFS+NAM two-stream design checklist. | Only useful if John explicitly revives that older experiment. | Expected GEFS/NAM field split, `Vtable.GEFS` implications, and `real.exe` stop point. |
| 4 | #21 domain/geog evidence pointer. | Separates syntax checks from human domain judgment. | Exact doc/namelist paths to inspect; no claim of fresh scientific approval. |

### Gate 11 Harness Entry Point

Render the practical-test packet from the case manifest:

```bash
python brc-cases/wrf_case.py render-practical-harness \
  brc-cases/jan2013_basin_nam.case.yaml \
  --output-dir /tmp/brc_gate11_jan2013_basin_gefs
```

The generated packet contains the baseline wrapper, scaling wrappers for
16/28/56 tasks, optional memory-candidate wrappers, `PREPARE_CHECKLIST.md`,
`APPROVAL_PACKET.md`, login-safe metadata checks, off-login artifact checks,
blank result tables, and the closeout record. It refuses repo-local output and
does not submit anything.

### Lane 2: Older `brc-tools` Backlog

These are not the current RAP source-support patch. Keep them parked unless
John switches back to the older GEFS/reforecast backlog.

| Order | Task | Why next | Evidence to leave |
| ---: | --- | --- | --- |
| 1 | #7 Multi-member staging proof. | Pressure-tests per-member layout before ensemble WRF use. | Mocked or small proof evidence; real transfer only after approval. |
| 2 | #10 Operational GEFS post-2017 path. | Needed for recent cases, not the Jan-2013 reforecast proof. | Reused staging abstractions and tests. |
| 3 | #13 Pin `wps_variable_levels` per data-year if token evidence supports it. | Prevents silent reforecast-token drift across 2000-2019. | Evidence-backed token map or explicit decision not to split. |

Recently closed upstream in `brc-tools`: #4 token preflight, #5
`obs_sanity_overlay` test, #6 cached `.idx` lead-time labeling/schema v2, #11
manifest byte/time provenance, #12 240 h boundary behavior, and #31 wishlist
pointer. Closed here: #32 cross-repo doc sync.

### Lane 3: Human Gates

| Decision | Needed before | Default stop point |
| --- | --- | --- |
| Whether to revive GEFS+NAM two-stream. | Any WPS two-stream proof work. | Keep one-source hot-swap work on RAP/other source contracts. |
| Whether to refresh the NAM-only staged contract. | Retiring `brc-cases/jan2013_basin_nam.contract.json`. | Validate reconstructed contract only. |
| Whether to spend allocation on scaling/memory sweeps. | Any `sbatch`, `real.exe`, or `wrf.exe` benchmark. | Render/check templates only. |
| Whether to promote staged inputs. | Copying scratch inputs to durable group storage. | Inventory paths and run manifest verification only. |

## WRF-Side No-Run Templates

### Fresh NAM-Only Contract Validation

Use this only after fresh `brc-tools` staging has produced a real sidecar:

```bash
# Off-login only: this hashes staged files and reads scratch artifacts.
cd ../brc-tools
conda run -n brc-tools-2026 python -m brc_tools.nwp.wrf_staging --verify-manifest \
  /scratch/general/vast/$USER/wrf_inputs/<case>/manifest_<case>.json
cd ../brc-wrf

# Then point a review copy of the case yaml at:
# /scratch/general/vast/$USER/wrf_inputs/<case>/contract_<case>.json
# Off-login only when --strict-files reads staged/archive paths.
python brc-cases/wrf_case.py validate <case>.yaml --strict-files
```

Acceptance: strict validation passes against the fresh `contract_<case>.json`.
Only then consider retiring `brc-cases/jan2013_basin_nam.contract.json`.

### Parked GEFS+NAM Two-Stream Notes

This is legacy optional design context. Do not use it as the default path for
Pelican alternate forcing.

Prepare the design before any approved WPS execution:

| Item | Expected handling |
| --- | --- |
| GEFS pressure fields | Include both `_pres` and `_pres_abv700mb` tokens for `hgt`, `tmp`, `ugrd`, `vgrd`, and `spfh`; humidity is specific humidity, not RH. |
| GEFS near-surface fields | Map `pres_msl`, `pres_sfc`, `hgt_sfc`, `tmp_2m`, `spfh_2m`, `tmp_sfc`, `ugrd_hgt`, and `vgrd_hgt`. |
| NAM filler fields | Keep NAM responsible for `LANDSEA`, `SKINTEMP`/SST, `SNOWH`, and standard 4-layer soil unless a reviewed Vtable proves otherwise. |
| WPS stream settings | Use separate ungrib streams and `metgrid fg_name = 'GEFS','NAM'`; two-stream interval is expected to be `10800`. |
| Stop point | After metgrid, show `met_em` field list, `num_metgrid_levels`, and warnings. Do not run `real.exe` without a new approval. |

### Scaling And Memory Result Tables

Use these tables after a human approves benchmark submissions.

| Tasks | Memory request | Wall time | Sim hours | Wall time per sim hour | WRF marker | Archive path | Notes |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- |
| 16 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 28 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 56 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

| Run | Memory request | Peak memory evidence | WRF marker | Archive path | Recommendation |
| --- | ---: | --- | --- | --- | --- |
| Baseline | `900G` | TBD | TBD | TBD | TBD |
| Right-size candidate | TBD | TBD | TBD | TBD | TBD |

### Wrapper Robustness Checklist

Keep these checks attached to any future maintained run wrapper:

- Print a settings readback before model execution: case window, forcing stream,
  WPS cadence, Vtable/prefix/`fg_name`, expected `met_em`/levels, Slurm shape,
  launcher, scratch run path, and durable archive path.
- Generate compact debug files in addition to WRF's native `rsl.*` logs:
  `debug/run_debug_summary.txt`, `debug/run_phase_times.tsv`, and
  `debug/run_file_inventory.tsv`.
- Treat WRF success, `real.exe` success, archive completeness, and Slurm state as
  separate facts. Required markers are `SUCCESS COMPLETE REAL_EM INIT` and
  `SUCCESS COMPLETE WRF`.
- Archive WRF colon filenames as local paths, for example
  `rsync -av ./wrfout_d0* ...`, so `rsync` does not parse the timestamp colon as
  a remote host separator.
- Do not use `srun --jobid` probes inside a fully occupied WRF allocation; use
  `squeue`, exact logs, success markers, and on-disk artifacts instead.
- Keep downloads and staging in `brc-tools`: use Herbie-backed paths where that
  repo supports them, respect its direct NCEI path for historical NAM analysis,
  force `conda run -n brc-tools-2026 ...` for its Python commands, and run full
  NWP transfers on `notchpeak-dtn`.

## Pelican Slope/Shading Review And MYJ/Eta Gate (2026-07-09)

Treatment-1 execution evidence:

- accepted control: NAM one-way terrain3s WRF job `13852034` at
  `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s/full6h/run_20260708T021809Z/`;
- slope/shading: preparation `13876527`, WRF `13876534`, and quicklooks
  `13877355`, all completed `0:0`;
- slope archive:
  `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s_slope/full6h/run_20260710T003606Z/`;
- mechanical proof: 21 hourly `wrfout`, `SUCCESS COMPLETE WRF`, zero-byte
  `debug/wrf_error_marker_scan.txt`, 54 nonempty quicklooks, and manifest
  verification `2/2 OK`; the six retained `met_em` files caused only the
  documented nonfatal stale-input warning.

Paired science review job `13877599` completed `0:0` in `00:00:38` on
`notch392`. Its durable review directory is:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s_slope/control/run_20260710T003606Z/review_control_vs_slope_13877599/
```

The directory contains `field_stats.tsv` (189 matched rows),
`continuity_stats.tsv`, `threshold_counts.tsv`, surface-cell and shortwave
component audits, eight d03 surface triptychs, two vertical-theta sections, a
d03 time-series panel, and Horsepool 16/18Z profiles. All reviewed arrays were
finite.

Review findings:

- D03 `SWDOWN` changes are small in the domain mean and terrain-aligned in the
  tails. At 16/17/18Z, 7/4/34 of 22,500 cells exceeded `|20 W m-2|`; the
  strongest components were only 1-5 cells. The darkest absolute cells appear
  in both control and treatment and are not missing/nonfinite values.
- D03 `GLW`, `HFX`, and `LH` respond coherently along the same terrain/shadow
  features; there is no domain-wide energy collapse.
- D03 T2 mean absolute differences are `0.065`, `0.031`, and `0.033 K` at
  16/17/18Z. The roughly `-6 K` extreme tail is confined to the one-cell north
  lateral boundary by 17-18Z; d02's `-8.86 K` minimum is also one cell from a
  boundary. These stay as explicit caveats, not basin-interior science values.
- D03 PBLH mean absolute differences remain `1.36-1.77 m`; d03 10 m wind
  remains `0.017-0.023 m s-1`, with no wind change reaching `1 m s-1`.
- Across all 75 d03 levels, theta mean absolute differences remain
  `0.0021-0.0048 K`; central sections are about `+/-0.04 K`, Horsepool
  profiles differ by less than about `0.02 K`, and no d03 value exceeds `1 K`.
- Adjacent-cell p99 jumps remain comparable between the two runs. The extreme
  boundary tails do not spread into the basin-interior thermal column, and no
  missing/nonfinite field or pathological domain collapse was found.

The user subsequently approved slope+MYJ/Eta. Incremental namelist evidence
proved only `bl_pbl_physics = 1 -> 2` and `sf_sfclay_physics = 1 -> 2` changed
from the slope treatment; Noah remained `sf_surface_physics = 2`.
Preparation job `13879078` completed `0:0` in `00:00:15` with six `met_em`
files and namelist SHA-256
`401ac40d057b3314ea407e67fbd421780128a0ef72781125f734f120056a5f32`.
WRF job `13879100` completed `0:0` in `01:41:53` on `notch392`; `real.exe`
took 28 seconds, `wrf.exe` took 6047 seconds, all executable/runtime provenance
checks passed, 21 hourly files were archived, and the error-marker scan was
empty. Quicklook job `13879973` completed `0:0` in `00:01:15` with 54 PNGs:
30 standard, 12 supplemental, and 12 surface-energy maps. Durable archive:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s_slope_myj/full6h/run_20260710T003606Z/
```

Publication generator `13879669` completed `0:0` in `00:11:53` with 604 tasks
and no per-figure errors. Final convergence job `13880154` completed `0:0` in
`00:00:19`. The seven per-case roots contain 63 PNGs each (441 total), and the
cross-case compare root contains 184 PNGs, including 21 `MYJ-Eta-slope`
differences. Focused paired diagnostic job `13880122` completed `0:0` in
`00:00:40` with 189 field/time/domain rows, zero nonfinite values, 12 figures,
and structured continuity/threshold/extreme-cell audits:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s_slope_myj/control/run_20260710T003606Z/review_slope_vs_myj_13880122/
```

At d03 16/17/18Z, MYJ-minus-slope mean T2 was `+0.040/+0.157/+0.307 K`,
mean PBLH was `-33.3/-69.6/-74.8 m`, and mean 10 m wind-speed differences
were `-0.086/+0.095/+0.065 m s-1`. Three-dimensional theta mean differences
were about `-0.04` to `-0.05 K`, with mean absolute differences
`0.083-0.091 K`; sections and Horsepool profiles place most response below
about 700 m AGL. No d03 T2 cell exceeded `5 K`, but the MYJ PBLH field is
substantially patchier and needs explicit human interpretation.

The standard terrain3s two-way feedback companion is also complete. Preparation
job `13880432` completed `0:0` in `00:00:12`; the normalized namelist diff
changed only `feedback = 0 -> 1`, retaining `smooth_option = 0`, standard
YSU/revised-MM5 physics, and no slope/shading. WRF job `13880435` completed
`0:0` in `01:44:43`; `real.exe` took 28 seconds, `wrf.exe` took 6214 seconds,
all executable/runtime provenance checks passed, 21 hourly files were
archived, and the error-marker scan was empty. Quicklook job `13881153`
completed `0:0` in `00:01:30` with 54 PNGs and manifest verification `2/2 OK`.
Durable archive:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_twoway_terrain3s/full6h/run_20260710T084413Z/
```

Paired diagnostic job `13881198` completed `0:0` in `00:00:50` with 189
field/time/domain rows, zero nonfinite values, 12 figures, continuity metrics,
threshold counts, and extreme-cell boundary distances:

```text
/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_twoway_terrain3s/control/run_20260710T084413Z/review_oneway_vs_twoway_13881198/
```

At d03 16/17/18Z, two-way-minus-one-way mean T2 was
`+0.037/-0.003/-0.023 K` with mean absolute differences
`0.108/0.096/0.086 K`; mean PBLH was `+1.36/+0.47/+0.91 m` with mean
absolute differences `5.80/6.74/6.20 m`; mean 10 m wind speed was
`-0.016/-0.015/+0.007 m s-1` with mean absolute differences
`0.132/0.134/0.127 m s-1`. Local response is non-null and often interior:
late d03 extrema reached about `+/-1.9 K` T2, `+/-166 m` PBLH, and
`+/-2.4 m s-1` wind. Adjacent-cell p99 roughness remained comparable between
members for T2, PBLH, wind, and three-dimensional theta, providing no evidence
of broad grid-noise amplification. Cells with `|SWDOWN|` differences at least
`20 W m-2` increased from 462 to 960 to 1658 of 22,500 at 16/17/18Z, mostly
more than ten cells from the d03 outer boundary.

Current stop: manuscript review of the completed default-terrain factorial and
human science review of the physics suite and terrain3s feedback pair. Separate
parent/nest-edge effects from d03 basin-interior response; the current edge
audit measures distance from each domain's outer boundary, not the parent
feedback-footprint interface. No additional WRF treatment is authorized.

## Parked For Human Review Or Approval

Do not lose sight of these. They are not good login-node free-running tasks.

| Task | Owner | Why parked | What Codex can prepare | Human decision or action |
| --- | --- | --- | --- | --- |
| Reconstructed-contract retirement decision | `brc-tools` + `brc-wrf` | Fresh scratch `contract_<case>.json` now passed, but tracked fallback retirement is a separate compatibility decision. | Point to Gate 5 evidence and draft the patch if retirement is approved. | Decide whether/when `brc-cases/jan2013_basin_nam.contract.json` remains as a fallback. |
| #16 GEFS+NAM two-stream proof | `brc-wrf` with brc-tools context | Parked optional path; WPS work and eventual `real.exe` are approval-gated. | Draft `Vtable.GEFS` mapping only if John revives this experiment. | Decide whether two-stream is needed. |
| #17 Ungrib staged reforecast and inspect fields | Human-led WPS proof | Runs WPS tooling and inspects meteorological field coverage. | Build checklist and expected field list. | Approve WPS/ungrib execution; review missing fields. |
| #21 Confirm geogrid, `geog_data_path`, and Basin domain | Human-led review | This is scientific/domain judgment, not just syntax. | Collect exact namelist paths and current expected values. | Confirm the domain/geog setup is the intended baseline. |
| #23 Full DTN stage | Human-led CHPC transfer | Multi-GB stage belongs on `notchpeak-dtn`, not login nodes. | Check script path and render plan; verify command shape. | Approve `sbatch scripts/stage_inputs.dtn.slurm` or equivalent. |
| #24 Compute-node internet/proxy answer | Human-led CHPC policy | Requires helpdesk or CHPC policy confirmation. | Draft the question and place to record answer in `brc-knowledge`. | Ask helpdesk and accept the canonical answer. |
| #26/#27 Scaling and memory benchmarks | `brc-wrf` run tuning | Real WRF runs consume allocation time. | Render scripts, result table template, archive checklist. | Approve run submissions and choose task/memory sweep. |
| #33 Retention/promotion | Human-led storage policy | Scratch purges; durable promotion consumes group storage. | Inventory current paths and manifest verification command. | Decide whether to promote staged inputs to `lawson-group6`. |

## Remaining Microtask Table

| Task | Label | Repo | Current classification | Next Codex action | Human review or stop point |
| --- | --- | --- | --- | --- | --- |
| #7 | Multi-member staging proof | `brc-tools` | Codex can partially do | Design per-member layout and mocked manifest aggregation. | Any real multi-member stage needs transfer approval. |
| #10 | Operational GEFS post-2017 path | `brc-tools` | Codex can do after design | Reuse staging abstractions and tests. | Review source naming and scope before live use. |
| #13 | Pin `wps_variable_levels` per data-year if needed | `brc-tools` | Codex can do after evidence review | Add structure only if token evidence supports it. | Human/science review if year differences affect WPS. |
| #16 | GEFS+NAM Vtable and two-stream WPS proof | `brc-wrf` | Parked optional | Draft Vtable/field-source design only if explicitly revived; no execution. | Approval before WPS and before `real.exe`. |
| #17 | Ungrib staged reforecast and inspect fields | `brc-wrf` | Human-led | Prepare expected field checklist. | WPS execution and field review. |
| #21 | Confirm geogrid/path/domain | `brc-wrf` | Human-led | Point to exact namelist and runbook evidence. | Human confirms domain/geog baseline. |
| #23 | Full DTN stage | `brc-tools` | Human-led | Verify script and plan command only. | Approve DTN `sbatch`. |
| #24 | Compute-node internet/proxy answer | `brc-knowledge` | Human-led | Draft helpdesk question and doc destination. | Human obtains/records answer. |
| #26 | Scaling benchmark | `brc-wrf` | Approval-gated run tuning | Prepare scripts and result table. | Approve WRF submissions. |
| #27 | Memory benchmark | `brc-wrf` | Approval-gated run tuning | Prepare memory sweep and accounting table. | Approve WRF submissions. |
| #33 | Retention/promotion | `brc-tools` + `brc-wrf` + storage | Human-led | Inventory scratch and durable target commands. | Human decides what to promote. |

## Recently Closed Microtasks

| Task | Close evidence |
| --- | --- |
| #4 | `brc-tools` merged offline-tested token preflight; live S3 list-URL format remains a first-live-run caveat. |
| #5 | `brc-tools` added the synthetic `obs_sanity_overlay` test. |
| #6 | `brc-tools` manifest schema v2 labels cached lead-time limitations/additions; additive for `brc-wrf`. |
| #11 | `brc-tools` records manifest byte/time provenance. |
| #12 | `brc-tools` pins the 240 h boundary behavior as warn+partial. |
| #31 | `brc-tools` added the `WISHLIST-TASKS.md` pointer. |
| #32 | `brc-wrf` docs point to current `../brc-tools/docs/WRF-INPUT-STAGING.md`, scratch layout, and handoff files; link-check passes with binary files ignored. |
| Gate 11 | `brc-cases/wrf_case.py render-practical-harness` renders the maintained practical-test packet and benchmark Slurm review scripts outside the repo. |
| Pelican quicklooks | `brc-cases/wrf_quicklook.py` now renders a standardized 10-product per-domain set using `brc-tools` plotting helpers; 333 m output has d01/d02/d03 and the earlier 3/1 km output has d01/d02. Latest like-for-like NAM/GFS render: job `13755401`, 30 PNGs per forcing under each archive's historical `quicklooks/standardized_compare_20260630T214000Z/`; future default is `<archive-run>/quicklooks/dXX/`. |

## Documentation Refresh Map

Update docs where the evidence belongs, not all in one place.

| Evidence changes | Primary doc | Secondary pointer |
| --- | --- | --- |
| Active experiment todo or routing changes | `doc/BRC_WRF_EXPERIMENT_TODO.md` | `AGENTS.md` only as a short router |
| Historical microtask counts or evidence details | `doc/BRC_WRF_MICROTASK_HANDOFF.md` | `doc/BRC_WRF_EXPERIMENT_TODO.md` only if the current next task changes |
| NAM-only run proof facts | `brc-docs/BRC-WRF-FIRST-CASE.md` | `brc-docs/BRC-WRF-STATE-PLAYBOOK.md` |
| Case manifest or render-only Slurm review | `brc-cases/README.md` | `doc/BRC_WRF_EXPERIMENT_TODO.md` |
| WRF quicklook product list or adapter behavior | `brc-cases/README.md` and `brc-cases/wrf_quicklook.py` | `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| Reusable plotting primitives | `../brc-tools/brc_tools/visualize/` | `brc-wrf` should only point to the helper |
| brc-tools staging behavior, manifests, contracts | `../brc-tools/docs/WRF-INPUT-STAGING.md` | `brc-docs/BRC-WRF-FIRST-CASE.md` |
| GEFS+NAM field split and Vtable design | `../brc-tools/docs/WRF-GEFS-NAM-FIELD-MAP.md` until WPS proof exists | Parked optional; point here only if John revives that experiment |
| CHPC node, storage, proxy, Slurm truth | `../brc-knowledge/scholarium/reference-base/resources/` | BRC-WRF docs should point, not duplicate |
| Benchmark results | `brc-docs/BRC-WRF-STATE-PLAYBOOK.md` | `brc-docs/BRC-WRF-FIRST-CASE.md` if runbook changes |

## Standing Preferences For The Next Session

- Treat this as a large upstream-style WRF tree with a thin BRC-local layer.
- Prefer docs, validators, and focused tests before any run-scale workflow.
- Keep `brc-tools`, `brc-wrf`, and `brc-knowledge` ownership separate.
- Leave breadcrumbs: command, evidence, owner repo, and stop point.
- If a task starts needing WPS, WRF, Slurm, large downloads, or CHPC policy,
  stop and park it in the human/approval table instead of improvising.
- Keep `AGENTS.md` as a router. Put detailed state here or in the workflow doc
  that owns the evidence.
