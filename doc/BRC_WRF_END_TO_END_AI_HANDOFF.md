# BRC WRF End-To-End AI Handoff

Purpose: give a cold-start AI session the shortest useful path toward John's
repeatable end-to-end WRF workflow on CHPC.

This is a pointer map, not a replacement for the source docs. Read named
sections, verify live disk state, then leave command/evidence/stop-point
breadcrumbs.

## End Goal

Build and run John's BRC WRF fork in a way that is:

- compiled from `~/gits/brc-wrf`, with John's git SHA and local modifications
  preserved as provenance;
- paired with a John-owned WPS root, not another user's WPS or WRF build;
- staged through `../brc-tools` manifests/contracts;
- run on CHPC using architecture-aware choices from `../brc-knowledge`;
- archived under `lawson-group6/.../wrf_archive/...`;
- repeatable by a later human or AI without guessing which module, path, source,
  or artifact was used.

Michael Davies' proven path under `lawson-group6/u6060939/wrf_build/` is a
yardstick. Use it to understand expected artifact classes, success markers,
directory shape, and gotchas. Do not point John's wrappers at Michael-owned WRF
or WPS executables, and do not treat his path as John's install recipe.

## Minimal Read Packet

Read in this order. Do not ingest broad WRF source until one of these docs points
to a specific file or failure mode.

| Need | Read | Why |
| --- | --- | --- |
| CHPC authority first | `../brc-knowledge/scholarium/reference-base/resources/chpc-team-resource-inventory.md` sections 1, 2, 5, 7, Q1, Q4, Q5, Q6, and 8 | Hardware, storage, scheduler, software-module landscape, and WRF architecture constraints. |
| WRF build/run details | `../brc-knowledge/scholarium/reference-base/resources/wrf-on-chpc-quickstart.md` sections 3, 4, 5, 7, 8, 10, 11, and 12 | Validated Intel stack, `--mpi=pmi2`, WRF/WPS build choices, run layout, scaling, and known failure modes. |
| Generic Slurm only if needed | `../brc-knowledge/scholarium/reference-base/resources/chpc-slurm-job-examples.md` sections 5 and 7 | Ensemble shape and long-running LLM/API agent shape. Do not copy generic WRF body from here. |
| Repo router | `AGENTS.md` | Boundaries, login-node-safe commands, and repo ownership. |
| Current experiment todo | `doc/BRC_WRF_EXPERIMENT_TODO.md` | Active WRF experiment tasks across `brc-wrf` and `brc-tools`. |
| Detailed WRF evidence ledger | `doc/BRC_WRF_MICROTASK_HANDOFF.md` | Historical gates, stopped work, and no-run templates. |
| Proven NAM path | `brc-docs/BRC-WRF-FIRST-CASE.md` | Current start-to-finish proof and source identity. |
| Case wrapper | `brc-cases/README.md` and `brc-cases/jan2013_basin_nam.case.yaml` | Manifest, executable roots, Slurm render, and validation behavior. |
| Input handshake | `../brc-tools/docs/WRF-STAGING-STATE-PLAYBOOK.md` and `../brc-tools/docs/WRF-INPUT-STAGING.md` | Fresh `manifest_<case>.json` and `contract_<case>.json` expectations. |

Optional only after the above:

| Need | Read |
| --- | --- |
| CMake comparison | `doc/README.cmake_build` |
| Local SANE automation | `.sane/wrf/README.md` |
| Human-facing overview | `brc-docs/BRC-WRF-STATE-PLAYBOOK.md` |
| CHPC usage summary | `brc-docs/BRC-WRF-USAGE.md` |

## Operating Model

| Principle | Consequence |
| --- | --- |
| No CHPC prebuilt WRF product. | Use CHPC modules for compiler/MPI/HDF5/netCDF/Jasper support only. The WRF executable root must be compiled from John's fork. |
| Architecture before command. | Read `chpc-team-resource-inventory.md` before choosing nodes, partitions, build host, storage, or module stack. |
| Legacy WRF/WPS first. | The validated CHPC path is legacy `./configure` + `./compile`; CMake is a later comparison unless explicitly chosen. |
| Pure MPI first. | Use Intel `dmpar` and basic nesting per quickstart; avoid `dm+sm` until there is a reason and evidence. |
| Source and run data split. | Source stays in git; active WPS/WRF I/O goes to scratch; durable logs and archives go to `lawson-group6`. |
| Michael is comparison evidence. | Match artifact categories and checks, not ownership paths. |
| AI can orchestrate, not improvise science. | LLM CLI sessions can draft scripts, compare docs, and summarize logs; meteorology and run approval stay human-gated. |
| brc-tools env is explicit. | Any sibling `brc-tools` Python/Herbie/source-planning command uses `conda run -n brc-tools-2026 ...` or the absolute env interpreter, never bare `python` from an inherited shell. |

## Current Truth To Preserve

| Topic | Current state |
| --- | --- |
| Proven case | Jan-2013 Uinta Basin, NAM-only, 12/4 km nest, fresh 2026-06-18 path through WPS, `real.exe`, `wrf.exe`, archive, and quicklooks. |
| Proven input identity | Fresh `brc-tools` NAM-only contract on scratch, `Vtable.NAM`, `interval_seconds = 21600`, WPS `prefix = 'NAM'`, `fg_name = 'NAM'`. Old scratch used WPS `FILE`/`FILE` naming and remains historical context only. |
| Not proven | GEFSv12 plus NAM two-stream forcing, 3-hour cadence, `fg_name = 'GEFS','NAM'`. |
| Runtime default | `lawson-np`, `notch392`, one node, 56 tasks, `900G`, `srun --mpi=pmi2`. |
| Build truth | A fresh checkout has no `real.exe` or `wrf.exe`; check disk before claiming build readiness. |
| WPS truth | John-owned WPS v4.6.0 is built at `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build/WPS`; Gate 3 evidence is under `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/gate3_20260618T054456Z_13539773/`. |
| Input contract | Fresh `brc-tools` staging emitted `/scratch/general/vast/u0737349/wrf_inputs/jan2013_basin_gefs/contract_jan2013_basin_gefs.json`; reconstructed legacy contract is a fallback until explicitly retired. |
| Practical-test harness | Gate 11 is implemented as `python brc-cases/wrf_case.py render-practical-harness ... --output-dir <outside-repo-dir>`; generated scripts are review artifacts and still require approval before `sbatch`. |

## Architecture Contract

Before compiling or rendering a real run wrapper, write a short build/run
contract with these fields:

| Field | Expected source |
| --- | --- |
| Target cluster/node | `chpc-team-resource-inventory.md` sections 2 and Q1. Default: `notch392`. |
| Account/partition | Inventory sections 1 and 3. Default: `lawson-np` / `lawson-np`. |
| Build host context | Approved compute/batch context for compile-scale work; not a login-node compile. |
| Toolchain modules | `wrf-on-chpc-quickstart.md` section 4, then live `module spider` if drift is suspected. |
| WRF configure path | Legacy first unless the user explicitly chooses CMake comparison. |
| WRF configure choices | Intel `dmpar`, basic nesting, from quickstart section 4. |
| WPS configure choices | Same stack, `JASPER*` exports, GRIB2 support check in `configure.wps`. |
| Source root | John's `~/gits/brc-wrf` git checkout. |
| WRF executable root | John-owned build from that checkout; must contain `main/real.exe` and `main/wrf.exe` or run-linked equivalents. |
| WPS executable root | John-owned WPS root with `geogrid.exe`, `ungrib.exe`, `metgrid.exe`, `link_grib.csh`, and `Vtable.NAM`. |
| Build logs | Persistent `lawson-group6/<namespace>/wrf_build_logs/...`, not repo-local sprawl. |
| Active run I/O | `/scratch/general/vast/$USER/wrf_runs/<case>/`. |
| Durable archive | `lawson-group6/<namespace>/wrf_archive/<case>/run_<UTC>/`. |

## Build Lane

Do this only after approval for compile-scale work.

For new research builds use `BRC_WRF_RESEARCH_BUILDS.md` and
`brc-cases/build_research_wrf.slurm`: a fresh detached copy of the approved
source and submodule commits, a unique durable executable root, and hashes.
The existing development-checkout binaries are historical build evidence;
do not overwrite them or infer their identity from today's checkout HEAD.

| Step | Action | Evidence | Stop point |
| ---: | --- | --- | --- |
| 1 | Confirm branch, SHA, dirty files, and remote. | `git status --short --branch --untracked-files=all`; `git rev-parse HEAD`; `git remote -v`. | Do not build if source state is ambiguous. |
| 2 | Confirm CHPC architecture and modules from `brc-knowledge`. | Notes citing inventory/quickstart sections plus live module list if checked. | Do not cargo-cult old module paths. |
| 3 | Choose build/output locations. | Explicit `WRF_SRC`, `WRF_BUILD`, `WPS_ROOT`, and build-log root. | Do not use Michael-owned roots. |
| 4 | Load compiler/MPI/HDF5/netCDF/Jasper environment. | `module -t list`, `NETCDF`, `NETCDF_C`, `JASPERLIB`, `JASPERINC`. | Do not `module load wrf` or rely on a prebuilt WRF binary. |
| 5 | Configure WRF legacy path. | `configure.wrf`, prompt choices, command transcript. | Stop if `netcdf.inc` is missing or configure choices differ from plan. |
| 6 | Compile `em_real`. | Compile command, compile log, exit status, executable timestamps/sizes. | Stop at build proof; do not run WRF. |
| 7 | Configure/compile WPS or verify John-owned WPS. | WPS log, `configure.wps` GRIB2 flags, executable paths. | Stop before WPS case execution. |
| 8 | Record a build manifest. | Markdown or text build record outside repo plus pointer from docs if promoted. | No untracked logs in git checkout. |

Current build-lane state: WRF and WPS executable proofs have passed. The WPS
v4.6.0 configure choice was option `23` for Linux x86_64 Intel Classic `dmpar`;
the successful helper pinned `DM_FC = mpif90 -f90=$(SFC)` and
`DM_CC = mpicc -cc=$(SCC)` after configure. Do not rebuild unless live disk
state or a human decision requires it.

## WPS/WRF Proof Lane

Use the proven NAM-only case first unless the human explicitly chooses
GEFS+NAM.

Current proof-lane state: Gates 5-11 passed on 2026-06-18. The fresh NAM-only
contract verified `7/7 OK`, WPS produced 14 `met_em` files, `real.exe` reached
`SUCCESS COMPLETE REAL_EM INIT`, `wrf.exe` reached `SUCCESS COMPLETE WRF`, the
archive contains 74 `wrfout` files, Gate 10 wrote five quicklook PNGs from the
new archive, and Gate 11 renders the practical-test packet from the case
manifest without submitting jobs.

| Step | Action | Evidence | Stop point |
| ---: | --- | --- | --- |
| 1 | Validate the case manifest cheaply. | `python brc-cases/wrf_case.py validate ...`. | Login-safe metadata only. |
| 2 | Validate fresh input contract if available. | Off-login `conda run -n brc-tools-2026 python -m brc_tools.nwp.wrf_staging --verify-manifest`; strict case validation. | Stop once fresh `contract_<case>.json` passes. |
| 3 | Set up WPS run directory on scratch. | Symlinks/files listed; `Vtable.NAM`; paired prefix/`fg_name`. | Stop before WPS unless approved. |
| 4 | Run WPS when approved. | `geogrid`, `ungrib`, `metgrid` logs; `met_em` count and fields. | Stop before `real.exe` unless approval includes it. |
| 5 | Run `real.exe` when approved. | `SUCCESS COMPLETE REAL_EM INIT`; saved `real.rsl.*`. | Stop before `wrf.exe` unless approval includes it. |
| 6 | Run `wrf.exe` when approved. | `srun --mpi=pmi2`; `SUCCESS COMPLETE WRF`; Slurm state. | Stop before archive cleanup if failure is ambiguous. |
| 7 | Archive and quicklook. | `wrfout`, namelists, logs, debug files, quicklooks under `lawson-group6`. | Update docs only from checked artifacts. |

## GEFS+NAM Lane

This is not the default proof lane.

| Question | Stop rule |
| --- | --- |
| Does the science need GEFS+NAM now? | If no, improve NAM repeatability first. |
| Is the `brc-tools` field map sufficient? | If no, patch or clarify `../brc-tools/docs/WRF-GEFS-NAM-FIELD-MAP.md` in a separate repo session. |
| Is `Vtable.GEFS` selected or built? | Stop before WPS if the Vtable is not reviewed. |
| Do `met_em` fields look complete? | Stop after `metgrid`; show field list and warnings before `real.exe`. |

## Michael Yardstick

Use Michael's proven demo to ask "what should John's proof produce?", not "what
path should John's proof use?"

| Yardstick item | John's equivalent |
| --- | --- |
| Michael-owned WRF/WPS roots under `lawson-group6/u6060939/wrf_build/`. | John-owned WRF built from `~/gits/brc-wrf`; John-owned WPS root in persistent storage. |
| `configure.wrf`, module list, compile log. | Same artifact types, with John's branch/SHA and module environment. |
| `geogrid.exe`, `ungrib.exe`, `metgrid.exe`, `Vtable.NAM`. | Same executable requirements, but from John's WPS root. |
| Successful `real.exe` and `wrf.exe` markers. | Same markers plus BRC debug summary/phase/inventory files. |
| Archive under group storage. | `lawson-group6/<john-namespace>/wrf_archive/<case>/run_<UTC>/`. |
| Lessons such as `srun --mpi=pmi2`, `NETCDF=$(nf-config --prefix)`, and `JASPER*`. | Adopt lessons; verify in current CHPC docs before running. |

## LLM CLI / AI Operator Lane

Use AI to reduce ambiguity and preserve state; do not let it hide commands.

| Use | Pattern |
| --- | --- |
| Long agent/API orchestration | Read `chpc-slurm-job-examples.md` section 7. Use a small owned-node job if the process is not login-node trivial. |
| Context-heavy code review | Feed this handoff plus exact target files, not the whole WRF tree. |
| Build/run scripting | Ask AI for a draft, then validate against `brc-knowledge` and local case files before execution. |
| Secrets/API keys | Never commit. Use environment or non-tracked secret files. |
| Compute-node network | Verify proxy/helpdesk status before assuming external API access from compute nodes. |
| Handoff closeout | Leave a terse record: command, host, job ID if any, exit status, artifact path, next gate. |

## Approval Gates

Do not cross these without explicit human approval and a written stop point.

| Gate | Examples |
| --- | --- |
| Compile-scale work | WRF/WPS configure or compile, SANE build actions, regression builds. |
| Transfer work | Full DTN staging, large GRIB downloads, durable promotion of scratch inputs. |
| WPS execution | `geogrid.exe`, `ungrib.exe`, `metgrid.exe`. |
| Model execution | `real.exe`, `wrf.exe`, scaling sweeps, memory benchmarks. |
| Science branch | GEFS+NAM two-stream proof, new nesting, physics/stochastic changes. |

## Evidence Checklist

Every serious step should leave these fields somewhere durable:

| Category | Required fields |
| --- | --- |
| Source | repo path, branch, SHA, dirty status, changed files. |
| Environment | host, date/time UTC, modules, key env vars, working directory. |
| Build | configure choices, compile command, log path, executable paths, timestamps. |
| WPS | WPS root, Vtable, prefix/`fg_name`, `geog_data_path`, `met_em` count, warnings. |
| WRF | Slurm account/partition/node/tasks/memory, launcher, `real.exe` marker, `wrf.exe` marker. |
| Input | manifest path, contract path, source stream, cadence, verification status. |
| Archive | archive root, file counts, key logs, debug files, quicklook paths. |
| Decision | what changed, what is still unproven, who approved the next gate. |

## Copy-Paste Prompt For Next AI Session

```text
You are in ~/gits/brc-wrf. Goal: advance John's end-to-end WRF workflow, not
general docs cleanup. Use doc/BRC_WRF_END_TO_END_AI_HANDOFF.md as the routing
map. Read brc-knowledge chpc-team-resource-inventory.md before choosing any
architecture, module, path, Slurm, or storage setting; then read
wrf-on-chpc-quickstart.md for WRF-specific build/run details.

Michael's lawson-group6/u6060939/wrf_build path is a yardstick only. Do not use
it as John's WRF or WPS root. John's WRF executable root must be compiled from
~/gits/brc-wrf with branch/SHA provenance. WPS must be John-owned too.

First decide the next gate:
1. Render/review the Gate 11 practical-test packet for the proven NAM-only baseline.
2. Scaling/memory benchmark rows; submissions require approval.
3. GEFS+NAM WPS-only field proof after science approval.
4. Storage-retention or fallback-contract retirement decision.

Stay login-node-safe unless approval explicitly allows compile/WPS/WRF/Slurm
work. Leave breadcrumbs: command, evidence, owner repo, artifact path, stop
point.
```
