from __future__ import annotations

import colour
import numpy as np
import pytest

from spektrafilm.utils import gamut_compression
from spektrafilm.utils.fast_cam16ucs import cam16ucs_to_xyz, xyz_to_cam16ucs
from spektrafilm.utils.gamut_compression import OutputGamutCompressSpec, compress_rgb

L_A = gamut_compression._CAM16UCS_L_A
Y_B = gamut_compression._CAM16UCS_Y_B
WHITE = gamut_compression._output_cs_whitepoint_xyz('sRGB')


def _reference_forward(xyz, xyz_w, l_a, y_b):
    return np.asarray(colour.XYZ_to_CAM16UCS(xyz, XYZ_w=xyz_w, L_A=l_a, Y_b=y_b))


def _reference_inverse(jab, xyz_w, l_a, y_b):
    return np.asarray(colour.CAM16UCS_to_XYZ(jab, XYZ_w=xyz_w, L_A=l_a, Y_b=y_b))


def test_forward_matches_colour_including_out_of_gamut() -> None:
    xyz = np.random.default_rng(1).uniform(-0.3, 2.0, (20000, 3))
    with np.errstate(all='ignore'):
        expected = _reference_forward(xyz, WHITE, L_A, Y_B)
    np.testing.assert_allclose(xyz_to_cam16ucs(xyz, xyz_w=WHITE, l_a=L_A, y_b=Y_B), expected, atol=1e-9, rtol=0)


def test_inverse_matches_colour_in_gamut() -> None:
    rng = np.random.default_rng(2)
    xyz = np.asarray(colour.RGB_to_XYZ(rng.random((20000, 3)), colourspace='sRGB', apply_cctf_decoding=False))
    jab = _reference_forward(xyz, WHITE, L_A, Y_B)
    np.testing.assert_allclose(cam16ucs_to_xyz(jab, xyz_w=WHITE, l_a=L_A, y_b=Y_B), _reference_inverse(jab, WHITE, L_A, Y_B), atol=1e-9, rtol=0)


@pytest.mark.parametrize(
    'jab',
    [
        [0.0, 30.0, 10.0],  # lightness floor
        [-1.0, 20.0, 10.0],  # negative lightness
        [8.0, np.nan, np.nan],  # undefined hue collapses to achromatic
    ],
)
def test_inverse_matches_colour_on_edge_branches(jab) -> None:
    # colour rejects input that is entirely NaN, so keep one ordinary row alongside.
    values = np.array([jab, [50.0, 40.0, 10.0]], dtype=float)
    with np.errstate(all='ignore'):
        expected = _reference_inverse(values, WHITE, L_A, Y_B)
    np.testing.assert_allclose(cam16ucs_to_xyz(values, xyz_w=WHITE, l_a=L_A, y_b=Y_B), expected, atol=1e-9, rtol=0)


def test_compression_is_unchanged_on_saturated_colors(monkeypatch) -> None:
    rng = np.random.default_rng(3)
    size = (150, 200)
    rgb = np.stack([rng.uniform(-0.2, 1.4, size), rng.uniform(-0.2, 0.1, size), rng.uniform(-0.2, 0.1, size)], axis=-1)
    spec = OutputGamutCompressSpec(algorithm='cam16ucs')
    fast = compress_rgb(rgb, spec, output_color_space='sRGB')

    monkeypatch.setattr(gamut_compression, 'xyz_to_cam16ucs', lambda xyz, xyz_w, l_a, y_b: _reference_forward(xyz, xyz_w, l_a, y_b))
    monkeypatch.setattr(gamut_compression, 'cam16ucs_to_xyz', lambda jab, xyz_w, l_a, y_b: _reference_inverse(jab, xyz_w, l_a, y_b))
    with np.errstate(all='ignore'):
        reference = compress_rgb(rgb, spec, output_color_space='sRGB')

    np.testing.assert_allclose(np.clip(fast, 0, 1), np.clip(reference, 0, 1), atol=1e-6, rtol=0)
