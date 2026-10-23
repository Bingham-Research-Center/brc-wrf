"""WRF mass-grid SINT interpolation and blend_terrain weights for static packets.

Source: share/sint.F, share/interp_fcn.F:interp_fcn_sint and
dyn_em/nest_init_utils.F:blend_terrain in the frozen WRF 4.8.0 tree.
Arrays use south-to-north rows, as WRF does. No terrain smoothing is applied.
"""
import numpy as np


def _residual(v, a):
    """One dimension of SINT's fourth-order, limited residual advection."""
    m2, m1, z, p1, p2 = v
    def donor(left, right):
        return np.where(a >= 0, left, right) * a
    def tr4(w, x, y, z):
        return (a * np.float32(1/12) * (7 * (y+x) - (z+w))
                - a*a * np.float32(1/24) * (15 * (y-x) - (z-w))
                - a*a*a * np.float32(1/12) * ((y+x) - (z+w))
                + a*a*a*a * np.float32(1/24) * (3 * (y-x) - (z-w)))
    fl0, fl1 = donor(m1, z), donor(z, p1)
    w = z - (fl1 - fl0)
    mx = np.maximum.reduce([m1, z, p1, w])
    mn = np.minimum.reduce([m1, z, p1, w])
    f0, f1 = tr4(m2, m1, z, p1)-fl0, tr4(m1, z, p1, p2)-fl1
    ov = (mx-w) / (-np.minimum(f1, 0)+np.maximum(f0, 0)+np.float32(1e-10))
    un = (w-mn) / (np.maximum(f1, 0)-np.minimum(f0, 0)+np.float32(1e-10))
    f0 = np.maximum(f0, 0)*np.minimum(1, ov)+np.minimum(f0, 0)*np.minimum(1, un)
    f1 = np.maximum(f1, 0)*np.minimum(1, un)+np.minimum(f1, 0)*np.minimum(1, ov)
    return w-(f1-f0)


def parent_terrain(parent, shape, i_parent_start, j_parent_start, ratio):
    """Interpolate a parent HGT onto an odd-ratio, unstaggered child grid."""
    parent = np.asanyarray(parent)
    assert not np.ma.getmaskarray(parent).any() and np.isfinite(parent).all()
    assert ratio >= 3 and ratio % 2 == 1
    yy, xx = np.indices(shape)
    ci, cj = i_parent_start-1+xx//ratio, j_parent_start-1+yy//ratio
    assert ci.min() >= 2 and cj.min() >= 2
    assert ci.max()+2 < parent.shape[1] and cj.max()+2 < parent.shape[0]
    a = np.float32(ratio-1)/np.float32(2*ratio)
    ax = a-(xx % ratio).astype('f4')/np.float32(ratio)
    ay = a-(yy % ratio).astype('f4')/np.float32(ratio)
    parent = np.asarray(parent, dtype='f4')
    rows = [_residual([parent[cj+j, ci+i] for i in range(-2, 3)], ax)
            for j in range(-2, 3)]
    return _residual(rows, ay)


def blend_terrain(fine, parent, spec_bdy_width=5, blend_width=5):
    """Return blended HGT and fine-terrain weights; preserve the interior exactly."""
    fine, parent = np.asanyarray(fine), np.asanyarray(parent)
    assert fine.ndim == 2 and fine.shape == parent.shape
    assert spec_bdy_width > 0 and blend_width >= 0
    assert min(fine.shape) > 2*(spec_bdy_width+blend_width)
    assert not any(np.ma.getmaskarray(v).any() for v in (fine, parent))
    assert all(np.isfinite(v).all() for v in (fine, parent))
    yy, xx = np.indices(fine.shape)
    edge = np.minimum.reduce([xx, yy, fine.shape[1]-1-xx, fine.shape[0]-1-yy])
    weight = np.clip((edge-spec_bdy_width+1)/(blend_width+1), 0, 1).astype('f4')
    out = np.asarray(fine).copy()
    changed = weight < 1
    out[changed] = weight[changed]*fine[changed]+(1-weight[changed])*parent[changed]
    return out, weight
