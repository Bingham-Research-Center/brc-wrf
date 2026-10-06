# brc-wrf Fork and Porting Policy

## Identity

`brc-wrf` is Bingham Research Center's purpose-built WRF fork. It is based on
WRF `4.8.0`, but is maintained as an independent research code line for the
BRC cases, wrappers, and reproducible CHPC evidence in this repository.

## Freeze Rule

This fork does not automatically follow upstream WRF or other branch lines in
this repository. In particular, do not merge, rebase, or routinely synchronize
`john/*` work from `master`, `main`, or an upstream remote. The current BRC
line remains frozen unless a specific port is intentionally approved.

## Canonical Research Line

The maintained research line is `john/wrf`. Experiment configurations share
that line; immutable experiment/build tags and manifests pin provenance.
See `BRC_WRF_RESEARCH_BUILDS.md` for the build contract and the October 2026
consolidation of existing John branches. This does not authorize upstream
synchronization.

## Selective Port Procedure

When a newer WRF change is needed:

1. State the operational or scientific reason for the port.
2. Identify the exact upstream release, commit, or patch series.
3. Make the port on a `john/port-<topic>` branch; do not import unrelated
   branch history.
4. Record the source identifier, rationale, affected paths, compatibility
   notes, and validation evidence in the port's commit message or linked
   evidence document.
5. Validate the change proportionally before adopting it on the BRC line.

An upstream release upgrade is therefore an explicit BRC change, not a routine
sync operation.
