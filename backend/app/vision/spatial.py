from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import cv2
from shapely.geometry import Point, Polygon, LineString

class SpatialZone:
    """
    Production-grade Spatial Geofence Zone for Cattle Sheds:
    - Supports Feeder Trough ('चारा चरणी'), Pen Perimeter ('बाड़ा सुरक्षा सीमा'),
      Quarantine Ward ('क्वारंटीन वार्ड'), and Resting Bay ('विश्राम एवं जुगाली शेड').
    - Dual evaluation: Fast OpenCV cv2.pointPolygonTest + Shapely geometry.
    - Virtual Tripwire line segment tracking for breach and intrusion detection.
    """
    def __init__(
        self,
        zone_id: str,
        name: str,
        polygon_coords: List[List[float]],
        name_hi: Optional[str] = None,
        max_capacity: int = 4,
        color: str = "#10b981",
        zone_type: Optional[str] = None
    ):
        self.zone_id = zone_id
        self.zone_type = zone_type or zone_id
        self.name = name
        self.name_hi = name_hi or name
        self.polygon_coords = [[float(p[0]), float(p[1])] for p in polygon_coords]
        self.max_capacity = max_capacity
        self.color = color

        # Precompute Shapely Polygon and OpenCV Contour
        if len(self.polygon_coords) >= 3:
            self.polygon = Polygon(self.polygon_coords)
            self.cv_contour = np.array(self.polygon_coords, dtype=np.int32).reshape((-1, 1, 2))
        else:
            self.polygon = None
            self.cv_contour = None

        # Precompute boundary line segments for virtual tripwire intersections
        self.segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        if len(self.polygon_coords) >= 3:
            n = len(self.polygon_coords)
            for i in range(n):
                p1 = (self.polygon_coords[i][0], self.polygon_coords[i][1])
                p2 = (self.polygon_coords[(i + 1) % n][0], self.polygon_coords[(i + 1) % n][1])
                self.segments.append((p1, p2))

    def contains_point(self, x: float, y: float) -> bool:
        """Fast point-in-polygon test."""
        if self.cv_contour is not None:
            # cv2.pointPolygonTest returns > 0 (inside), = 0 (on edge), < 0 (outside)
            res = cv2.pointPolygonTest(self.cv_contour, (float(x), float(y)), False)
            return res >= 0
        if self.polygon is not None:
            pt = Point(x, y)
            return self.polygon.contains(pt) or self.polygon.touches(pt)
        return False

    def intersects_segment(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Checks if a movement vector (x1, y1) -> (x2, y2) crosses the zone's perimeter."""
        if self.polygon is None:
            return False
        motion_line = LineString([(x1, y1), (x2, y2)])
        boundary_line = self.polygon.boundary
        return motion_line.intersects(boundary_line)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.zone_id,
            "type": self.zone_type,
            "name": self.name,
            "name_hi": self.name_hi,
            "polygon": self.polygon_coords,
            "max_capacity": self.max_capacity,
            "color": self.color
        }


def analyze_trough_visual_density(frame: np.ndarray, polygon: List[List[float]]) -> Dict[str, Any]:
    """
    Vision-Based Feeder Trough Emptiness & Pixel Density Analysis:
    - Crops the feeder polygon ROI.
    - Masks non-polygon pixels.
    - Evaluates HSV color presence for green fodder (fresh grass/berseem),
      yellow/amber fodder (dry hay/bhusa/straw), and cattle grain pellets.
    - Computes Laplacian variance for texture gradient (food texture vs smooth trough surface).
    - Returns fill percentage, depletion status, and optical confidence.
    """
    if frame is None or frame.size == 0 or len(polygon) < 3:
        return {
            "fill_percent": 0.0,
            "is_empty": True,
            "is_low": True,
            "status": "NOT_CONFIGURED",
            "confidence": 0.0,
            "color_distribution": {"green_fodder": 0.0, "dry_hay": 0.0, "empty_base": 1.0}
        }

    try:
        fh, fw = frame.shape[:2]
        pts = np.array(polygon, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(fw, x + w), min(fh, y + h)

        if x2 <= x1 or y2 <= y1:
            return {
                "fill_percent": 0.0,
                "is_empty": True,
                "is_low": True,
                "status": "INVALID_BOUNDS",
                "confidence": 0.0
            }

        # Sub-crop and local mask
        roi = frame[y1:y2, x1:x2]
        local_pts = pts - [x1, y1]
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        cv2.fillPoly(mask, [local_pts], 255)

        total_trough_pixels = max(1, int(np.count_nonzero(mask)))

        # HSV Color Density Analysis
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 1. Fresh green grass/fodder (H: 25-88, S: 30-255, V: 30-255)
        green_mask = cv2.inRange(hsv_roi, (25, 30, 30), (88, 255, 255))
        green_masked = cv2.bitwise_and(green_mask, green_mask, mask=mask)
        green_pixels = int(np.count_nonzero(green_masked))

        # 2. Dry straw/bhusa/hay (H: 12-25, S: 40-255, V: 45-255)
        dry_mask = cv2.inRange(hsv_roi, (12, 40, 45), (25, 255, 255))
        dry_masked = cv2.bitwise_and(dry_mask, dry_mask, mask=mask)
        dry_pixels = int(np.count_nonzero(dry_masked))

        # 3. Feed pellets/chana/grain concentrate (H: 5-20, S: 20-180, V: 30-200)
        concentrate_mask = cv2.inRange(hsv_roi, (5, 20, 30), (20, 180, 200))
        concentrate_masked = cv2.bitwise_and(concentrate_mask, concentrate_mask, mask=mask)
        concentrate_pixels = int(np.count_nonzero(concentrate_masked))

        # Combine all fodder masks
        combined_fodder = cv2.bitwise_or(green_masked, dry_masked)
        combined_fodder = cv2.bitwise_or(combined_fodder, concentrate_masked)
        fodder_pixel_count = int(np.count_nonzero(combined_fodder))

        # Texture gradient check via Laplacian
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())
        texture_boost = min(0.20, laplacian_var / 2500.0)

        # Raw fill ratio normalized
        raw_ratio = float(fodder_pixel_count) / float(total_trough_pixels)
        adjusted_ratio = min(1.0, raw_ratio * 1.5 + (texture_boost if raw_ratio > 0.05 else 0.0))

        fill_percent = round(adjusted_ratio * 100.0, 1)
        is_empty = fill_percent < 15.0
        is_low = (15.0 <= fill_percent < 35.0)

        if fill_percent >= 60.0:
            status = "OPTIMAL"
        elif fill_percent >= 35.0:
            status = "ADEQUATE"
        elif fill_percent >= 15.0:
            status = "LOW_FODDER"
        else:
            status = "DEPLETED_EMPTY"

        green_pct = round((green_pixels / total_trough_pixels) * 100.0, 1)
        dry_pct = round((dry_pixels / total_trough_pixels) * 100.0, 1)

        return {
            "fill_percent": fill_percent,
            "is_empty": is_empty,
            "is_low": is_low,
            "status": status,
            "confidence": min(0.98, max(0.65, 0.50 + fill_percent / 200.0)),
            "laplacian_texture_variance": round(laplacian_var, 1),
            "color_distribution": {
                "fresh_green_fodder_pct": green_pct,
                "dry_straw_hay_pct": dry_pct,
                "empty_trough_floor_pct": max(0.0, round(100.0 - fill_percent, 1))
            }
        }
    except Exception as e:
        return {
            "fill_percent": 0.0,
            "is_empty": True,
            "is_low": True,
            "status": f"INSPECTION_ERROR: {str(e)}",
            "confidence": 0.0
        }


class SpatialAnalytics:
    """
    Manages all polygon geofence zones for a specific camera/shed:
    - Feeder Trough ('feeder')
    - Pen Perimeter ('boundary')
    - Quarantine Ward ('quarantine')
    - Resting & Rumination Bay ('resting')
    """
    def __init__(self, camera_zones: Dict[str, Any]):
        self.zones: Dict[str, SpatialZone] = {}
        self.feeder_zone: Optional[SpatialZone] = None
        self.boundary_zone: Optional[SpatialZone] = None
        self.quarantine_zone: Optional[SpatialZone] = None
        self.resting_zone: Optional[SpatialZone] = None

        STANDARD_METADATA = {
            "feeder": {
                "name": "Feeder Trough (चारा चरणी)",
                "name_hi": "चारा चरणी क्षेत्र",
                "color": "#10b981",
                "max_capacity": 4
            },
            "boundary": {
                "name": "Pen Perimeter (बाड़ा सुरक्षा सीमा)",
                "name_hi": "बाड़ा सुरक्षा सीमा",
                "color": "#ef4444",
                "max_capacity": 25
            },
            "quarantine": {
                "name": "Quarantine Ward (क्वारंटीन वार्ड)",
                "name_hi": "पृथक / क्वारंटीन वार्ड",
                "color": "#f59e0b",
                "max_capacity": 3
            },
            "resting": {
                "name": "Resting Bay (विश्राम एवं जुगाली शेड)",
                "name_hi": "विश्राम एवं जुगाली शेड",
                "color": "#3b82f6",
                "max_capacity": 12
            }
        }

        for zone_type, config in camera_zones.items():
            meta = STANDARD_METADATA.get(zone_type, {})
            zone = SpatialZone(
                zone_id=zone_type,
                name=config.get("name") or meta.get("name", zone_type.capitalize()),
                name_hi=config.get("name_hi") or meta.get("name_hi", zone_type),
                polygon_coords=config.get("polygon", []),
                max_capacity=config.get("max_capacity") or meta.get("max_capacity", 4),
                color=config.get("color") or meta.get("color", "#10b981"),
                zone_type=zone_type
            )
            self.zones[zone_type] = zone

            if zone_type == "feeder":
                self.feeder_zone = zone
            elif zone_type == "boundary":
                self.boundary_zone = zone
            elif zone_type == "quarantine":
                self.quarantine_zone = zone
            elif zone_type == "resting":
                self.resting_zone = zone

    def check_geofence_breach(self, cx: float, cy: float) -> bool:
        """Returns True if cattle is outside the pen boundary perimeter."""
        if self.boundary_zone and self.boundary_zone.polygon:
            return not self.boundary_zone.contains_point(cx, cy)
        return False

    def is_in_feeder(self, cx: float, cy: float) -> bool:
        """Returns True if point is inside the feeder trough zone."""
        if self.feeder_zone:
            return self.feeder_zone.contains_point(cx, cy)
        return False

    def is_in_quarantine(self, cx: float, cy: float) -> bool:
        """Returns True if point is inside the quarantine ward."""
        if self.quarantine_zone:
            return self.quarantine_zone.contains_point(cx, cy)
        return False

    def is_in_resting_bay(self, cx: float, cy: float) -> bool:
        """Returns True if point is inside the resting bay."""
        if self.resting_zone:
            return self.resting_zone.contains_point(cx, cy)
        return False

    def check_quarantine_tripwire(self, prev_x: float, prev_y: float, curr_x: float, curr_y: float) -> Optional[str]:
        """
        Virtual Tripwire on Quarantine Boundary:
        - Detects unauthorized entry ("INTRUSION") or escape ("ESCAPE").
        """
        if not self.quarantine_zone or not self.quarantine_zone.polygon:
            return None

        was_inside = self.quarantine_zone.contains_point(prev_x, prev_y)
        is_inside = self.quarantine_zone.contains_point(curr_x, curr_y)

        if not was_inside and is_inside:
            return "UNAUTHORIZED_ENTRY"
        elif was_inside and not is_inside:
            return "QUARANTINE_ESCAPE"
        elif self.quarantine_zone.intersects_segment(prev_x, prev_y, curr_x, curr_y):
            return "PERIMETER_CROSSING"
        return None

    def get_zone_name_for_point(self, cx: float, cy: float, lang: str = "hi") -> str:
        """Returns localized human-readable name of the zone for a point."""
        for zone in self.zones.values():
            if zone.contains_point(cx, cy):
                return zone.name_hi if lang == "hi" else zone.name
        return "खुला विचरण प्रांगण" if lang == "hi" else "Open Shed Area"

    def analyze_trough(self, frame: np.ndarray) -> Dict[str, Any]:
        """Runs visual density analysis on the configured feeder zone."""
        if not self.feeder_zone or len(self.feeder_zone.polygon_coords) < 3:
            return {
                "fill_percent": 0.0,
                "is_empty": True,
                "is_low": True,
                "status": "NOT_CONFIGURED",
                "message": "Feeder trough polygon not defined"
            }
        return analyze_trough_visual_density(frame, self.feeder_zone.polygon_coords)
