# Repository Context

This is Bingham Research Center's purpose-built `brc-wrf` fork:

- Remote: `https://github.com/Bingham-Research-Center/brc-wrf.git`
- Branch family: `john/*`
- Pinned baseline: WRF `4.8.0`

This tree is large. Start narrow and local. Do not broad-scan WRF internals,
scratch trees, archives, or sibling repos unless a named file or `rg` result
points there.

## Fork Freeze

`brc-wrf` is deliberately independent of upstream WRF and of other branch
lines in this fork. Do not merge, rebase, or routinely synchronize from
`master`, `main`, or an upstream remote. Port a newer WRF change only when it
is specifically needed: use a reviewable `john/port-*` branch, record the
source version/commit and BRC rationale in `doc/BRC_WRF_PORTING_POLICY.md`,
then validate the port before it is adopted.

## Cold Start

Keep this file as the AI router and safety contract, not a backlog.

Default start:

1. `git status --short --branch --untracked-files=no`
2. `sed -n '1,180p' AGENTS.md`
3. `sed -n '1,220p' doc/BRC_WRF_EXPERIMENT_TODO.md`

Then choose one owner document below; do not read the whole set.

## Case And Run Lookup

| Need | Read first | Start from |
| --- | --- | --- |
| New or existing case: validate, render, or inspect the available manifests | `brc-cases/README.md` | `brc-cases/*.case.yaml` and `brc-cases/wrf_case.py` |
| Validated Jan-2013 Uinta Basin NAM proof | `brc-docs/BRC-WRF-FIRST-CASE.md` | `brc-cases/jan2013_basin_nam.case.yaml` |
| Pelican NAM/GFS control, feedback, source comparison, or human review | `brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md` | `doc/BRC_WRF_EXPERIMENT_TODO.md`, then `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| Pelican custom 3s terrain or a geogrid-only terrain proof | `brc-docs/BRC-WRF-DOMAIN-PREVIEW-SOP.md` | `brc-cases/wps_hgt_static.py` and `brc-cases/README.md` |
| Pelican derived physics/nesting treatment from an accepted control | `brc-cases/README.md` | `brc-cases/wrf_treatment.py` and the `*terrain3s*.case.yaml` manifests |
| Pelican RAP WPS-only field adequacy review | `brc-docs/BRC-WRF-PELICAN-RAP-FEASIBILITY.md` | `brc-cases/pelican2013_rap_3_1_333m_75lev.case.yaml` |
| A new forcing source or a staging/contract problem | `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md` | `../brc-tools/docs/WRF-INPUT-STAGING.md`; return here only with a verified contract |
| Build, WPS, or full WRF conveyor route | `doc/BRC_WRF_END_TO_END_AI_HANDOFF.md` | `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| Canonical research builds, provenance, or gigawatts tracer rebuild | `doc/BRC_WRF_RESEARCH_BUILDS.md` | `brc-cases/build_research_wrf.slurm` |

For every run, use the case manifest and rendered control evidence as the
authority for executable paths and run roots; do not copy a path from an old
archive or another case.  An existing completed case is review evidence, not
authorization to rerun it.

Other targeted owner documents:

- Detailed historical evidence: `doc/BRC_WRF_MICROTASK_HANDOFF.md`
- CHPC node, storage, scheduler, proxy, and Slurm truth:
  `../brc-knowledge/scholarium/reference-base/resources/`
- Local automation: `.sane/wrf/README.md`
- CI: `.ci/tests/build.sh` and `.github/workflows/ci.yml`

Do not revive deleted June handoffs, chat-style notes, or stale priority files.
If a fact changes, update the owner doc and leave only short pointers elsewhere.

## Source Of Truth

| Truth | Canonical file |
| --- | --- |
| Fork identity and selective upstream-port policy | `doc/BRC_WRF_PORTING_POLICY.md` |
| Current experiment todo across `brc-wrf` and `brc-tools` | `doc/BRC_WRF_EXPERIMENT_TODO.md` |
| Detailed evidence ledger | `doc/BRC_WRF_MICROTASK_HANDOFF.md` |
| End-to-end WRF/WPS route | `doc/BRC_WRF_END_TO_END_AI_HANDOFF.md` |
| Pelican conveyor, archive, and quicklook rules | `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| Pelican source/terrain verdicts and review prompts | `brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md` |
| First-case proof and run explanation | `brc-docs/BRC-WRF-FIRST-CASE.md` |
| Printable state summary | `brc-docs/BRC-WRF-STATE-PLAYBOOK.md` |
| Case helpers, static terrain helper, and WRF-output quicklook adapter | `brc-cases/README.md` |
| Input staging and downloader behavior | `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md` and `../brc-tools/docs/WRF-INPUT-STAGING.md` |
| CHPC infrastructure facts | `../brc-knowledge/scholarium/reference-base/resources/` |

## Ownership

- `brc-wrf`: WRF source, WPS/WRF-side docs, case manifests, validators, run
  templates, maintained wrappers, and WRF-output quicklook adaptation.
- `brc-tools`: input staging, manifests, contracts, token checks, NWP download
  logic, and reusable visualization helpers such as `brc_tools.visualize.grid`.
- `brc-knowledge`: canonical CHPC infrastructure facts and validated Slurm
  guidance.

Patch the repo that owns the behavior. Do not add downloader/staging logic to
`brc-wrf`. Do not put WRF/WPS execution wrappers in `brc-tools`.

## `brc-tools` Python Environment

For any command that runs sibling `../brc-tools` Python, Herbie, NWP source
planning, input staging, manifest verification, or `pytest`, force the
maintained environment:

```bash
conda run -n brc-tools-2026 python ...
conda run -n brc-tools-2026 pytest ...
```

The stricter equivalent is:

```bash
/uufs/chpc.utah.edu/common/home/u0737349/software/pkg/miniforge3/envs/brc-tools-2026/bin/python ...
```

Bare `python brc-cases/...` remains acceptable for this dependency-light
`brc-wrf` repo unless the task invokes `brc-tools`.

Exception: WRF-output quicklook rendering reads WRF NetCDF and imports plotting
helpers from `../brc-tools`. Source planning still belongs in
`brc-tools-2026`, but if that environment lacks the xarray NetCDF backend, use
a proven NetCDF-capable render environment with `PYTHONPATH` pointed at
`../brc-tools` and record the environment in the control/log evidence.

## Active Experiment Snapshot

- Drainage-canyons-gigawatts: 24-tracer compile approved on 6 October 2026;
  build/provenance owner is `doc/BRC_WRF_RESEARCH_BUILDS.md`. Model tests and
  the 48-hour run remain separate gates. Canonical source line: `john/wrf`.
- The Jan-2013 NAM proof is validated; use it as the small reference case.
- Pelican NAM/GFS controls, feedback comparisons, custom-3s terrain, and the
  approved terrain treatments are complete through quicklooks. The current
  stop is human science review; no new Pelican WRF treatment is authorized.
- RAP remains WPS-field-adequacy-only; ERA5 is locally blocked; FNL and
  GEFSv12+NAM require an explicit revival decision. Exact status, evidence,
  job IDs, paths, and next steps belong in `doc/BRC_WRF_EXPERIMENT_TODO.md`.
- John-owned WPS is
  `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build/WPS`.
  Check the WRF executable path from rendered control evidence on disk.
- Fresh `brc-tools` staging emits `manifest_<case>.json` and
  `contract_<case>.json`; `brc-wrf` consumes those sidecars.

## Login-Safe Versus Off-Login

Login-node-safe examples when kept small:

- `git status --short --branch --untracked-files=no`
- `sed -n '1,180p' <named-doc>`
- `rg -n '<specific-pattern>' <narrow-paths>`
- `python -m py_compile brc-cases/wrf_case.py brc-cases/wrf_quicklook.py`
- `python -m py_compile brc-cases/wps_hgt_static.py`
- `PYTHONPATH=brc-cases python brc-cases/test_wrf_quicklook.py`
- `PYTHONPATH=brc-cases python brc-cases/test_wps_hgt_static.py`
- `python brc-cases/wps_hgt_static.py render-slurm-packet ...`
- `python brc-cases/wrf_case.py validate brc-cases/jan2013_basin_nam.case.yaml`

Run only in approved Slurm batch or interactive compute context:

- `python brc-cases/wps_hgt_static.py query-usgs ...`
- `python brc-cases/wps_hgt_static.py download-manifest ...`
- `python brc-cases/wps_hgt_static.py build-from-inventory ...`
- `conda run -n brc-tools-2026 python -m brc_tools.nwp.wrf_staging --verify-manifest ...`
- strict validators that read staged inputs, manifests, WPS/WRF files, or archives
- `python brc-cases/wrf_quicklook.py check ...`
- `python brc-cases/wrf_quicklook.py render ...`
- WPS, `real.exe`, `wrf.exe`, NetCDF inspection, manifest hashing, archive
  inventories, staging plans, scaling sweeps, memory tests, and large downloads

Never run full builds, WPS, WRF, Slurm submissions, scaling sweeps, or large
downloads without explicit approval.

## Storage And Artifacts

- Staged forcing: `/scratch/general/vast/$USER/wrf_inputs/<case>/`
- Static terrain DEM cache: `/scratch/general/vast/$USER/wrf_inputs/<case>/terrain_dem_cache/`
- Static WPS geography overlays: `/scratch/general/vast/$USER/wps_geog_<purpose>/`
- Active WPS/WRF I/O: `/scratch/general/vast/$USER/wrf_runs/<case>/`
- Durable run artifacts:
  `/uufs/chpc.utah.edu/common/home/lawson-group6/<namespace>/wrf_archive/<case>/run_<UTC>/`
- Durable logs:
  `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/`

Generated runs, staged inputs, run-local namelists, rendered Slurm scripts,
logs, NetCDF, PNGs, and inventories do not belong in this repo.

## Workflow Gotchas

- Build truth must be checked from disk; a fresh checkout has no `real.exe` or
  `wrf.exe` until compiled.
- WPS is separate from this checkout. Production wrappers must use John-owned
  WRF/WPS roots, not Michael-owned comparison paths.
- Gate 11 practical wrappers byte-match scenario executables and runtime tables
  against John's build before `real.exe`.
- WRF filenames contain colons; archive with local-style sources such as
  `rsync -av ./wrfout_d0* ...`.
- Treat `real.exe`, `wrf.exe`, archive completeness, Slurm state, and
  quicklooks as separate evidence.
- Prefer structured artifacts over large logs:
  `debug/run_debug_summary.txt`, `debug/run_phase_times.tsv`,
  `debug/run_file_inventory.tsv`, `sacct`, and targeted `rg` patterns.

## Build And Test Caution

Both build paths exist:

- Legacy: `./configure`, `./compile`, `./clean`
- CMake-oriented: `./configure_new`, `./compile_new`, `./cleanCMake.sh`

Do not assume one path is correct. Read the relevant local doc or script first.

## Change SOP

- Keep changes lean, logical, and scientifically grounded.
- Update the canonical owner doc when workflow truth changes.
- Stage only relevant files; leave unrelated sibling-repo dirt alone.
- Write concise commit subjects and detailed bodies with motivation, evidence,
  validation, and operational impact.
- When AI materially assists a change, include both coauthor trailers:
  `Co-authored-by: John Lawson <john.lawson@usu.edu>` and
  `Co-authored-by: Codex <codex@openai.com>`.
