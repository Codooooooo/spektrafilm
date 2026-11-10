"""Compiled CAM16-UCS transforms for the output gamut compression.

Numerically matches ``colour.XYZ_to_CAM16UCS`` / ``colour.CAM16UCS_to_XYZ`` for
the Average surround, but only computes what the conversion needs (no hue
quadrature, no intermediate correlates) and runs in parallel. Viewing-condition
constants still come from ``colour`` so the two can never drift apart.
"""

from __future__ import annotations

from functools import lru_cache
from math import atan2, copysign, cos, degrees, expm1, fabs, hypot, isfinite, log1p, pi, radians, sin, sqrt

from colour.appearance.ciecam02 import degree_of_adaptation, viewing_conditions_dependent_parameters
from colour.appearance.cam16 import MATRIX_16, MATRIX_INVERSE_16, VIEWING_CONDITIONS_CAM16
from colour.constants import EPSILON
from colour.models.cam02_ucs import COEFFICIENTS_UCS_LUO2006
from numba import njit, prange
import numpy as np

_EPSILON = float(EPSILON)
_NONLINEAR_EXPONENT = 0.42
_NONLINEAR_SCALE = 27.13
_HUNT_T = 50000.0 / 13.0
_CHROMA_EXPONENT = 0.73
_T_EXPONENT = 0.9


@njit(cache=True)
def _spow(value, power):
    if value == 0.0:
        return 0.0
    return copysign(fabs(value) ** power, value)


@njit(cache=True)
def _sdiv(numerator, denominator):
    if denominator == 0.0:
        return 0.0
    quotient = numerator / denominator
    return quotient if isfinite(quotient) else 0.0


@njit(cache=True)
def _compress_response(value, f_l):
    level = _spow(f_l * fabs(value) / 100.0, _NONLINEAR_EXPONENT)
    sign = 0.0 if value == 0.0 else copysign(1.0, value)
    return 400.0 * sign * level / (_NONLINEAR_SCALE + level) + 0.1


@njit(cache=True)
def _expand_response(value, f_l):
    offset = value - 0.1
    sign = 0.0 if offset == 0.0 else copysign(1.0, offset)
    magnitude = fabs(offset)
    return sign * 100.0 / f_l * _spow(_NONLINEAR_SCALE * magnitude / (400.0 - magnitude), 1.0 / _NONLINEAR_EXPONENT)


@njit(parallel=True, cache=True)
def _xyz_to_ucs(xyz, m16, d_rgb, f_l, n, z, n_bb, n_cb, n_c, c, a_w, c_1, c_2):
    count = xyz.shape[0]
    out = np.empty((count, 3), dtype=np.float64)
    chroma_scale = _spow(1.64 - 0.29 ** n, _CHROMA_EXPONENT)
    colourfulness_scale = _spow(f_l, 0.25)
    for index in prange(count):
        x, y, zed = xyz[index, 0] * 100.0, xyz[index, 1] * 100.0, xyz[index, 2] * 100.0
        r = _compress_response(d_rgb[0] * (m16[0, 0] * x + m16[0, 1] * y + m16[0, 2] * zed), f_l)
        g = _compress_response(d_rgb[1] * (m16[1, 0] * x + m16[1, 1] * y + m16[1, 2] * zed), f_l)
        b_a = _compress_response(d_rgb[2] * (m16[2, 0] * x + m16[2, 1] * y + m16[2, 2] * zed), f_l)

        a = r - 12.0 * g / 11.0 + b_a / 11.0
        b = (r + g - 2.0 * b_a) / 9.0
        h = degrees(atan2(b, a)) % 360.0
        e_t = 0.25 * (cos(2.0 + h * pi / 180.0) + 3.8)
        achromatic = (2.0 * r + g + b_a / 20.0 - 0.305) * n_bb
        lightness = 100.0 * _spow(_sdiv(achromatic, a_w), c * z)

        t = _HUNT_T * n_c * n_cb * _sdiv(e_t * _spow(a * a + b * b, 0.5), r + g + 21.0 * b_a / 20.0)
        chroma = _spow(t, _T_EXPONENT) * _spow(lightness / 100.0, 0.5) * chroma_scale
        colourfulness = chroma * colourfulness_scale

        m_p = (1.0 / c_2) * log1p(c_2 * colourfulness)
        hue_radians = radians(h)
        out[index, 0] = ((1.0 + 100.0 * c_1) * lightness) / (1.0 + c_1 * lightness)
        out[index, 1] = m_p * cos(hue_radians)
        out[index, 2] = m_p * sin(hue_radians)
    return out


@njit(parallel=True, cache=True)
def _ucs_to_xyz(jab, inverse_m16, d_rgb, f_l, n, z, n_bb, n_cb, n_c, c, a_w, c_1, c_2):
    count = jab.shape[0]
    out = np.empty((count, 3), dtype=np.float64)
    chroma_scale = _spow(1.64 - 0.29 ** n, _CHROMA_EXPONENT)
    colourfulness_scale = _spow(f_l, 0.25)
    p_3 = 21.0 / 20.0
    for index in prange(count):
        j_p, a_p, b_p = jab[index, 0], jab[index, 1], jab[index, 2]
        lightness = -j_p / (c_1 * j_p - 1.0 - 100.0 * c_1)
        m_p = hypot(a_p, b_p)
        h = degrees(atan2(b_p, a_p)) % 360.0
        colourfulness = expm1(m_p * c_2) / c_2
        chroma = colourfulness / colourfulness_scale

        floored_lightness = max(lightness, _EPSILON)
        t = _spow(chroma / (sqrt(floored_lightness / 100.0) * chroma_scale), 1.0 / _T_EXPONENT)
        e_t = 0.25 * (cos(2.0 + h * pi / 180.0) + 3.8)
        achromatic = a_w * _spow(lightness / 100.0, 1.0 / (c * z))

        p_1 = _sdiv(_HUNT_T * n_c * n_cb * e_t, t)
        p_2 = achromatic / n_bb + 0.305

        hue_radians = radians(h)
        sin_h = sin(hue_radians)
        cos_h = cos(hue_radians)
        a = 0.0
        b = 0.0
        if t != 0.0:
            term = p_2 * (2.0 + p_3) * (460.0 / 1403.0)
            if fabs(sin_h) >= fabs(cos_h):
                cot_h = _sdiv(cos_h, sin_h)
                b = term / (
                    _sdiv(p_1, sin_h)
                    + (2.0 + p_3) * (220.0 / 1403.0) * cot_h
                    - (27.0 / 1403.0)
                    + p_3 * (6300.0 / 1403.0)
                )
                a = b * cot_h
            elif fabs(sin_h) < fabs(cos_h):  # both tests fail for a NaN hue, leaving a = b = 0
                tan_h = _sdiv(sin_h, cos_h)
                a = term / (
                    _sdiv(p_1, cos_h)
                    + (2.0 + p_3) * (220.0 / 1403.0)
                    - ((27.0 / 1403.0) - p_3 * (6300.0 / 1403.0)) * tan_h
                )
                b = a * tan_h

        r = _expand_response((460.0 * p_2 + 451.0 * a + 288.0 * b) / 1403.0, f_l) / d_rgb[0]
        g = _expand_response((460.0 * p_2 - 891.0 * a - 261.0 * b) / 1403.0, f_l) / d_rgb[1]
        b_c = _expand_response((460.0 * p_2 - 220.0 * a - 6300.0 * b) / 1403.0, f_l) / d_rgb[2]
        out[index, 0] = (inverse_m16[0, 0] * r + inverse_m16[0, 1] * g + inverse_m16[0, 2] * b_c) / 100.0
        out[index, 1] = (inverse_m16[1, 0] * r + inverse_m16[1, 1] * g + inverse_m16[1, 2] * b_c) / 100.0
        out[index, 2] = (inverse_m16[2, 0] * r + inverse_m16[2, 1] * g + inverse_m16[2, 2] * b_c) / 100.0
    return out


@lru_cache(maxsize=32)
def _viewing_constants(xyz_w: tuple[float, float, float], l_a: float, y_b: float) -> tuple:
    surround = VIEWING_CONDITIONS_CAM16['Average']
    white = np.asarray(xyz_w, dtype=np.float64) * 100.0
    y_w = white[1]
    rgb_w = MATRIX_16 @ white
    degree = float(np.clip(degree_of_adaptation(surround.F, l_a), 0, 1))
    n, f_l, n_bb, n_cb, z = (float(value) for value in viewing_conditions_dependent_parameters(y_b, y_w, l_a))
    d_rgb = degree * y_w / rgb_w + 1.0 - degree
    rgb_wc = d_rgb * rgb_w
    level = np.sign(rgb_wc) * (f_l * np.abs(rgb_wc) / 100.0) ** _NONLINEAR_EXPONENT
    r_aw, g_aw, b_aw = 400.0 * np.sign(rgb_wc) * np.abs(level) / (_NONLINEAR_SCALE + np.abs(level)) + 0.1
    a_w = float((2.0 * r_aw + g_aw + b_aw / 20.0 - 0.305) * n_bb)
    _k_l, c_1, c_2 = COEFFICIENTS_UCS_LUO2006['CAM02-UCS'].values
    return (
        d_rgb, f_l, n, z, n_bb, n_cb,
        float(surround.N_c), float(surround.c), a_w, float(c_1), float(c_2),
    )


def _as_points(values: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(values, dtype=np.float64).reshape(-1, 3))


def xyz_to_cam16ucs(xyz: np.ndarray, *, xyz_w: np.ndarray, l_a: float, y_b: float) -> np.ndarray:
    """``colour.XYZ_to_CAM16UCS`` for the Average surround."""
    values = np.asarray(xyz, dtype=np.float64)
    constants = _viewing_constants(tuple(float(v) for v in np.asarray(xyz_w)), float(l_a), float(y_b))
    return _xyz_to_ucs(_as_points(values), np.asarray(MATRIX_16, dtype=np.float64), *constants).reshape(values.shape)


def cam16ucs_to_xyz(jab: np.ndarray, *, xyz_w: np.ndarray, l_a: float, y_b: float) -> np.ndarray:
    """``colour.CAM16UCS_to_XYZ`` for the Average surround."""
    values = np.asarray(jab, dtype=np.float64)
    constants = _viewing_constants(tuple(float(v) for v in np.asarray(xyz_w)), float(l_a), float(y_b))
    return _ucs_to_xyz(_as_points(values), np.asarray(MATRIX_INVERSE_16, dtype=np.float64), *constants).reshape(values.shape)


def warmup_fast_cam16ucs() -> None:
    white = np.array([0.95047, 1.0, 1.08883])
    jab = xyz_to_cam16ucs(np.full((2, 2, 3), 0.18), xyz_w=white, l_a=64.0, y_b=20.0)
    cam16ucs_to_xyz(jab, xyz_w=white, l_a=64.0, y_b=20.0)


__all__ = ['cam16ucs_to_xyz', 'warmup_fast_cam16ucs', 'xyz_to_cam16ucs']
