import ctypes
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest
from nest_terrain import parent_terrain, blend_terrain


def test_blend_has_five_parent_rows_and_five_transition_rows():
    fine=np.full((30,34),120.,dtype='f4');parent=np.full_like(fine,60.)
    out,w=blend_terrain(fine,parent)
    np.testing.assert_allclose(w[15,:11],[0,0,0,0,0,1/6,2/6,3/6,4/6,5/6,1])
    np.testing.assert_allclose(out[15,:11],[60,60,60,60,60,70,80,90,100,110,120])
    np.testing.assert_array_equal(out[10:-10,10:-10],fine[10:-10,10:-10])
    np.testing.assert_array_equal(w,w[::-1,::-1])


def test_sint_preserves_constant_and_linear_terrain():
    y,x=np.indices((32,32));a=(100+3*x+6*y).astype('f4')
    cy,cx=np.indices((18,18))
    expected=100+3*(7+(cx-1)/3)+6*(7+(cy-1)/3)
    np.testing.assert_allclose(parent_terrain(a,(18,18),8,8,3),expected,atol=1e-4)
    np.testing.assert_array_equal(parent_terrain(a*0+8,(18,18),8,8,3),8)


def test_sint_matches_the_frozen_wrf_fortran(tmp_path):
    compiler=shutil.which('gfortran')
    if compiler is None:
        pytest.skip('gfortran needed for the independent WRF oracle')
    source=Path(__file__).resolve().parents[1]/'share/sint.F'
    code=source.read_text().split('      SUBROUTINE SINTB(')[0]
    f=tmp_path/'sint.f90';f.write_text(code)
    lib=tmp_path/'sint.so'
    subprocess.run([compiler,'-shared','-fPIC','-O0','-ffree-line-length-none',str(f),'-o',str(lib)],check=True)
    rng=np.random.default_rng(93);parent=rng.uniform(900,2700,(32,32)).astype('f4')
    xf=np.asfortranarray(np.repeat(parent.T[:,:,None],9,axis=2))
    mask=np.ones((32,32),dtype='i4',order='F')
    nums=[ctypes.c_int(v) for v in [1,32,1,32,5,26,5,26,9,0,0]]
    ptr=lambda a:a.ctypes.data_as(ctypes.c_void_p)
    ctypes.CDLL(str(lib)).sint_(ptr(xf),*[ctypes.byref(n) for n in nums[:4]],ptr(mask),
        *[ctypes.byref(n) for n in nums[4:]])
    y,x=np.indices((18,18));expected=xf[7+x//3,7+y//3,x%3+3*(y%3)]
    np.testing.assert_allclose(parent_terrain(parent,(18,18),8,8,3),expected,rtol=0,atol=5e-4)
