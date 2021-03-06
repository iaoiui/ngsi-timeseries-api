"""
This module provides types to represent the NGSI Simple Location Format
geometries: point, line, box, and polygon. Each type implements a common
interface (defined by ``SlfGeometry``) to enumerate the points that define
the geometry. ``Iterables`` are used throughout so to be able to handle
large set of points in *constant* space.
"""

from typing import List, Iterable, Iterator, Optional
from geocoding.centroid import best_effort_centroid2d
from utils.streams import ensure_min_items


class SlfGeometry:
    """
    Represents a geometry in the NGSI Simple Location Format.
    """

    def enum_points(self) -> Iterator[List[float]]:
        """
        Enumerate the points that define this geometry's shape.
        This method can only be called once since it consumes the underlying
        stream of points that define the shape.

        :return: an iterable of coordinate pairs, where each pair is a list
            of two numbers ``[longitude, latitude]``---note the numbers are
            in the same order as in GeoJSON.
        """
        for p in self._points():
            yield [p.longitude(), p.latitude()]

    def _points(self) -> Iterable['SlfPoint']:
        pass

    def to_ngsi_attribute(self) -> dict:
        """
        Convert this geometry to the NGSI location attribute dictionary
        representation.
        :return: the NGSI location attribute.
        """
        ps = [p.wgs84_coords() for p in self._points()]
        return {
            'type': self.__class__.ngsi_type(),
            'value': ps[0] if isinstance(self, SlfPoint) else ps
        }

    @staticmethod
    def ngsi_type():
        """
        :return: this geometry's NGSI type.
        """
        pass

    def centroid2d(self) -> Optional['SlfPoint']:
        """
        Same as ``best_effort_centroid2d`` but converts the returned centroid
        coordinates (if any) to an ``SlfPoint``.
        """
        centroid = best_effort_centroid2d(self.enum_points())
        # enum_points returns [lon, lat] points, so centroid coords will be in
        # the same order.
        if centroid:
            return SlfPoint(longitude=centroid[0], latitude=centroid[1])
        return None

# NOTE. Performance.
# We could implement _points so that it always produces a fresh stream.
# Indeed this is what the implementation of SlfPoint and SlfBox do since
# it's efficient in those cases. If we wanted to do that for SlfLine and
# SlfPolygon too, we could use e.g. tee to duplicate the stream:
#
#     def _points(self) -> Iterable['SlfPoint']:
#         ps1, ps2 = tee(self._pts)
#         self._pts = ps1
#         return ps2
#
# But this sort of defeats the purpose of having streams in the first
# place. In fact, after ps2 is consumed, you end up with ps1 having a
# backing queue that contains all of the elements in _pts. (See tee's
# implementation.) So you'd have sucked the whole data set into memory
# which isn't what you want if you're streaming a large number of items.
# If we really need to be able to enumerate points more than once, then
# we should use lists instead of streams.


class SlfPoint(SlfGeometry):
    """
    Represents an NGSI Simple Location Format point.
    """

    def __init__(self, latitude: float, longitude: float):
        if latitude is None or longitude is None:
            raise ValueError
        self._latitude = latitude
        self._longitude = longitude

    def latitude(self) -> float:
        """
        :return: this point's latitude.
        """
        return self._latitude

    def longitude(self) -> float:
        """
        :return: this point's longitude.
        """
        return self._longitude

    def wgs84_coords(self):
        """
        :return: this point's coordinates in the WSG84 format:
            "latitude, longitude"
        """
        return '{}, {}'.format(self.latitude(), self.longitude())

    def _points(self) -> Iterable['SlfPoint']:
        yield self

    @staticmethod
    def ngsi_type() -> str:
        """
        :return: the NGSI type for an SLF point.
        """
        return 'geo:point'


class SlfLine(SlfGeometry):
    """
    Represents an NGSI Simple Location Format line.
    """

    def __init__(self, points: Iterable['SlfPoint']):
        self._pts = ensure_min_items(2, points)

    def _points(self) -> Iterable['SlfPoint']:
        return self._pts

    @staticmethod
    def ngsi_type():
        """
        :return: the NGSI type for an SLF line.
        """
        return 'geo:line'


class SlfPolygon(SlfGeometry):
    """
    Represents an NGSI Simple Location Format polygon.
    """

    def __init__(self, points: Iterable['SlfPoint']):
        self._pts = ensure_min_items(4, points)

    def _points(self) -> Iterable['SlfPoint']:
        return self._pts

    @staticmethod
    def ngsi_type():
        """
        :return: the NGSI type for an SLF polygon.
        """
        return 'geo:polygon'


class SlfBox(SlfGeometry):
    """
    Represents an NGSI Simple Location Format box.
    """

    def __init__(self, points: Iterable['SlfPoint']):
        ps = iter(ensure_min_items(2, points))
        self._bottom_right_corner = next(ps)
        self._top_left_corner = next(ps)

    def bottom_right_corner(self) -> SlfPoint:
        """
        :return: this box's bottom right corner point.
        """
        return self._bottom_right_corner

    def top_left_corner(self) -> SlfPoint:
        """
        :return: this box's top left corner point.
        """
        return self._top_left_corner

    def _points(self) -> Iterable['SlfPoint']:
        for p in [self.bottom_right_corner(), self.top_left_corner()]:
            yield p

    def to_polygon(self) -> SlfPolygon:
        """
        Convert this box into a rectangle encoded a Simple Location Format
        polygon.

        :return: the polygon.
        """
        top_right_corner = SlfPoint(self._top_left_corner.latitude(),
                                    self._bottom_right_corner.longitude())
        bottom_left_corner = SlfPoint(self._bottom_right_corner.latitude(),
                                      self._top_left_corner.longitude())
        return SlfPolygon([
            self._top_left_corner, top_right_corner,
            self._bottom_right_corner, bottom_left_corner,
            self._top_left_corner
        ])

    @staticmethod
    def ngsi_type() -> str:
        """
        :return: the NGSI type for an SLF polygon.
        """
        return 'geo:box'
