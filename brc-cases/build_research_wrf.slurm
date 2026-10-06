#!/bin/bash
# Approved compile proof only. Supply SOURCE, full SHA, new BUILD and existing EVIDENCE.
# sbatch --output=<evidence>/slurm_%j.out --error=<evidence>/slurm_%j.err \
#   brc-cases/build_research_wrf.slurm SOURCE SHA BUILD EVIDENCE
#SBATCH --job-name=wrf_tracers24_build
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00

set -euo pipefail
[[ $# == 4 && -n ${SLURM_JOB_ID:-} ]] || { echo 'Expected four arguments and a Slurm allocation'; exit 2; }
WRF_SOURCE=$(realpath "$1")
WRF_SHA=$2
WRF_BUILD=$3
EVIDENCE=$(realpath "$4")
[[ $WRF_SHA =~ ^[0-9a-f]{40}$ && $WRF_BUILD == /* && ! -e $WRF_BUILD ]]
[[ $(git -C "$WRF_SOURCE" rev-parse "$WRF_SHA^{commit}") == "$WRF_SHA" ]]
SUMMARY="$EVIDENCE/job_summary.txt"
trap 'rc=$?; printf "exit_code=%s\nfinished_utc=%s\n" "$rc" "$(date -u +%FT%TZ)" >> "$SUMMARY"' EXIT
printf 'source_commit=%s\nsource=%s\nbuild=%s\njob_id=%s\nhost=%s\nstarted_utc=%s\n' \
    "$WRF_SHA" "$WRF_SOURCE" "$WRF_BUILD" "$SLURM_JOB_ID" "$(hostname)" "$(date -u +%FT%TZ)" > "$SUMMARY"

# Independent Git object stores: future changes/cleanup in the development checkout
# cannot change this build's source. Never reuse old objects or executables.
git clone --no-hardlinks --no-checkout -- "$WRF_SOURCE" "$WRF_BUILD" > "$EVIDENCE/clone.log" 2>&1
git -C "$WRF_BUILD" checkout --detach "$WRF_SHA" >> "$EVIDENCE/clone.log" 2>&1
copy_submodules() {
    local source=$1 dest=$2 commit=$3 mode kind sha path
    while read -r mode kind sha path; do
        [[ $mode == 160000 ]] || continue
        git -C "$source/$path" cat-file -e "$sha^{commit}"
        git clone --no-hardlinks --no-checkout -- "$source/$path" "$dest/$path"
        git -C "$dest/$path" checkout --detach "$sha"
        copy_submodules "$source/$path" "$dest/$path" "$sha"
    done < <(git -C "$source" ls-tree -r "$commit")
}
copy_submodules "$WRF_SOURCE" "$WRF_BUILD" "$WRF_SHA" >> "$EVIDENCE/clone.log" 2>&1
cd "$WRF_BUILD"
git status --porcelain=v1 --untracked-files=all > "$EVIDENCE/source_status.txt"
[[ ! -s "$EVIDENCE/source_status.txt" ]]
git submodule status --recursive > "$EVIDENCE/submodules.txt"
git show --no-patch --format=fuller HEAD > "$EVIDENCE/source_commit.txt"
git ls-tree -r HEAD > "$EVIDENCE/source_tree.tsv"
cp Registry/Registry.EM "$EVIDENCE/Registry.EM"
cp brc-cases/build_research_wrf.slurm "$EVIDENCE/build_research_wrf.slurm"
python3 -B brc-cases/check_tracer_registry.py . > "$EVIDENCE/tracer_source_check.txt"

if ! type module >/dev/null 2>&1; then source /etc/profile.d/modules.sh; fi
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1
module load hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
module -t list > "$EVIDENCE/modules_loaded.txt" 2>&1
export NETCDF="$(nf-config --prefix)" NETCDF_C="$(nc-config --prefix)"
export JASPERLIB=/usr/lib64 JASPERINC=/usr/include/jasper
export WRF_EM_CORE=1 WRF_CHEM=0 WRF_KPP=0 WRF_DA_CORE=0 WRF_PLUS_CORE=0 WRF_HYDRO=0
export OMP_NUM_THREADS=1
[[ -f "$NETCDF/include/netcdf.inc" ]]
{
    printf 'NETCDF=%s\nNETCDF_C=%s\n' "$NETCDF" "$NETCDF_C"
    command -v ifort icc mpif90 mpicc nf-config nc-config
    ifort --version
    icc --version
    nf-config --all
    nc-config --all
} > "$EVIDENCE/build_env.txt" 2>&1
printf '15\n1\n' | ./configure > "$EVIDENCE/configure_transcript.txt" 2>&1
grep -Eq '^DMPARALLEL[[:space:]]*=[[:space:]]*1' configure.wrf
grep -Eq '^SFC[[:space:]]*=[[:space:]]*ifort' configure.wrf
cp configure.wrf "$EVIDENCE/configure.wrf"
printf 'phase=compile\n' >> "$SUMMARY"
./compile -j "${SLURM_CPUS_PER_TASK}" em_real > "$EVIDENCE/compile_em_real.log" 2>&1
# WRF's compile driver may return zero after an internal make failure.
for exe in wrf real ndown tc; do test -x "main/$exe.exe"; done
python3 -B brc-cases/check_tracer_registry.py . --generated > "$EVIDENCE/tracer_generated_check.txt"
grep -F "$WRF_SHA" inc/commit_decl > "$EVIDENCE/embedded_commit.txt"
{
    file main/{wrf,real,ndown,tc}.exe
    ls -l --time-style=long-iso main/{wrf,real,ndown,tc}.exe
} > "$EVIDENCE/executable_inventory.txt"
for exe in wrf real; do
    ldd "main/$exe.exe" > "$EVIDENCE/ldd_$exe.txt"
    if grep -q 'not found' "$EVIDENCE/ldd_$exe.txt"; then exit 1; fi
done
# These small manifests pin the actual executables, runtime tables, and configuration.
sha256sum main/{wrf,real,ndown,tc}.exe configure.wrf Registry/Registry.EM > "$EVIDENCE/build_sha256.txt"
find -L run -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum > "$EVIDENCE/runtime_sha256.txt"
git diff --binary HEAD > "$EVIDENCE/post_build_source.diff"
printf 'result=PASS_COMPILE_ONLY\n' >> "$SUMMARY"
