# BRC WRF Experiment To-Do

This is the short active task router for running and reviewing WRF
experiments across `brc-wrf` and sibling `brc-tools`.

Use this before the longer evidence files. It should stay small enough for an
AI cold start.

## Current Aim

**6 October 2026: drainage canyons in gigawatts.** JRL approved a 24-tracer
WRF rebuild from the October `ub-wx` handoff. Canonical source is `john/wrf`;
the source change, build contract, branch audit and outstanding science issues
are in `BRC_WRF_RESEARCH_BUILDS.md`. Compile in a fresh pinned directory,
preserving the June executables. Stop at verified compile proof: model
pre-flight tests and the 48-hour run are not authorized by this rebuild.

## Completed Pelican Work Awaiting Review

Use the completed Pelican 3/1/0.333 km, 75-level runs as a poor-man's ensemble:

- NAM two-way baseline: complete.
- GFS analysis hot-swap: complete.
- GFS one-way feedback sensitivity: complete through WRF and post-processing.
- NAM one-way feedback sensitivity: complete.
- NAM terrain3s two-way feedback sensitivity: complete.
- Standard and supplemental quicklooks: complete.

The default-terrain GFS feedback companion is complete. Preparation `13894268`
copied six verified GFS `met_em` files; WRF job `13894282` changed only
`feedback = 1 -> 0`, completed with `real.exe` in 32 s and `wrf.exe` in 5865 s,
and archived 21 hourly files with an empty error-marker scan. Quicklooks
`13896648` completed with 54 PNGs. Manuscript analysis `13896641`, publication
figure jobs `13896642` and `13896828`, and exact-config convergence `13896871`
completed `0:0`; X10 has 63 publication PNGs and the refreshed study compare
root has 247. This fills the missing WRF leg of the default-terrain GFS/NAM by
one-/two-way feedback factorial without a new WPS run.
The durable control packet includes `execution_manifest.tsv` with SHA-256
`bf5b10053c7f84e001165ef214e0ad73fb36ca38cd5b29cd407b120db401d724`.

The custom `3s` `HGT_M` lane is complete. WPS job `13851884`, WRF job
`13852034`, and quicklook job `13852773` produced the accepted NAM one-way
terrain3s control with 21 hourly `wrfout` files and 42 standard/supplemental
PNGs. Its clean feedback-on companion is complete: preparation `13880432`,
WRF `13880435`, and quicklooks `13881153` completed `0:0`. The normalized
namelist diff changed only `feedback = 0 -> 1`, retained `smooth_option = 0`
and the standard YSU/revised-MM5 physics, and produced 21 hourly files, an
empty archived error-marker scan, and 54 PNGs. Paired diagnostic job
`13881198` completed `0:0` with 189 finite field/time/domain rows and 12
figures. From 16-18Z, d03 mean T2 changed by only
`+0.037/-0.003/-0.023 K`, mean PBLH by `+1.36/+0.47/+0.91 m`, and mean 10 m
wind speed by `-0.016/-0.015/+0.007 m s-1`; localized interior response is
non-null, while adjacent-cell p99 roughness remains comparable. Human review
and a parent-nest-footprint mask remain before a manuscript verdict. The no-FDDA,
six-hour slope-radiation/terrain-shading treatment is now
complete: preparation job `13876527`, WRF job `13876534`, and quicklook job
`13877355` completed `0:0`. The archive has 21 hourly `wrfout` files, an empty
WRF error-marker scan, and 54 PNGs: 30 standard, 12 supplemental, and 12
surface-energy maps. Paired control-versus-slope review job `13877599`
completed `0:0` and
wrote 189 field/time/domain rows plus comparison figures with no nonfinite
values. The science recommendation was **GO** for the slope+MYJ/Eta treatment:
the slope response is terrain-local, basin-interior means remain small, and
vertical-theta structure remains stable. Retain the documented lateral-boundary
outliers as an analysis caveat. The approved slope+MYJ/Eta increment is now
complete: preparation `13879078`, WRF `13879100`, and quicklooks `13879973`
completed `0:0`. The incremental diff changed only `bl_pbl_physics` and
`sf_sfclay_physics` from 1 to 2 on all domains, retained Noah, and produced a
21-file archive, empty WRF error-marker scan, and 54 base quicklooks. The
paired publication suite and focused diagnostic review are now complete in
jobs `13879669` and `13880122`; final convergence job `13880154` proved all
seven-case products current. Current stop is human science review of the
physics suite plus the new feedback pair; no additional WRF treatment is
authorized.

## Next Tasks

| Order | Repo | Task | Stop point |
| ---: | --- | --- | --- |
| 1 | `brc-wrf` | Slope/shading treatment execution and base quicklooks. | Done: jobs `13876527`, `13876534`, and `13877355`; 21 outputs and 54 quicklooks accepted mechanically. |
| 2 | human + figure workflow | Review the slope treatment and create any additional figures before deciding on MYJ. | Done: review job `13877599`; **GO** with lateral-boundary outliers retained as a caveat. |
| 3 | `brc-wrf` | Prepare and run the approved slope+MYJ/Eta treatment. | Done: preparation `13879078`, WRF `13879100`, and quicklooks `13879973`; two-key diff, Noah retention, 21 outputs, empty error scan, and 54 PNGs accepted mechanically. |
| 4 | `brc-tools` + `wrf-nudge-ozone-air2026` | Create and review the paired slope-versus-MYJ figure suite, then decide whether a longer surface/snow reconstruction is justified. | Figures done: generator `13879669`, diagnostics `13880122`, convergence `13880154`; human interpretation remains. Treat six-hour output as controlled response evidence, not persistent-cold-pool skill. |
| 5 | human + figure workflow | Review one-way `13852034` versus two-way `13880435`, keeping parent/nest-edge masks separate from d03 basin-interior metrics. | Diagnostics `13881198` are done; inspect the 12 figures and add the parent-nest-footprint mask before a manuscript verdict or any further run. |
| 6 | `brc-tools` | If another forcing source is chosen, do source feasibility first: source access, fields, cadence, Vtable implications, manifest/contract plan. | No WPS/WRF; hand back a staged or clearly blocked contract path. |
| 7 | `brc-wrf` | Consume only a verified `brc-tools` contract: case YAML, WPS/Vtable review, WPS-only field proof if field adequacy is uncertain. | Stop before `real.exe` unless explicitly approved after field review. |
| 8 | `brc-wrf` | Run the WRF conveyor only after approval: WPS, `real.exe`, `wrf.exe`, archive, quicklooks. | Leave job IDs, logs, archive path, quicklook path, and failure/success markers. |

## Current Evidence Pointers

| Need | File |
| --- | --- |
| Geogrid-only terrain/domain preview | `brc-docs/BRC-WRF-DOMAIN-PREVIEW-SOP.md` |
| Custom WPS `HGT_M` static tile preparation | `brc-cases/wps_hgt_static.py` and `brc-cases/README.md` |
| Pelican source verdicts, terrain state, and quicklook roots | `brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md` |
| Conveyor rules, archive layout, quicklook layout | `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| First Jan-2013 proof and gate evidence | `brc-docs/BRC-WRF-FIRST-CASE.md` |
| Detailed historical evidence ledger | `doc/BRC_WRF_MICROTASK_HANDOFF.md` |
| Build/WPS/WRF end-to-end route | `doc/BRC_WRF_END_TO_END_AI_HANDOFF.md` |
| Case helpers and quicklook adapter | `brc-cases/README.md` |
| Derived-run packet renderer | `brc-cases/wrf_treatment.py`, the two `terrain3s_slope*.case.yaml` manifests, `pelican2013_nam_3_1_333m_75lev_twoway_terrain3s.case.yaml`, and `pelican2013_gfs_3_1_333m_75lev_oneway.case.yaml` |
| WRF staging state in `brc-tools` | `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md` |
| WRF staging implementation details in `brc-tools` | `../brc-tools/docs/WRF-INPUT-STAGING.md` |
| Broader `brc-tools` backlog | `../brc-tools/WISHLIST-TASKS.md` |

## Source Choices

| Source path | Current status | Owner |
| --- | --- | --- |
| NAM baseline | Complete; comparison anchor. | `brc-wrf` review only |
| GFS analysis | Two-way and matched one-way runs complete through post-processing. | Manuscript and coauthor review |
| NAM one-way feedback | Complete; feedback sensitivity, not a new forcing source. | `brc-wrf` review only |
| RAP-only | Blocked before `real.exe`: hybrid RAP lacks usable 3D atmosphere; pressure RAP lacks layered soil temperature/moisture. | `brc-tools` source fix or explicit filler design |
| ERA5 | Locally blocked: no `brc-tools` source support, CDS tooling, or CDS credentials. | `brc-tools` access/tooling first |
| FNL | Optional independent third source; not current default. | `brc-tools` feasibility first |
| GEFSv12+NAM two-stream | Parked legacy path. | revive only by explicit human decision |

## Approval Boundaries

Login-safe:

- read/edit docs;
- run `git status`;
- run path-only quicklook tests;
- run `python -m py_compile` on `brc-cases` helpers;
- render terrain Slurm packets without submitting them.

Off-login or approval-gated:

- terrain DEM metadata/download/cache/build jobs;
- strict manifest/contract checks that hash staged inputs;
- NetCDF/archive reads;
- quicklook rendering;
- DTN staging;
- WPS, `real.exe`, `wrf.exe`;
- Slurm submissions, scaling, memory benchmarks;
- durable promotion from scratch.

## Repo Boundary

- `brc-tools`: downloads, source access, GRIB staging, manifests, contracts,
  token/source checks, input quicklooks.
- `brc-wrf`: WRF source, WPS/WRF consumption, case YAML, validators, run
  wrappers, WRF-output quicklooks, archive evidence.
- `brc-knowledge`: CHPC node, storage, scheduler, proxy, and validated Slurm
  truth.

Patch the repo that owns the behavior. If this file and a sibling `brc-tools`
doc disagree, refresh the owner doc and leave a short pointer here.
