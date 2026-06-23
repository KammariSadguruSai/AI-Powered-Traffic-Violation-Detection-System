"""
Rule-based violation detection engine.
Each rule receives a DetectorResult and returns zero or more ViolationResult objects.
All geometry is in absolute pixel coordinates.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

import numpy as np

from app.config import ViolationType, settings
from app.core.detection.detector import Detection, DetectorResult

logger = logging.getLogger(__name__)


@dataclass
class ViolationResult:
    violation_type: str
    confidence:     float
    bbox:           Optional[Dict[str, float]] = None   # {x1,y1,x2,y2}
    vehicle_type:   Optional[str] = None
    description:    str = ""
    related_objects: List[Detection] = field(default_factory=list)

    @property
    def bbox_dict(self):
        return self.bbox or {}


# ── Helper utilities ──────────────────────────────────────────────────────────

def _bbox_dict(d: Detection) -> Dict[str, float]:
    return {"x1": d.x1, "y1": d.y1, "x2": d.x2, "y2": d.y2}


def _persons_on_vehicle(vehicle: Detection, persons: List[Detection]) -> List[Detection]:
    """Return persons whose centre-point lies within the vehicle bounding box."""
    riders: List[Detection] = []
    for p in persons:
        cx, cy = p.center
        if vehicle.x1 <= cx <= vehicle.x2 and vehicle.y1 <= cy <= vehicle.y2:
            riders.append(p)
    return riders


def _iou_overlap(a: Detection, b: Detection, threshold: float = 0.15) -> bool:
    return a.iou(b) >= threshold


# ── Violation Rule Classes ────────────────────────────────────────────────────

class HelmetViolationRule:
    """
    Detect riders on motorcycles without helmets.

    Heuristic:
    - A rider's head region (top ~25% of person bbox) is examined.
    - If the head sub-region is relatively bright/skin-toned and no
      dark helmet-like blob is detected, a violation is flagged.
    - Confidence is proportional to clarity of the head region.

    Note: A production system would use a dedicated helmet classifier trained
    on Indian traffic images. This heuristic gives reasonable results on clear images.
    """

    MIN_CONFIDENCE = settings.HELMET_CONFIDENCE_MIN

    def check(
        self,
        image: np.ndarray,
        result: DetectorResult,
    ) -> List[ViolationResult]:
        violations: List[ViolationResult] = []
        for moto in result.motorcycles:
            riders = _persons_on_vehicle(moto, result.persons)
            for rider in riders:
                conf = self._head_region_no_helmet(image, rider)
                if conf >= self.MIN_CONFIDENCE:
                    violations.append(ViolationResult(
                        violation_type=ViolationType.HELMET_VIOLATION,
                        confidence=conf,
                        bbox=_bbox_dict(rider),
                        vehicle_type="motorcycle",
                        description="Rider detected without helmet",
                        related_objects=[moto, rider],
                    ))
        return violations

    def _head_region_no_helmet(self, image: np.ndarray, person: Detection) -> float:
        """Analyse head region. Returns confidence that NO helmet is present."""
        h, w = image.shape[:2]
        x1 = int(max(0, person.x1))
        y1 = int(max(0, person.y1))
        x2 = int(min(w, person.x2))
        y2 = int(min(h, person.y2))

        if x2 <= x1 or y2 <= y1:
            return 0.0

        person_h = y2 - y1
        head_y2  = y1 + int(person_h * 0.28)   # top 28% = head
        head_roi = image[y1:head_y2, x1:x2]

        if head_roi.size == 0:
            return 0.0

        # Convert to HSV and check for dark regions (helmet) in head area
        import cv2
        hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
        dark_mask = (hsv[:, :, 2] < 80)         # Value < 80 → dark object
        dark_ratio = dark_mask.sum() / dark_mask.size

        # High dark ratio in head → helmet present → low violation confidence
        # Low dark ratio → no helmet → high violation confidence
        no_helmet_conf = float(np.clip(0.95 - dark_ratio * 1.5, 0.0, 0.95))
        # Scale by person detection confidence
        return no_helmet_conf * person.confidence


class TripleRidingRule:
    """Flag motorcycle with 3 or more persons overlapping its bbox."""

    MIN_PERSONS = settings.TRIPLE_RIDING_MIN_PERSONS

    def check(self, result: DetectorResult) -> List[ViolationResult]:
        violations: List[ViolationResult] = []
        for moto in result.motorcycles:
            riders = _persons_on_vehicle(moto, result.persons)
            if len(riders) >= self.MIN_PERSONS:
                conf = min(0.95, 0.70 + (len(riders) - self.MIN_PERSONS) * 0.1)
                violations.append(ViolationResult(
                    violation_type=ViolationType.TRIPLE_RIDING,
                    confidence=conf,
                    bbox=_bbox_dict(moto),
                    vehicle_type="motorcycle",
                    description=f"{len(riders)} persons detected on motorcycle",
                    related_objects=[moto, *riders],
                ))
        return violations


class StopLineViolationRule:
    """
    Detect vehicles that cross a defined stop line.

    stop_line_y: Y-pixel coordinate of the stop line in the image.
    direction: "down" if vehicles move top-to-bottom, "up" otherwise.
    """

    def __init__(
        self,
        stop_line_y: Optional[int] = None,
        direction: str = "down",
        margin: int = settings.STOP_LINE_MARGIN_PX,
    ):
        self.stop_line_y = stop_line_y
        self.direction   = direction
        self.margin      = margin

    def check(self, result: DetectorResult) -> List[ViolationResult]:
        if self.stop_line_y is None:
            return []
        violations: List[ViolationResult] = []
        for v in result.vehicles:
            crossed = (
                v.y2 > self.stop_line_y + self.margin
                if self.direction == "down"
                else v.y1 < self.stop_line_y - self.margin
            )
            if crossed:
                violations.append(ViolationResult(
                    violation_type=ViolationType.STOP_LINE_VIOLATION,
                    confidence=min(0.92, v.confidence * 0.95),
                    bbox=_bbox_dict(v),
                    vehicle_type=v.class_name,
                    description="Vehicle crossed stop line",
                    related_objects=[v],
                ))
        return violations


class WrongSideDrivingRule:
    """
    Detect wrong-side driving using movement direction across a road centre line.

    road_center_x: X-pixel coordinate splitting road into two lanes.
    expected_direction_left: Direction vehicles on the LEFT lane should move.
        "down" = top-to-bottom (standard left-hand traffic).
    Tracked vehicles are compared frame-to-frame via track history.
    """

    def __init__(self, road_center_x: Optional[int] = None):
        self.road_center_x = road_center_x
        self._track_history: Dict[int, List[Tuple[float, float]]] = {}

    def update(self, result: DetectorResult) -> List[ViolationResult]:
        if self.road_center_x is None:
            return []
        violations: List[ViolationResult] = []

        for v in result.vehicles:
            if v.track_id is None:
                continue
            cx, cy = v.center
            history = self._track_history.setdefault(v.track_id, [])
            history.append((cx, cy))
            if len(history) > 10:
                history.pop(0)

            if len(history) < 4:
                continue

            dy = history[-1][1] - history[0][1]  # positive = moving downward
            is_left_lane = cx < self.road_center_x

            # Left-hand traffic: left lane should move downward (dy > 0)
            # Right-hand traffic: left lane should move upward (dy < 0)
            wrong_way = (is_left_lane and dy < -10) or (not is_left_lane and dy > 10)

            if wrong_way:
                speed_factor = abs(dy) / 10
                conf = min(0.90, 0.65 + speed_factor * 0.05)
                violations.append(ViolationResult(
                    violation_type=ViolationType.WRONG_SIDE_DRIVING,
                    confidence=conf,
                    bbox=_bbox_dict(v),
                    vehicle_type=v.class_name,
                    description="Vehicle moving in wrong direction",
                    related_objects=[v],
                ))

        return violations


class IllegalParkingRule:
    """
    Flag vehicles stationary in a no-parking zone for N consecutive frames.
    Requires tracking IDs. parking_zones is a list of (x1, y1, x2, y2) tuples.
    """

    def __init__(
        self,
        parking_zones: Optional[List[Tuple[int, int, int, int]]] = None,
        stationary_threshold: int = settings.PARKING_STATIONARY_FRAMES,
    ):
        self.parking_zones = parking_zones or []
        self.threshold     = stationary_threshold
        self._stationary_counts: Dict[int, int] = {}
        self._last_positions: Dict[int, Tuple[float, float]] = {}

    def update(self, result: DetectorResult) -> List[ViolationResult]:
        if not self.parking_zones:
            return []
        violations: List[ViolationResult] = []

        for v in result.vehicles:
            if v.track_id is None:
                continue
            cx, cy = v.center

            if not self._in_no_parking_zone(cx, cy):
                self._stationary_counts.pop(v.track_id, None)
                continue

            last = self._last_positions.get(v.track_id)
            moved = last and (abs(cx - last[0]) + abs(cy - last[1])) > 5

            if moved:
                self._stationary_counts[v.track_id] = 0
            else:
                self._stationary_counts[v.track_id] = (
                    self._stationary_counts.get(v.track_id, 0) + 1
                )

            self._last_positions[v.track_id] = (cx, cy)

            if self._stationary_counts[v.track_id] >= self.threshold:
                conf = min(0.95, 0.7 + self._stationary_counts[v.track_id] / 100)
                violations.append(ViolationResult(
                    violation_type=ViolationType.ILLEGAL_PARKING,
                    confidence=conf,
                    bbox=_bbox_dict(v),
                    vehicle_type=v.class_name,
                    description=f"Vehicle parked illegally for {self._stationary_counts[v.track_id]} frames",
                    related_objects=[v],
                ))

        return violations

    def _in_no_parking_zone(self, cx: float, cy: float) -> bool:
        for zx1, zy1, zx2, zy2 in self.parking_zones:
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                return True
        return False


# ── Seatbelt Violation Rule ────────────────────────────────────────────────────

class SeatbeltViolationRule:
    """
    Detect drivers/passengers in cars not wearing seatbelts.

    Heuristic:
    - For each person detected inside a car bbox, examine the upper-torso region
      (roughly 25-55% height of the person bbox).
    - A seatbelt typically appears as a dark diagonal band across the torso.
    - If no such diagonal edge pattern is found, flag as violation.
    """

    MIN_CONFIDENCE = settings.HELMET_CONFIDENCE_MIN  # reuse threshold

    # COCO class IDs for cars
    CAR_CLASS_IDS = {2, 5, 7}  # car, bus, truck

    def check(
        self,
        image: np.ndarray,
        result: DetectorResult,
    ) -> List[ViolationResult]:
        violations: List[ViolationResult] = []
        cars = [d for d in result.detections if d.class_id in self.CAR_CLASS_IDS]

        for car in cars:
            occupants = _persons_on_vehicle(car, result.persons)
            for person in occupants:
                conf = self._check_no_seatbelt(image, person)
                if conf >= self.MIN_CONFIDENCE:
                    violations.append(ViolationResult(
                        violation_type=ViolationType.SEATBELT_VIOLATION,
                        confidence=conf,
                        bbox=_bbox_dict(person),
                        vehicle_type=car.class_name,
                        description="Occupant detected without seatbelt",
                        related_objects=[car, person],
                    ))
        return violations

    def _check_no_seatbelt(self, image: np.ndarray, person: Detection) -> float:
        """Analyze torso region for diagonal seatbelt strap. Returns no-seatbelt confidence."""
        import cv2

        h, w = image.shape[:2]
        x1 = int(max(0, person.x1))
        y1 = int(max(0, person.y1))
        x2 = int(min(w, person.x2))
        y2 = int(min(h, person.y2))

        if x2 <= x1 or y2 <= y1:
            return 0.0

        person_h = y2 - y1
        # Torso region: 25% to 55% of person height
        torso_y1 = y1 + int(person_h * 0.25)
        torso_y2 = y1 + int(person_h * 0.55)
        torso_roi = image[torso_y1:torso_y2, x1:x2]

        if torso_roi.size == 0:
            return 0.0

        # Convert to grayscale and detect diagonal edges (seatbelt strap)
        gray = cv2.cvtColor(torso_roi, cv2.COLOR_BGR2GRAY)

        # Use Canny + diagonal Hough lines to detect strap
        edges = cv2.Canny(gray, 50, 150)

        # Check for diagonal lines (30-60 degrees from horizontal)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=15,
                                minLineLength=int(min(torso_roi.shape[:2]) * 0.3),
                                maxLineGap=10)

        has_diagonal = False
        if lines is not None:
            for line in lines:
                lx1, ly1, lx2, ly2 = line[0]
                dx = abs(lx2 - lx1)
                dy = abs(ly2 - ly1)
                if dx > 0:
                    angle = np.degrees(np.arctan(dy / dx))
                    # Seatbelt straps are typically 20-70 degrees
                    if 20 <= angle <= 70:
                        has_diagonal = True
                        break

        # Also check for dark band (seatbelt is usually dark on clothing)
        hsv = cv2.cvtColor(torso_roi, cv2.COLOR_BGR2HSV)
        dark_mask = (hsv[:, :, 2] < 60)
        dark_ratio = dark_mask.sum() / max(dark_mask.size, 1)

        # Has diagonal dark band → seatbelt present → low violation conf
        if has_diagonal and dark_ratio > 0.05:
            return 0.0  # seatbelt detected

        # No seatbelt pattern found
        no_belt_conf = float(np.clip(0.85 - (dark_ratio * 2.0), 0.0, 0.90))
        return no_belt_conf * person.confidence


# ── Red Light Violation Rule ──────────────────────────────────────────────────

class RedLightViolationRule:
    """
    Detect vehicles crossing the stop line while the traffic light is red.

    Approach:
    - Scan the upper portion of the image for red circular blobs (traffic lights).
    - If a red signal is detected, check if any vehicle's bottom edge has
      crossed the stop_line_y.
    - Requires stop_line_y to be configured.
    """

    def __init__(self, stop_line_y: Optional[int] = None):
        self.stop_line_y = stop_line_y
        self._red_detected = False

    def check(
        self,
        image: np.ndarray,
        result: DetectorResult,
    ) -> List[ViolationResult]:
        if self.stop_line_y is None:
            return []

        violations: List[ViolationResult] = []

        # Detect red traffic light in upper 40% of image
        self._red_detected = self._detect_red_light(image)

        if not self._red_detected:
            return violations

        # Check vehicles crossing stop line while red
        for v in result.vehicles:
            if v.y2 > self.stop_line_y + 15:  # crossed stop line
                conf = min(0.92, v.confidence * 0.90)
                violations.append(ViolationResult(
                    violation_type=ViolationType.RED_LIGHT_VIOLATION,
                    confidence=conf,
                    bbox=_bbox_dict(v),
                    vehicle_type=v.class_name,
                    description="Vehicle crossed stop line during red signal",
                    related_objects=[v],
                ))

        return violations

    def _detect_red_light(self, image: np.ndarray) -> bool:
        """Detect red traffic light in the upper portion of the image."""
        import cv2

        h, w = image.shape[:2]
        # Only scan top 40% of image for traffic lights
        upper_region = image[0:int(h * 0.4), :]

        if upper_region.size == 0:
            return False

        hsv = cv2.cvtColor(upper_region, cv2.COLOR_BGR2HSV)

        # Red in HSV has two ranges (wraps around 0/180)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 | mask2

        # Look for circular red blobs (traffic lights are round)
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 50:  # too small
                continue
            # Check circularity
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity > 0.5:  # reasonably circular
                return True

        # Fallback: check if significant red area exists
        red_ratio = red_mask.sum() / (red_mask.size * 255)
        return red_ratio > 0.002


# ── Violation Engine — combines all rules ─────────────────────────────────────

class ViolationEngine:
    """
    Runs all enabled violation rules against a DetectorResult.
    Stateful rules (tracking) are maintained per engine instance.
    """

    def __init__(
        self,
        stop_line_y: Optional[int] = None,
        road_center_x: Optional[int] = None,
        parking_zones: Optional[List[Tuple[int, int, int, int]]] = None,
    ):
        self._helmet_rule    = HelmetViolationRule()
        self._triple_rule    = TripleRidingRule()
        self._stop_rule      = StopLineViolationRule(stop_line_y=stop_line_y)
        self._wrong_rule     = WrongSideDrivingRule(road_center_x=road_center_x)
        self._parking_rule   = IllegalParkingRule(parking_zones=parking_zones or [])
        self._seatbelt_rule  = SeatbeltViolationRule()
        self._redlight_rule  = RedLightViolationRule(stop_line_y=stop_line_y)

    def analyze(
        self,
        image: np.ndarray,
        result: DetectorResult,
    ) -> List[ViolationResult]:
        violations: List[ViolationResult] = []

        violations.extend(self._helmet_rule.check(image, result))
        violations.extend(self._triple_rule.check(result))
        violations.extend(self._stop_rule.check(result))
        violations.extend(self._wrong_rule.update(result))
        violations.extend(self._parking_rule.update(result))
        violations.extend(self._seatbelt_rule.check(image, result))
        violations.extend(self._redlight_rule.check(image, result))

        logger.debug(f"Violations detected: {[v.violation_type for v in violations]}")
        return violations
