#!/usr/bin/env python3
"""m1_ssim.py -- M1 milestone checker for the Raptor A/B benchmark.

M1 (per the pre-registered scoring spec, section 2D):
    level-1 background + player ship rendered on canvas from the real GLB
    data: screenshot similarity (SSIM) to a DOSBox reference frame >= 0.80
    on the playfield region, AND >= 90% of the reference palette present.

This script takes a model screenshot PNG and a DOSBox reference PNG,
crops both to an identical caller-supplied pixel box (the crop coords are
not known ahead of time, so they are a required CLI argument rather than
hardcoded), and reports:

  1. SSIM between the two crops (grayscale luminance).
  2. Palette coverage: what fraction of the distinct colors present in the
     reference crop also appear (within a small Euclidean-distance
     tolerance) somewhere in the model crop.

SSIM implementation:
    Tries `skimage.metrics.structural_similarity` first. If scikit-image
    is not installed, falls back to a pure-numpy windowed SSIM
    implementation using a uniform (box) window instead of the usual
    Gaussian window -- this fallback is an APPROXIMATION of the standard
    SSIM algorithm (box filter vs. Gaussian-weighted filter changes the
    result slightly, typically by a few hundredths), not a bit-exact
    match to skimage's output. Prefer having scikit-image installed for
    the authoritative score; the fallback exists purely so this script
    still runs (and still produces a directionally-correct score) in an
    environment without scikit-image.

Output:
    Prints exactly one JSON line to stdout:
        {"ssim": <float>, "palette_coverage": <float>,
         "pass_ssim": <bool>, "pass_palette": <bool>, "pass_m1": <bool>}
    pass_ssim    := ssim >= --ssim-threshold (default 0.80)
    pass_palette := palette_coverage >= --palette-threshold (default 0.90)
    pass_m1      := pass_ssim and pass_palette

    Diagnostic info (which SSIM implementation was used, crop sizes, etc.)
    is written to stderr, never to stdout, so stdout stays a single clean
    JSON line safe for a caller to `json.loads()`.

Usage:
    python m1_ssim.py --model-png model.png --ref-png ref.png \
        --crop 0,0,320,200
    python m1_ssim.py --model-png model.png --ref-png ref.png \
        --crop 40,20,240,160 --palette-tolerance 10
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is a hard dependency here
    print(
        "ERROR: Pillow (PIL) is required to load PNGs. Install with "
        "`pip install pillow`.",
        file=sys.stderr,
    )
    raise

try:
    from skimage.metrics import structural_similarity as _sk_ssim

    _HAVE_SKIMAGE = True
except ImportError:
    _HAVE_SKIMAGE = False


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M1 checker: SSIM + palette-coverage between a model "
        "screenshot and a DOSBox reference frame, over an identical crop "
        "box applied to both images."
    )
    parser.add_argument(
        "--model-png", required=True, help="Path to the model's canvas screenshot PNG."
    )
    parser.add_argument(
        "--ref-png", required=True, help="Path to the DOSBox reference PNG."
    )
    parser.add_argument(
        "--crop",
        required=True,
        help="Crop box 'x,y,w,h' in pixel coords, applied identically to "
        "both images before comparing (e.g. 0,0,320,200).",
    )
    parser.add_argument(
        "--palette-tolerance",
        type=float,
        default=8.0,
        help="Max Euclidean RGB distance for a model-crop color to count "
        "as matching a reference-crop color (default: 8).",
    )
    parser.add_argument(
        "--quant-step",
        type=float,
        default=8.0,
        help="Bucket size used to quantize RGB colors (via rounding) "
        "before computing the distinct-color sets for palette coverage "
        "(default: 8).",
    )
    parser.add_argument(
        "--ssim-threshold",
        type=float,
        default=0.80,
        help="Minimum SSIM to pass M1's similarity criterion (default: 0.80).",
    )
    parser.add_argument(
        "--palette-threshold",
        type=float,
        default=0.90,
        help="Minimum palette coverage fraction to pass M1's palette "
        "criterion (default: 0.90).",
    )
    return parser.parse_args(argv)


def parse_crop(crop_str: str) -> tuple[int, int, int, int]:
    parts = crop_str.split(",")
    if len(parts) != 4:
        print(
            f"ERROR: --crop must be 'x,y,w,h', got: {crop_str!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError:
        print(
            f"ERROR: --crop values must be integers, got: {crop_str!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    if w <= 0 or h <= 0:
        print(
            f"ERROR: --crop width/height must be positive, got w={w}, h={h}",
            file=sys.stderr,
        )
        sys.exit(2)
    return x, y, w, h


# --------------------------------------------------------------------------
# Image loading / cropping
# --------------------------------------------------------------------------

def load_and_crop(path: str, x: int, y: int, w: int, h: int, label: str) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    width, height = img.size
    if x < 0 or y < 0 or x + w > width or y + h > height:
        print(
            f"ERROR: crop box (x={x}, y={y}, w={w}, h={h}) is out of "
            f"bounds for {label} image {path!r} (size {width}x{height}).",
            file=sys.stderr,
        )
        sys.exit(2)
    cropped = img.crop((x, y, x + w, y + h))
    return np.asarray(cropped, dtype=np.uint8)


def to_gray(rgb: np.ndarray) -> np.ndarray:
    """Standard luminosity-weighted grayscale conversion."""
    r = rgb[..., 0].astype(np.float64)
    g = rgb[..., 1].astype(np.float64)
    b = rgb[..., 2].astype(np.float64)
    return 0.299 * r + 0.587 * g + 0.114 * b


# --------------------------------------------------------------------------
# SSIM
# --------------------------------------------------------------------------

def _box_filter(img: np.ndarray, k: int) -> np.ndarray:
    """Mean filter with a k x k box (k odd), 'same'-size output, using
    reflect padding at the edges. Implemented via an integral image so it
    stays O(H*W) with pure numpy (no scipy dependency)."""
    if k % 2 == 0:
        k += 1
    pad = k // 2
    padded = np.pad(img, ((pad, pad), (pad, pad)), mode="reflect")
    h, w = img.shape
    ii = np.zeros((padded.shape[0] + 1, padded.shape[1] + 1), dtype=np.float64)
    ii[1:, 1:] = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    total = (
        ii[k : k + h, k : k + w]
        - ii[0:h, k : k + w]
        - ii[k : k + h, 0:w]
        + ii[0:h, 0:w]
    )
    return total / (k * k)


def _ssim_numpy_fallback(ref: np.ndarray, model: np.ndarray, win: int = 7) -> float:
    """Pure-numpy approximate SSIM using a uniform (box) window instead of
    the Gaussian window the reference SSIM algorithm uses. See module
    docstring for caveats -- this is documented as an approximation."""
    x = ref.astype(np.float64)
    y = model.astype(np.float64)

    data_range = 255.0
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2

    mu_x = _box_filter(x, win)
    mu_y = _box_filter(y, win)
    mu_x2 = mu_x * mu_x
    mu_y2 = mu_y * mu_y
    mu_xy = mu_x * mu_y

    sigma_x2 = _box_filter(x * x, win) - mu_x2
    sigma_y2 = _box_filter(y * y, win) - mu_y2
    sigma_xy = _box_filter(x * y, win) - mu_xy

    numerator = (2 * mu_xy + c1) * (2 * sigma_xy + c2)
    denominator = (mu_x2 + mu_y2 + c1) * (sigma_x2 + sigma_y2 + c2)
    ssim_map = numerator / denominator

    return float(np.mean(ssim_map))


def compute_ssim(ref_gray: np.ndarray, model_gray: np.ndarray) -> tuple[float, str]:
    if _HAVE_SKIMAGE:
        win_size = min(7, ref_gray.shape[0], ref_gray.shape[1])
        if win_size % 2 == 0:
            win_size -= 1
        win_size = max(win_size, 3)
        score = _sk_ssim(
            ref_gray, model_gray, data_range=255, win_size=win_size
        )
        return float(score), "skimage"
    return _ssim_numpy_fallback(ref_gray, model_gray), "numpy_fallback"


# --------------------------------------------------------------------------
# Palette coverage
# --------------------------------------------------------------------------

def unique_quantized_colors(rgb: np.ndarray, quant_step: float) -> np.ndarray:
    """Round RGB pixels to the nearest `quant_step` bucket and return the
    set of distinct resulting colors, shape (n, 3)."""
    flat = rgb.reshape(-1, 3).astype(np.float64)
    quantized = np.round(flat / quant_step) * quant_step
    quantized = np.clip(quantized, 0, 255)
    return np.unique(quantized, axis=0)


def palette_coverage(
    ref_crop: np.ndarray,
    model_crop: np.ndarray,
    tolerance: float,
    quant_step: float,
) -> float:
    """Fraction of distinct (quantized) reference-crop colors that have a
    match within Euclidean distance <= tolerance somewhere in the
    (quantized) model-crop colors."""
    ref_colors = unique_quantized_colors(ref_crop, quant_step)
    model_colors = unique_quantized_colors(model_crop, quant_step)

    if ref_colors.shape[0] == 0:
        return 1.0
    if model_colors.shape[0] == 0:
        return 0.0

    covered = 0
    chunk_size = 256
    for start in range(0, ref_colors.shape[0], chunk_size):
        ref_chunk = ref_colors[start : start + chunk_size]  # (c, 3)
        diff = ref_chunk[:, None, :] - model_colors[None, :, :]  # (c, m, 3)
        dist = np.sqrt(np.sum(diff * diff, axis=2))  # (c, m)
        min_dist = dist.min(axis=1)
        covered += int(np.sum(min_dist <= tolerance))

    return covered / ref_colors.shape[0]


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    args = parse_args(argv)
    x, y, w, h = parse_crop(args.crop)

    ref_crop = load_and_crop(args.ref_png, x, y, w, h, "reference")
    model_crop = load_and_crop(args.model_png, x, y, w, h, "model")

    ref_gray = to_gray(ref_crop)
    model_gray = to_gray(model_crop)

    ssim_score, ssim_method = compute_ssim(ref_gray, model_gray)
    coverage = palette_coverage(
        ref_crop, model_crop, args.palette_tolerance, args.quant_step
    )

    print(
        f"[m1_ssim] crop=({x},{y},{w},{h}) ssim_method={ssim_method} "
        f"ref_distinct_colors={unique_quantized_colors(ref_crop, args.quant_step).shape[0]} "
        f"model_distinct_colors={unique_quantized_colors(model_crop, args.quant_step).shape[0]}",
        file=sys.stderr,
    )

    result = {
        "ssim": round(float(ssim_score), 4),
        "palette_coverage": round(float(coverage), 4),
    }
    result["pass_ssim"] = bool(result["ssim"] >= args.ssim_threshold)
    result["pass_palette"] = bool(result["palette_coverage"] >= args.palette_threshold)
    result["pass_m1"] = bool(result["pass_ssim"] and result["pass_palette"])

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
