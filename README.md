# brc-wrf

`brc-wrf` is Bingham Research Center's purpose-built WRF fork, based on WRF
4.8.0 with BRC-local case tooling, CHPC run practices, and AI routing layered
on top. The GitHub repository is
[`Bingham-Research-Center/brc-wrf`](https://github.com/Bingham-Research-Center/brc-wrf).

The extensionless `README` is the upstream WRF notice/release/documentation
file. This `README.md` is the local BRC entry point. Keep it terse and route
details to the owning docs.

## Fork Policy

This is an independent, frozen fork: it does not automatically follow upstream
WRF or changes on `master`, `main`, or other branch lines. WRF 4.8.0 is the
pinned starting point. When a newer upstream change is needed, port only that
specific change through a reviewable BRC branch, record its source and reason,
and validate it here before adoption. See `doc/BRC_WRF_PORTING_POLICY.md`.

`john/wrf` is the canonical research line and GitHub default. Build releases
pin exact source/submodule commits and executable hashes; experiments pin
their case/control configuration separately. See
[`doc/BRC_WRF_RESEARCH_BUILDS.md`](doc/BRC_WRF_RESEARCH_BUILDS.md).

## Fast Start

For a cold start, read:

1. `AGENTS.md` - repo safety, ownership, and task routing.
2. `doc/BRC_WRF_EXPERIMENT_TODO.md` - the current WRF experiment todo list
   spanning `brc-wrf` and sibling `brc-tools`.

Then read only the task-specific owner doc listed there. The long
`doc/BRC_WRF_MICROTASK_HANDOFF.md` is now a detailed evidence ledger, not the
default first stop.

## Current Posture

Validated baseline: NAM-only Jan-2013 Uinta Basin, 12/4 km nested, WPS
`Vtable.NAM`, `interval_seconds = 21600`; Gates 5-11 passed on 2026-06-18.

The drainage-canyons-gigawatts 24-tracer compile release is verified and
tagged; its provenance record is in `doc/BRC_WRF_RESEARCH_BUILDS.md`.
Model pre-flight tests and the 48-hour reference run
remain separate gates. Pelican controls, feedback comparisons and approved
terrain/physics treatments are complete through quicklooks and await human
science review. Exact state and evidence belong in the experiment todo.

RAP-only is blocked before `real.exe`, ERA5 is blocked locally by source
support/tooling/credentials, FNL is optional third-source work, and the older
GEFS+NAM two-stream idea is parked unless explicitly revived.

## Where Work Lives

| Need | File |
| --- | --- |
| Active experiment todo across `brc-wrf` and `brc-tools` | `doc/BRC_WRF_EXPERIMENT_TODO.md` |
| Detailed evidence ledger | `doc/BRC_WRF_MICROTASK_HANDOFF.md` |
| Build/WPS/WRF route | `doc/BRC_WRF_END_TO_END_AI_HANDOFF.md` |
| Canonical research source, build provenance, gigawatts review | `doc/BRC_WRF_RESEARCH_BUILDS.md` |
| Pelican source verdicts and review prompts | `brc-docs/BRC-WRF-PELICAN-NWP-HOTSWAP-HANDOFF.md` |
| Conveyor, archive, and quicklook rules | `brc-docs/BRC-WRF-RUN-CONVEYOR-SOP.md` |
| Case manifests, validators, Slurm renderers, quicklooks | `brc-cases/README.md` |
| Input staging and source support | `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md` and `../brc-tools/docs/WRF-INPUT-STAGING.md` |
| Broader `brc-tools` backlog | `../brc-tools/WISHLIST-TASKS.md` |
| CHPC node, storage, scheduler, proxy, Slurm truth | `../brc-knowledge/scholarium/reference-base/resources/` |

Do not revive deleted June to-do, handoff, or chat-style files. Update the
canonical owner above and leave only short pointers elsewhere.

## Boundaries

- `brc-wrf`: WRF source, WPS/WRF-side docs, case manifests, validators, run
  templates, maintained wrappers, and WRF-output quicklook adaptation.
- `brc-tools`: input staging, manifests, contracts, token checks, NWP download
  logic, and reusable plotting helpers.
- `brc-knowledge`: canonical CHPC infrastructure facts and validated Slurm
  guidance.

Do not add downloader/staging logic to `brc-wrf`. Do not put WRF/WPS execution
wrappers in `brc-tools`. Do not point John's wrappers at Michael-owned WRF/WPS
roots.

## Build And Run

Both WRF build paths exist:

- Legacy: `./configure`, `./compile`, `./clean`
- CMake-oriented: `./configure_new`, `./compile_new`, `./cleanCMake.sh`

Do not assume one path is correct for a task. Full builds, WPS, `real.exe`,
`wrf.exe`, Slurm jobs, large downloads, strict artifact reads, NetCDF-heavy
checks, archive inventories, and quicklook rendering need explicit approval and
the correct off-login context.

## Change Style

Keep edits lean, scoped, and scientifically motivated. Update the canonical doc
that owns the fact, then leave short pointers elsewhere. Stage only relevant
files, leave sibling-repo dirt alone, and preserve command/evidence/stop-point
details in commit bodies when workflow truth changes.

When AI materially assists a change, include:

```text
Co-authored-by: John Lawson <john.lawson@usu.edu>
Co-authored-by: Codex <codex@openai.com>
```

## Upstream WRF Resources

WRF registration, documentation, support, citation, and public notice links are
listed in the upstream `README`.
