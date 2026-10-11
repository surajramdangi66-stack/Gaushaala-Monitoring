from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from shapely.geometry import Point, Polygon

class SpatialZone:
    def __init__(self, zone_id: str, name: str, polygon_coords: List[List[float]], max_capacity: int = 4, color: str = "#10b981"):
        self.zone_id = zone_id
        self.name = name
        self.polygon_coords = polygon_coords
        self.max_capacity = max_capacity
        self.color = color
        # Shapely polygon
        if len(polygon_coords) >= 3:
            self.polygon = Polygon(polygon_coords)
        else:
            self.polygon = None

    def contains_point(self, x: float, y: float) -> bool:
        if self.polygon is None:
            return False
        point = Point(x, y)
        return self.polygon.contains(point) or self.polygon.touches(point)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.zone_id,
            "name": self.name,
            "polygon": self.polygon_coords,
            "max_capacity": self.max_capacity,
            "color": self.color
        }

class SpatialAnalytics:
    def __init__(self, camera_zones: Dict[str, Any]):
        self.zones: Dict[str, SpatialZone] = {}
        self.feeder_zone: Optional[SpatialZone] = None
        self.boundary_zone: Optional[SpatialZone] = None
        self.resting_zone: Optional[SpatialZone] = None

        for zone_type, config in camera_zones.items():
            zone = SpatialZone(
                zone_id=zone_type,
                name=config.get("name", zone_type.capitalize()),
                polygon_coords=config.get("polygon", []),
                max_capacity=config.get("max_capacity", 4),
                color=config.get("color", "#10b981")
            )
            self.zones[zone_type] = zone
            if zone_type == "feeder":
                self.feeder_zone = zone
            elif zone_type == "boundary":
                self.boundary_zone = zone
            elif zone_type == "resting":
                self.resting_zone = zone

    def check_geofence_breach(self, cx: float, cy: float) -> bool:
        """Returns True if the cattle is outside the pen boundary polygon."""
        if self.boundary_zone and self.boundary_zone.polygon:
            return not self.boundary_zone.contains_point(cx, cy)
        return False

    def is_in_feeder(self, cx: float, cy: float) -> bool:
        if self.feeder_zone:
            return self.feeder_zone.contains_point(cx, cy)
        return False

    def is_in_resting_bay(self, cx: float, cy: float) -> bool:
        if self.resting_zone:
            return self.resting_zone.contains_point(cx, cy)
        return False

    def get_zone_name_for_point(self, cx: float, cy: float) -> str:
        for zone in self.zones.values():
            if zone.contains_point(cx, cy):
                return zone.name
        return "Open Shed Area"
