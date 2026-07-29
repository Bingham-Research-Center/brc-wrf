#!/bin/bash
# Gate-B geogrid-only domain preview for ashley_drainage_120m (3 km / 600 m / 120 m).
#
# Deliberately simpler than geogrid_preview.slurm, which had to BUILD a custom
# 1-arc-second terrain set for a 37 m nest. At 120 m the existing 3-arc-second set
# (~90 m source) is the grid-appropriate one and already exists, so this runner only:
#   (1) patches a run-local GEOGRID.TBL with the brc_custom_3s token,
#   (2) runs geogrid.exe over the three domains,
#   (3) verifies d02 AND d03 actually used that token (no silent default fallback),
#   (4) renders domain_preview.png with the drainage waypoints marked,
#   (5) archives the review packet.
# It STOPS before ungrib, metgrid, real.exe and wrf.exe.
#
# The namelist.wps it stages is GENERATED -- edit the spec and re-render, never the
# namelist:
#   python brc-cases/domain_calc.py brc-cases/specs/ashley_drainage_120m.domain.toml \
#       --namelist-wps $WRF_ARCHIVE/ashley_drainage_120m/control/draft/namelist.wps
#
# Submit from a login shell, review-approved:
#   sbatch brc-cases/geogrid_preview_120m.slurm

#SBATCH --job-name=geogrid_preview_ashley120m
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --mem=48G
#SBATCH --time=00:20:00
#SBATCH --output=/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/geogrid_preview_120m_%j.out
#SBATCH --error=/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/geogrid_preview_120m_%j.out
#SBATCH --export=ALL

set -euo pipefail

fail() { echo "ERROR: $*" >&2; exit 2; }

# ---- configuration (env-overridable) ---------------------------------------
USER_NAME="${USER:-u0737349}"
CASE="${PREVIEW_CASE:-ashley_drainage_120m}"
WRF_SRC="${PREVIEW_WRF_SRC:-/uufs/chpc.utah.edu/common/home/u0737349/gits/brc-wrf}"
WPS_ROOT="${PREVIEW_WPS_ROOT:-/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build/WPS}"
# The 3-arc-second set is a COMPLETE geog_data_path (topo + landuse + soil + orogwd),
# so it is used directly -- no symlink assembly step is needed.
GEOG_DIR="${PREVIEW_GEOG_DIR:-/scratch/general/vast/${USER_NAME}/wps_geog_terrain3s}"
RUN_ROOT="${PREVIEW_RUN_ROOT:-/scratch/general/vast/${USER_NAME}/wrf_runs/${CASE}}"
WPS_RUN="${PREVIEW_WPS_RUN:-${RUN_ROOT}/domain_preview/wps_run}"
ARCHIVE_ROOT="${PREVIEW_ARCHIVE_ROOT:-/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/${CASE}}"
NAMELIST_TEMPLATE="${PREVIEW_NAMELIST:-${ARCHIVE_ROOT}/control/draft/namelist.wps}"
FIG_KEEP="${PREVIEW_FIG_KEEP:-/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/ub-wx-figures/ashley-drainage-120m}"
CONDA_PY="${PREVIEW_CONDA_PY:-/uufs/chpc.utah.edu/common/home/u0737349/software/pkg/miniforge3/envs/brc-tools-2026/bin/python}"

TOKEN_3S="brc_custom_3s"; REL_3S="topo_brc_custom_3s"
HELPER="${WRF_SRC}/brc-cases/wps_hgt_static.py"
PLOT="${WRF_SRC}/brc-cases/geogrid_preview_plot.py"
GEOGRID_TBL_BASE="${WPS_ROOT}/geogrid/GEOGRID.TBL.ARW"
GEOGRID_EXE="${WPS_ROOT}/geogrid.exe"
UTC="$(date -u +%Y%m%dT%H%M%SZ)"
JOBID="${SLURM_JOB_ID:-manual}"
PACKET="${ARCHIVE_ROOT}/domain_review/geogrid_${UTC}_${JOBID}"
NDOM="${PREVIEW_NDOM:-3}"   # overridable: the two-domain 600 m spec sets 2

# Plot annotation. Both default to the drainage case this script was written for, and
# both must be overridden when it is pointed at another case -- a preview PNG captioned
# with the wrong ladder is review evidence that says something untrue.
TITLE="${PREVIEW_TITLE:-${CASE}: 3 km / 600 m / 120 m, d03 Ashley Valley drainage}"
# Semicolon-separated "Name,lat,lon" triples; semicolons because the names contain
# spaces. Parsed into repeated --target arguments below.
TARGETS_SPEC="${PREVIEW_TARGETS:-Dry Fork,40.58,-109.63;Maeser,40.48,-109.58;Vernal,40.455,-109.53;Jensen,40.37,-109.35;Split Mtn,40.44,-109.20}"

target_args=()
IFS=';' read -r -a _target_list <<< "${TARGETS_SPEC}"
for _t in ${_target_list[@]+"${_target_list[@]}"}; do
    [[ -n "${_t}" ]] || continue
    IFS=',' read -r _tname _tlat _tlon <<< "${_t}"
    [[ -n "${_tname}" && -n "${_tlat}" && -n "${_tlon}" ]] \
        || fail "bad PREVIEW_TARGETS entry (want 'Name,lat,lon'): ${_t}"
    target_args+=(--target "${_tname}" "${_tlat}" "${_tlon}")
done

echo "geogrid preview (120 m) start $(date -u +%Y-%m-%dT%H:%M:%SZ) host=$(hostname) job=${JOBID}"
echo "  case=${CASE} wps_run=${WPS_RUN} geog=${GEOG_DIR}"

module purge 2>/dev/null || true

# ---- preflight -------------------------------------------------------------
[[ -x "${GEOGRID_EXE}" ]] || fail "geogrid.exe not executable: ${GEOGRID_EXE}"
[[ -f "${GEOGRID_TBL_BASE}" ]] || fail "missing GEOGRID.TBL.ARW: ${GEOGRID_TBL_BASE}"
[[ -f "${NAMELIST_TEMPLATE}" ]] || fail "missing generated namelist.wps: ${NAMELIST_TEMPLATE} (run domain_calc.py first)"
[[ -f "${HELPER}" ]] || fail "missing helper: ${HELPER}"
[[ -f "${PLOT}" ]] || fail "missing plot script: ${PLOT}"
[[ -d "${GEOG_DIR}/${REL_3S}" ]] || fail "missing 3-arc-second terrain set: ${GEOG_DIR}/${REL_3S}"
[[ -e "${GEOG_DIR}/topo_gmted2010_30s" ]] || fail "default topo missing under ${GEOG_DIR}"

grep -q "max_dom *= *${NDOM}" "${NAMELIST_TEMPLATE}" || fail "namelist.wps is not max_dom=${NDOM}"
grep -q "0000-00-00" "${NAMELIST_TEMPLATE}" && \
    echo "  NOTE: namelist dates are placeholders. Fine for geogrid (geometry only); they MUST be real before ungrib."

mkdir -p "${WPS_RUN}" "${PACKET}"

# ---- step 1: run-local patched GEOGRID.TBL ---------------------------------
echo "[1/5] patching GEOGRID.TBL with ${TOKEN_3S}"
if [[ -L "${WPS_RUN}/geogrid" ]]; then rm -f "${WPS_RUN}/geogrid"; fi
mkdir -p "${WPS_RUN}/geogrid"
TBL="${WPS_RUN}/geogrid/GEOGRID.TBL"
"${CONDA_PY}" -B "${HELPER}" patch-geogrid-table --base "${GEOGRID_TBL_BASE}" \
    --output "${TBL}" --token "${TOKEN_3S}" --rel-path "${REL_3S}"
grep -q "${TOKEN_3S}:" "${TBL}" || fail "patched table missing ${TOKEN_3S} token"

# ---- step 2: stage and run geogrid -----------------------------------------
echo "[2/5] staging + running geogrid.exe in ${WPS_RUN}"
cp -f "${NAMELIST_TEMPLATE}" "${WPS_RUN}/namelist.wps"
ln -sfn "${GEOGRID_EXE}" "${WPS_RUN}/geogrid.exe"
grep -q "$(basename "${GEOG_DIR}")" "${WPS_RUN}/namelist.wps" || \
    fail "staged namelist.wps geog_data_path does not reference ${GEOG_DIR}"
rm -f "${WPS_RUN}"/geo_em.d0*.nc "${WPS_RUN}/geogrid.log"

module purge
module load intel-oneapi-compilers/2021.4.0
module load intel-oneapi-mpi/2021.1.1
module load hdf5/1.14.3
module load netcdf-c/4.9.2
module load netcdf-fortran/4.6.1

cd "${WPS_RUN}"
t0=$(date -u +%s)
srun --mpi=pmi2 -n 1 ./geogrid.exe || fail "geogrid.exe failed (see ${WPS_RUN}/geogrid.log)"
t1=$(date -u +%s)
grep -q "Successful completion of program geogrid.exe" geogrid.log || fail "geogrid.log has no success marker"

# ---- step 3: guard against silent default fallback --------------------------
echo "[3/5] verifying HGT_M source per domain"
ndom_found=$(ls -1 geo_em.d0*.nc 2>/dev/null | wc -l)
[[ "${ndom_found}" -eq "${NDOM}" ]] || fail "expected ${NDOM} geo_em files, found ${ndom_found}"
hgt_src() { grep -A3 "Processing domain $1 of ${NDOM}" geogrid.log \
    | grep -m1 "data source for HGT_M" || true; }
grep -n "data source for HGT_M" geogrid.log > "${PACKET}/geogrid_hgt_source_grep.txt" || true
d2src="$(hgt_src 2)"; d3src="$(hgt_src 3)"
echo "      d02: ${d2src}"
echo "      d03: ${d3src}"
echo "${d2src}" | grep -q "${TOKEN_3S}" || fail "d02 did NOT use ${TOKEN_3S} (silent fallback): ${d2src}"
# d03 only exists when NDOM=3; the two-domain 600 m spec has no fine nest.
if [[ "${NDOM}" -ge 3 ]]; then
  echo "${d3src}" | grep -q "${TOKEN_3S}" || fail "d03 did NOT use ${TOKEN_3S} (silent fallback): ${d3src}"
fi

# ---- step 4: render preview -------------------------------------------------
echo "[4/5] rendering domain_preview.png"
module purge
"${CONDA_PY}" -B "${PLOT}" \
    --wps-run "${WPS_RUN}" \
    --out-png "${WPS_RUN}/domain_preview.png" \
    --summary-tsv "${WPS_RUN}/geogrid_geo_em_summary.tsv" \
    --title "${TITLE}" \
    ${target_args[@]+"${target_args[@]}"}
[[ -f "${WPS_RUN}/domain_preview.png" ]] || fail "plot did not produce domain_preview.png"

# ---- step 5: archive review packet -----------------------------------------
echo "[5/5] archiving review packet"
printf "geogrid\t%s\t%s\n" "$((t1 - t0))" "0" > "${WPS_RUN}/geogrid_phase_times.tsv"
{
  printf "case\t%s\n" "${CASE}"
  printf "tag\tgeogrid_%s\n" "${UTC}"
  printf "job_id\t%s\n" "${JOBID}"
  printf "host\t%s\n" "$(hostname)"
  printf "finish_utc\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf "wrf_commit\t%s\n" "$(git -C "${WRF_SRC}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf "wps_root\t%s\n" "${WPS_ROOT}"
  printf "geog_root\t%s\n" "${GEOG_DIR}"
  printf "geog_data_res\td01 default; d02-d03 %s+default\n" "${TOKEN_3S}"
  printf "hgt_m_source_d02\t%s\n" "${d2src}"
  printf "hgt_m_source_d03\t%s\n" "${d3src}"
  printf "namelist_source\t%s (generated by domain_calc.py)\n" "${NAMELIST_TEMPLATE}"
  printf "wps_run\t%s\n" "${WPS_RUN}"
  printf "archive\t%s\n" "${PACKET}"
  printf "stop_point\tgeogrid-only preview; did not run ungrib, metgrid, real.exe, wrf.exe, or quicklooks\n"
} > "${WPS_RUN}/domain_preview_summary.tsv"

cp -f "${WPS_RUN}/domain_preview.png" "${WPS_RUN}/geogrid_geo_em_summary.tsv" \
      "${WPS_RUN}/domain_preview_summary.tsv" "${WPS_RUN}/geogrid_phase_times.tsv" \
      "${WPS_RUN}/namelist.wps" "${WPS_RUN}/geogrid.log" "${TBL}" "${PACKET}/" 2>/dev/null || true
cp -f "${WPS_RUN}"/geo_em.d0*.nc "${PACKET}/" 2>/dev/null || true
{ ls -l "${WPS_RUN}" ; echo "---" ; ls -l "${PACKET}" ; } > "${PACKET}/file_inventory.tsv" 2>/dev/null || true

mkdir -p "${FIG_KEEP}"
cp -f "${WPS_RUN}/domain_preview.png" "${FIG_KEEP}/domain_preview.png"
cp -f "${WPS_RUN}/domain_preview_summary.tsv" "${FIG_KEEP}/domain_preview_summary.tsv" 2>/dev/null || true

echo "geogrid preview OK: packet=${PACKET}"
echo "  domain_preview.png -> ${FIG_KEEP}/domain_preview.png"
echo "geogrid preview stop $(date -u +%Y-%m-%dT%H:%M:%SZ)"
