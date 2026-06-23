"""
Image preprocessing pipeline.
Applies CLAHE, denoising, sharpening, and gamma correction
to normalize surveillance footage before inference.
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class PreprocessResult:
    image: np.ndarray          # processed BGR image
    original: np.ndarray       # original BGR image
    width: int
    height: int
    applied_steps: list[str]


class ImageEnhancer:
    """
    Multi-stage image enhancement for traffic surveillance frames.
    Each step is opt-in via keyword arguments to `enhance()`.
    """

    def __init__(
        self,
        clahe_clip_limit: float = 2.0,
        clahe_tile_grid: tuple = (8, 8),
        denoise_h: int = 10,
        sharpen_strength: float = 0.5,
    ):
        self._clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=clahe_tile_grid,
        )
        self._denoise_h = denoise_h
        self._sharpen_strength = sharpen_strength

    # ── Public API ────────────────────────────────────────────────────────────

    def enhance(
        self,
        image: np.ndarray,
        *,
        apply_clahe: bool = True,
        apply_denoise: bool = True,
        apply_sharpen: bool = True,
        apply_gamma: bool = True,
        target_size: Optional[tuple[int, int]] = None,
    ) -> PreprocessResult:
        """
        Run the enhancement pipeline on a BGR numpy image.

        Args:
            image: Input BGR numpy array (H, W, 3).
            apply_clahe: Contrast Limited Adaptive Histogram Equalization.
            apply_denoise: Non-local means denoising for noise/rain.
            apply_sharpen: Unsharp masking to reduce motion blur.
            apply_gamma: Auto gamma correction for low-light images.
            target_size: Optional (W, H) to resize output.

        Returns:
            PreprocessResult with enhanced image and metadata.
        """
        original = image.copy()
        out = image.copy()
        steps: list[str] = []

        if apply_gamma:
            out = self._auto_gamma(out)
            steps.append("auto_gamma")

        if apply_clahe:
            out = self._apply_clahe(out)
            steps.append("clahe")

        if apply_denoise:
            out = self._apply_denoise(out)
            steps.append("denoise")

        if apply_sharpen:
            out = self._apply_sharpen(out)
            steps.append("sharpen")

        if target_size:
            out = cv2.resize(out, target_size, interpolation=cv2.INTER_LINEAR)
            steps.append(f"resize_{target_size[0]}x{target_size[1]}")

        h, w = out.shape[:2]
        return PreprocessResult(image=out, original=original, width=w, height=h, applied_steps=steps)

    def load_from_bytes(self, data: bytes) -> np.ndarray:
        """Decode raw bytes (JPEG/PNG) to a BGR numpy array."""
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image — unsupported format or corrupted data.")
        return img

    def load_from_path(self, path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        return img

    # ── Private helpers ───────────────────────────────────────────────────────

    def _auto_gamma(self, image: np.ndarray) -> np.ndarray:
        """Compute gamma from mean brightness and apply LUT correction."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray) / 255.0
        # Darker images → lower gamma (brightens); well-lit → gamma ≈ 1
        gamma = np.log(0.5) / (np.log(mean_brightness + 1e-6))
        gamma = float(np.clip(gamma, 0.4, 2.5))

        lut = np.array(
            [min(255, int((i / 255.0) ** gamma * 255)) for i in range(256)],
            dtype=np.uint8,
        )
        return cv2.LUT(image, lut)

    def _apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """Apply CLAHE on the L channel in LAB color space."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l_clahe = self._clahe.apply(l)
        lab_clahe = cv2.merge([l_clahe, a, b])
        return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

    def _apply_denoise(self, image: np.ndarray) -> np.ndarray:
        """Fast non-local means denoising for noise reduction."""
        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            h=self._denoise_h,
            hColor=self._denoise_h,
            templateWindowSize=7,
            searchWindowSize=21,
        )

    def _apply_sharpen(self, image: np.ndarray) -> np.ndarray:
        """Unsharp masking to recover edges lost to motion blur."""
        blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)
        sharpened = cv2.addWeighted(
            image, 1.0 + self._sharpen_strength,
            blurred, -self._sharpen_strength,
            0,
        )
        return sharpened


# Module-level singleton for import convenience
enhancer = ImageEnhancer()
