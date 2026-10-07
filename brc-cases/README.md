# BRC WRF Case Scaffolds

This directory holds BRC-local case manifests and the cheap helper used to
review them before any WPS, WRF, or Slurm work starts.

## Gigawatts bounded preparation

`gigawatts_600m.case.yaml` and `prepare_gigawatts.py` render the October two-domain
packet. Separate `gigawatts_wps.slurm`, `gigawatts_real.slurm` and
`gigawatts_smoke.slurm` stop at their respective evidence gates. Current jobs,
source pins and approval scope are recorded in the ub-wx experiment README.

`gigawatts_metgrid_resume.slurm` is a bounded continuation for an initial WPS
job that reaches TIMEOUT after entering d02. It preserves completed files and
intermediates, redoes the last-started hour plus a completed overlap hour on
eight MPI ranks, compares every overlap field, and verifies all 98 output
clocks, required fields and levels. It refuses other failure states. The
initial render used a singleton metgrid launch; Slurm refused a runtime-limit
increase, so this packet avoids redoing the completed ungrib/domain-one work.

`prepare_delayed_static.py` prepares the later d03 static-only input from an
actual real.exe file. It audits the released build's complete Registry include
graph and uses otherwise empty input stream 6 with an explicit static allowlist.
It preserves the original, records hashes and field selection, and changes only
the copy's Times/START_DATE to the activation time. It excludes atmospheric,
tracer, snow/ice and transient surface/soil fields. Required namelist settings
are emitted in its provenance JSON; the three-domain packet and actual model
inheritance still require review. Job 16102225 passed four synthetic tests and
the released Registry audit. Details and timing are in
`../ub-wx/experiments/drainage-canyons-gigawatts/handoff/delayed_nest_review.md`.

`gigawatts_front_static.slurm` and `prepare_gigawatts_front_static.py` derive
that d03 input only after the two-domain real/initial-field checks pass. They
compare parent geometry with the accepted front geogrid, process two d03
forcing frames with eight MPI ranks, run real.exe, and prepare the restricted
static file plus the 19:00/19:15/20:15 delayed namelist. Three namelist regression
tests passed in job 16103167. No wrf.exe integration occurs; actual static-file
and delayed-activation evidence remain independent acceptance stages.

`gigawatts_delayed.slurm` makes one bounded 75-minute model launch on 56 ranks
(maximum eight wall-hours), with the d03 activation strictly inside it. It
requires accepted real/initial fields, accepted seeded transport, and the
matching static-packet review marker. The generic conveyor splits at domain
activation boundaries and must not be substituted for this test. The helper
copies/hashes parent restarts, checks all-rank logs, exact parent/d03 clocks,
static interior terrain and inherited tracer bounds, and records surface-state
differences for review. Six inherited-tracer regressions passed in 16103469.
There is no production continuation or restart pruning; actual model proof is
still required.

`gigawatts_init_probe.slurm` uses the eight free ranks for initialization and
three coarse steps (27 simulated seconds), after real/initial-field acceptance.
It suppresses history/auxiliary output, preserves the accepted inputs, verifies
all-rank logs and the exact end time, and has a 30-minute wall limit. This can
expose initialization defects while the full node is occupied. It provides no
performance, transport or nocturnal-stability acceptance; the matched tests
retain their 56-rank layout.

The checkpoint is intentionally small:

1. Write or edit a `*.case.yaml` file.
2. Validate the schema and cheap local facts:

   ```bash
   python brc-cases/wrf_case.py validate brc-cases/jan2013_basin_nam.case.yaml
   ```

   The Jan-2013 manifest points to the original `brc-tools` scratch manifest,
   and its contract path points to a tracked reconstructed NAM-only contract in
   this directory. Fresh `brc-tools` staging should emit a scratch
   `contract_<case>.json` next to the manifest instead.

3. Use stricter file checks only after inputs and run directories exist:

   ```bash
   python brc-cases/wrf_case.py validate --strict-files brc-cases/jan2013_basin_nam.case.yaml
   ```

   Strict validation also checks the declared WRF/WPS executable roots. The WRF
   build root must expose `main/real.exe`, `main/wrf.exe`, and runtime source
   files under `run/`; a scratch run directory with copied executables is not a
   build root. The WPS root must expose top-level `geogrid.exe`, `ungrib.exe`,
   `metgrid.exe`, `link_grib.csh`, and the case's configured
   `wps.vtable` under `ungrib/Variable_Tables/` (`Vtable.NAM` by default). It
   also rejects repo-local staged inputs, run directories, archive roots, logs,
   and generated data paths.

4. Render the Slurm script for review. This writes text only; it does not call
   `sbatch`.

   ```bash
   python brc-cases/wrf_case.py render-slurm brc-cases/jan2013_basin_nam.case.yaml
   ```

   This case uses the `owned_notch392_max` Slurm profile: owned `lawson-np`,
   `notch392`, one node, 56 tasks, `900G`, and `srun --mpi=pmi2`, matching the
   current `brc-knowledge` WRF quickstart. The earlier proof showed lower memory
   was enough; this profile deliberately reserves most of the large node for a
   high-powered single run.

   The rendered run wrapper writes a compact debug layer beside WRF's native
   `rsl.*` logs:

   | File | Purpose |
   | --- | --- |
   | `debug/run_debug_summary.txt` | Host, job, commit, paths, natural-language settings table, five gotchas, final status. |
   | `debug/run_phase_times.tsv` | `real.exe`, marker checks, `wrf.exe`, and archive phase timings with exit codes. |
   | `debug/run_file_inventory.tsv` | Counts, bytes, and newest mtimes for key `met_em`, `wrfinput`, `wrfbdy`, `wrfout`, and log patterns. |

   These files are first written under `<wrf_run>/brc_run_debug/` and then
   copied to `<archive-run>/debug/`, including failure exits when the archive
   path can be created.

5. Render the Gate 11 practical-test harness packet. This writes review
   artifacts outside the checkout; it does not submit Slurm or read staged,
   WPS/WRF, NetCDF, or archive artifacts.

   ```bash
   python brc-cases/wrf_case.py render-practical-harness \
     brc-cases/jan2013_basin_nam.case.yaml \
     --output-dir /tmp/brc_gate11_jan2013_basin_gefs
   ```

   The packet contains a `README.md`, `PREPARE_CHECKLIST.md`,
   `APPROVAL_PACKET.md`, approval-gated `prepare_<scenario>.sh` copy/check
   helpers, a baseline Slurm wrapper, scaling wrappers for 16/28/56 tasks,
   optional memory-candidate wrappers, approval boundaries, validation
   commands, blank result tables, and a closeout record template. Generated
   wrappers keep per-scenario scratch and archive paths under
   `practical_tests/<scenario>/`, fail fast if the scenario `wrf_run` directory
   is not prepared with `real.exe`, `wrf.exe`, `namelist.input`, and `met_em`
   files, or if the scenario executables do not byte-match
   `paths.wrf_build/main/{real.exe,wrf.exe}`. Runtime physics/table files must
   also byte-match John's `paths.wrf_build/run/` source files before `real.exe`
   starts. The prepare checklist sources executables and runtime physics files
   from John's compiled WRF tree, and uses the approved proven run artifacts
   only for `namelist.input` and `met_em` files. Current-case runtime preflight includes
   `CAMtr_volume_mixing_ratio`, `RRTMG_LW_DATA`, `RRTMG_SW_DATA`, ozone files,
   and core land-surface tables. Practical scripts set Slurm `--chdir`,
   stdout, and stderr to the shared
   `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf`
   root so early failures remain visible even when review packets are rendered
   under `/tmp`. They report the full missing preflight set before exiting, so
   a failed setup is not mistaken for WRF runtime evidence. The generated prep
   helpers require `BRC_PREP_APPROVED=YES`, refuse Michael-owned comparison
   paths, copy/check files only, and never submit Slurm or execute WRF. Any
   copy/check of scratch or archive WRF files remains off-login and
   approval-gated, and `sbatch` still requires explicit approval.

6. Render the RAP WPS-only field proof packet when working the Pelican RAP
   hot-swap. This writes review artifacts only; it does not submit Slurm or run
   WPS by itself. The rendered script requires
   `BRC_WPS_FIELD_PROOF_APPROVED=YES` and stops after `ungrib.exe`,
   `metgrid.exe`, `met_em` field extraction, `num_metgrid_levels`, warning
   capture, and the field checklist. It never runs `real.exe`, `wrf.exe`, the
   full conveyor, or quicklooks.

   ```bash
   python brc-cases/wrf_case.py render-wps-field-proof \
     brc-cases/pelican2013_rap_3_1_333m_75lev.case.yaml \
     --output-dir /uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_rap_3_1_333m_75lev/control/wps_field_proof_<UTC>
   ```

   The RAP proof packet uses the durable Pelican control `namelist.wps` as a
   template and the existing NAM 333 m `geo_em.d0*.nc` files as the domain
   source. If those scratch `geo_em` files have expired, stop and either restore
   them or explicitly approve a geogrid rerun before continuing.

7. Render a one-command no-run report when you want a compact login-safe
   checkpoint for handoff or approval review:

   ```bash
   python brc-cases/wrf_case.py render-no-run-report \
     brc-cases/jan2013_basin_nam.case.yaml
   ```

   The report writes under `/tmp` by default, renders the Gate 11 packet and a
   standalone Slurm review script outside the checkout, records branch/SHA,
   dirty state, case metadata validation, shell syntax status, artifact paths,
   and the explicit stop point. It does not run strict file checks, hash
   manifests, read NetCDF/archive artifacts, render quicklooks, submit Slurm, or
   run WPS/WRF.

8. Compare existing `namelist.input` text artifacts without touching model
   outputs:

   ```bash
   python brc-cases/namelist_diff.py \
     --case label_a=/path/to/run_or_namelist.input \
     --case label_b=/path/to/other_run_or_namelist.input \
     --output-dir /tmp/brc_wrf_namelist_diff
   ```

   The helper accepts labeled `LABEL=PATH` inputs where `PATH` is either a
   `namelist.input` file or a directory containing one. It parses normalized
   section/key values, writes a Markdown summary, a TSV matrix, and pairwise
   raw unified diffs, and refuses output inside this checkout. It reads text
   namelists only; it does not run WPS, WRF, Slurm, NetCDF reads, quicklooks,
   or archive promotion.

9. Render a paired derived-run control packet from an accepted WRF
   namelist and `met_em` source without rerunning WPS:

   ```bash
   python brc-cases/wrf_treatment.py \
     brc-cases/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s_slope.case.yaml \
     --output-dir /path/outside/this/checkout/control/run_<UTC> \
     --run-id run_<UTC>
   ```

   The treatment manifest declares `set.SECTION.KEY` assignments for physics
   or nesting sensitivities and, when a
   derived run reuses another case's staging sidecars, identifies that source
   with `forcing.artifact_case_name`. The renderer patches a copy of the
   accepted namelist, proves that only the declared normalized keys changed,
   writes raw and structured diffs, and syntax-checks separate preparation,
   WRF, and quicklook scripts. Each script has its own approval environment
   guard. Rendering does not inspect NetCDF, copy scratch data, submit Slurm,
   or run WRF.

   The accepted default-terrain GFS feedback companion is declared in
   `pelican2013_gfs_3_1_333m_75lev_oneway.case.yaml`. It reuses the accepted
   GFS staging sidecars, changes only `domains.feedback`, and routes exact run
   and post-processing evidence through `doc/BRC_WRF_EXPERIMENT_TODO.md`.

10. Render no-run visual quicklooks from the existing proof artifacts:

   ```bash
   python brc-cases/wrf_quicklook.py check brc-cases/jan2013_basin_nam.case.yaml
   python brc-cases/wrf_quicklook.py render brc-cases/jan2013_basin_nam.case.yaml
   ```

   The quicklook helper verifies the `brc-tools` input manifest first, then
   reads existing WPS `met_em` files and archived `wrfout` files. It does not
   run WPS, `real.exe`, `wrf.exe`, Slurm, or new input staging. It must run
   from an approved compute or interactive context, not a login node.
   Generated PNGs default to `<archive-run>/quicklooks/dXX/` under the durable
   `lawson-group6` archive; repo-local PNG output is refused. Use
   `--output-dir` only when you intentionally need a separate preserved render.
   Current WRF-output quicklooks render 10 standardized PNGs per case domain
   under `<archive-run>/quicklooks/dXX/`: temperature/wind, temperature anomaly,
   2 m potential temperature, wind speed, PBL height, snow depth, skin
   temperature, surface pressure, and W-E/S-N potential-temperature cross
   sections. The helper is a WRF-file adapter; reusable plotting primitives
   live in `../brc-tools/brc_tools/visualize/grid.py`.

   Supplemental review products can be added without touching the parent PNGs:

   ```bash
   python brc-cases/wrf_quicklook.py render-supplemental \
     brc-cases/jan2013_basin_nam.case.yaml
   ```

   This writes four add-on PNGs per domain below the selected output root:
   `_600hPa/01_600hPa_height_rh_wind_barbs.png` from the 1-hour lead WRF file,
   and `_4h/{01_t2_10m_wind.png,04_10m_wind_speed.png,06_snow_depth.png}` from
   the 4-hour lead WRF file. Use `--output-dir` to target an existing stamped
   comparison root such as `quicklooks/standardized_compare_<UTC>/`.

   Physics-treatment runs can also add surface-energy diagnostics at the
   four-hour lead without changing the standard or supplemental products:

   ```bash
   python brc-cases/wrf_quicklook.py render-surface-energy \
     brc-cases/<treatment>.case.yaml --archive-run <exact-run-path>
   ```

   This writes `SWDOWN`, `GLW`, `HFX`, and `LH` maps under each domain's
   `_4h_energy/` directory. The treatment packet renderer expects 12 such
   maps in addition to the established 42 standard/supplemental PNGs.
   Path-only quicklook unit tests are login-node safe because they do not
   verify manifests, open NetCDF files, read archives, or render PNGs.
   The workflow source is tracked in `jan2013_nam_workflow.mmd`.

10. Prepare custom WPS `HGT_M` terrain tiles. Login-safe commands can plan tiles
   and render a Slurm packet. DEM metadata queries, network download/cache, and
   GDAL static-tile builds should run from the rendered Slurm scripts, not on a
   login node. Generated rasters and packet outputs stay outside this checkout.

   ```bash
   python brc-cases/wps_hgt_static.py plan --bounds -114 37 -105 44

   python brc-cases/wps_hgt_static.py render-slurm-packet \
     --case-name pelican2013_nam_3_1_333m_75lev_oneway_terrain3s \
     --bounds -114 37 -105 44 \
     --packet-dir /uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/pelican2013_nam_3_1_333m_75lev_oneway_terrain3s/control/terrain_static_<UTC> \
     --geog-data-path /scratch/general/vast/$USER/wps_geog_terrain3s \
     --rel-path topo_brc_custom_3s \
     --download-dir /scratch/general/vast/$USER/wrf_inputs/pelican2013_terrain3s/usgs_3dep_1arcsec \
     --max-products 600 \
     --min-free-gb 10

   bash /path/to/terrain_static_<UTC>/submit_terrain_static.sh

   python brc-cases/wps_hgt_static.py patch-geogrid-table \
     --base /path/to/GEOGRID.TBL.ARW \
     --output /tmp/brc-wrf-terrain3s-control/GEOGRID.TBL.ARW.terrain3s \
     --token brc_custom_3s \
     --rel-path topo_brc_custom_3s

   python brc-cases/wps_hgt_static.py render-namelist \
     --template /path/to/namelist.wps \
     --output /tmp/brc-wrf-terrain3s-control/namelist.wps \
     --token brc_custom_3s \
     --geog-data-path /scratch/general/vast/$USER/wps_geog_terrain3s
   ```

   The default `plan` bounds are the current Pelican terrain lane's broad Utah
   review box. The helper emits regular-lat/lon, signed 16-bit, 3 arc-second,
   WPS continuous terrain tiles with `tile_bdr=3`; the run-local
   `GEOGRID.TBL` token should be used only for `HGT_M`, with all other static
   fields falling through to `default`. The Pelican broad box needs 63 WPS
   output tiles, but the current USGS 1 arc-second source query de-duplicates
   to 99 one-degree GeoTIFF tiles, about 4.53 GiB before GDAL temporary files.
   The generated 3 arc-second WPS `index` must include `filename_digits = 6`
   because the global tile indices exceed five digits; without it geogrid can
   select the custom source token but fill `HGT_M` with zeros. Keep at least
   10 GiB free in the DEM cache filesystem. The rendered download job defaults
   to the CHPC DTN convention used by `brc-tools`:
   `account=dtn`, `partition=notchpeak-dtn`, `qos=notchpeak-dtn`.

`wrf_case.py` uses only the Python standard library. Because this checkout does
not currently carry a YAML dependency, the `*.case.yaml` format is a deliberately
small subset: top-level sections, two-space-indented keys, quoted strings,
integers, booleans, and bracketed lists. Avoid anchors, nested lists, and complex
YAML features.

The helper is a pre-run review gate, not a workflow engine. Real WPS, `real.exe`,
`wrf.exe`, scaling sweeps, and Slurm submission still require explicit human
approval.

NWP input downloads and staging are not owned here. Use `../brc-tools`, its
Herbie-backed paths where available, and `notchpeak-dtn` for full NWP transfer
work. Static WPS terrain packets are a narrow exception in this repo because
they build WPS geography, not forcing contracts. This repo should consume fresh
NWP `contract_<case>.json` sidecars, not add GRIB download logic. The RAP review case
`pelican2013_rap_3_1_333m_75lev.case.yaml` points at the staged RAP contract
and deliberately leaves metgrid-derived counts pending until the WPS-only
field-adequacy proof runs off-login.

When a case-review task needs sibling `brc-tools` Python, Herbie, source
planning, staging, manifest verification, or tests, force the maintained env:

```bash
conda run -n brc-tools-2026 python ...
conda run -n brc-tools-2026 pytest ...
```

Do not use bare `python` or `pytest` for `brc-tools` commands from this repo;
Codex shells can inherit unrelated environments.

`wrf_quicklook.py` is separate from `wrf_case.py` on purpose: the case validator
stays dependency-free, while quicklook rendering uses the local NetCDF and
plotting stack when visual QA is wanted.
