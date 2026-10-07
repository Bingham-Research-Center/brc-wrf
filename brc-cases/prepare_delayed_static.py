#!/usr/bin/env python3
"""Build a static-only WRF nest input on unused input stream 6, on Slurm.

This prepares an input packet; actual delayed activation and parent-state
inheritance remain model acceptance tests. It never edits the source input.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np
from netCDF4 import Dataset, chartostring

STREAM = 6
# Spatial geometry and land/soil categories only. In particular, exclude
# atmosphere, tracers, soil water/temperature, SST/TSK, snow and sea ice.
REQUIRED = set('HGT LU_INDEX LANDMASK XLAND IVGTYP ISLTYP XLAT XLONG '
               'MAPFAC_M MAPFAC_U MAPFAC_V SINALPHA COSALPHA'.split())
STATIC = REQUIRED | set('XLAT_U XLAT_V XLONG_U XLONG_V LAKEMASK LANDUSEF '
    'SOILCTOP SOILCBOT MAPFAC_MX MAPFAC_MY MAPFAC_UX MAPFAC_UY MAPFAC_VX '
    'MAPFAC_VY MF_VX_INV CLAT F VAR_SSO SHDMAX SHDMIN SNOALB FRC_URB2D '
    'IMPERV CANFRA IRRIGATION LAKE_DEPTH'.split())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def registry_inventory(root):
    """Conservatively include conditional branches when checking stream 6.

    Follow only the actual Registry include graph. The released build includes
    its generated io_boilerplate_temporary.inc; a source-only tree is incomplete.
    """
    root = Path(root).resolve()
    seen, names, members = {}, set(), set()

    def walk(path):
        path = path.resolve()
        assert path.is_relative_to(root), 'Registry include escaped its root'
        key = str(path.relative_to(root))
        if key in seen:
            return
        seen[key] = sha(path)
        for line in path.read_text().replace('\\\n', ' ').splitlines():
            cols = line.split()
            if not cols or cols[0].startswith('#'):
                continue
            if cols[0] == 'include':
                walk(root / cols[1])
            if cols[0] != 'state' or len(cols) < 9:
                continue
            name = re.search(r'"([^"]+)"', line)
            if not name:
                continue
            name = name[1].upper()
            names.add(name)
            flag = re.search(r'i((?:\{\d+\}|\d)*)', cols[7])
            if flag:
                streams = {int(n.strip('{}')) for n in
                           re.findall(r'\{\d+\}|\d', flag[1])} or {0}
                if STREAM in streams:
                    members.add(name)
    walk(root / 'Registry')
    assert not members, f'input stream {STREAM} already has fields: {sorted(members)}'
    return {'files': seen, 'names': names, 'default_members': sorted(members)}


def prepare(source, output, registry, activation, base_iofields):
    activation = datetime.strptime(activation, '%Y-%m-%d_%H:%M:%S').strftime('%Y-%m-%d_%H:%M:%S')
    source, output = Path(source), Path(output)
    assert source.resolve() != output.resolve()
    assert not output.exists(), f'refusing to replace {output}'
    assert not output.with_suffix('.iofields.txt').exists()
    assert not output.with_suffix('.provenance.json').exists()
    inventory = registry_inventory(registry)
    before = sha(source)
    base = Path(base_iofields).read_text()
    for line in base.splitlines():
        if line.strip() and '#' not in line:
            assert re.fullmatch(r'[+-]:h:\d+:[A-Za-z0-9_,]+', line.strip()), 'base iofields must contain history rules only'
    with Dataset(source) as src:
        assert len(src.dimensions['Time']) == 1
        old_times = list(map(str, chartostring(src['Times'][:])))
        assert len(src.dimensions['west_east']) > 1
        assert int(src.getncattr('GRID_ID')) == 3, 'expected a real.exe d03 input'
        names = {n.upper(): n for n in src.variables}
        assert REQUIRED <= names.keys(), f'missing static fields: {sorted(REQUIRED - names.keys())}'
        chosen = sorted(STATIC & names.keys())
        assert set(chosen) <= inventory['names'], 'static field absent from compiled Registry'
        for upper in chosen:
            assert np.isfinite(src[names[upper]][:]).all(), f'nonfinite static field {upper}'
        with Dataset(output, 'w', format=src.data_model) as out:
            # Keep dimensions and global provenance, including simulation start;
            # only this run-local static frame's Times/START_DATE are retimed.
            for name, dim in src.dimensions.items():
                out.createDimension(name, None if dim.isunlimited() else len(dim))
            out.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
            out.setncattr('START_DATE', activation)
            out.setncattr('BRC_STATIC_INPUT_SOURCE_SHA256', before)
            out.setncattr('BRC_STATIC_INPUT_STREAM', STREAM)
            for name in ['Times'] + [names[n] for n in chosen]:
                v = src[name]
                fill = {'fill_value': v.getncattr('_FillValue')} if '_FillValue' in v.ncattrs() else {}
                target = out.createVariable(name, v.dtype, v.dimensions, **fill)
                target.setncatts({k: v.getncattr(k) for k in v.ncattrs() if k != '_FillValue'})
                target[:] = np.asarray(list(activation), dtype='S1')[None, :] if name == 'Times' else v[:]
    assert sha(source) == before, 'source changed during preparation'
    with Dataset(output) as check:
        assert list(map(str, chartostring(check['Times'][:]))) == [activation]
        assert {n.upper() for n in check.variables} == set(chosen) | {'TIMES'}
    masks = output.with_suffix('.iofields.txt')
    # WRF stops reading iofields at a blank line; remove blanks from the copy.
    masks.write_text('\n'.join(line for line in base.splitlines() if line.strip()) +
        f'\n# d03 static-only initialization on otherwise empty input stream {STREAM}.\n' +
        f'+:i:{STREAM}:' + ','.join(chosen) + '\n')
    inventory.pop('names')
    result = {'source': str(source.resolve()), 'source_sha256': before,
        'source_times': old_times, 'activation': activation, 'input_stream': STREAM,
        'output': str(output.resolve()), 'output_sha256': sha(output),
        'iofields': str(masks.resolve()), 'iofields_sha256': sha(masks),
        'static_fields': chosen, 'registry': inventory,
        'namelist_required': {'fine_input_stream': [0, 0, STREAM],
            'io_form_auxinput2': 2, 'io_form_auxinput6': 2,
            'ignore_iofields_warning': False},
        'accepted_for_model_launch': False,
        'remaining': 'Review three-domain namelist and initial file geometry; verify actual delayed activation, inherited tracers and surface state.'}
    output.with_suffix('.provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--activation', required=True)
    p.add_argument('--base-iofields', type=Path, required=True)
    a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'), 'NetCDF copying and hashing belong on Slurm'
    print(json.dumps(prepare(a.source, a.output, a.registry, a.activation, a.base_iofields), indent=2))


if __name__ == '__main__':
    main()
