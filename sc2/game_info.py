from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple

from sc2.cache import property_immutable_cache, property_mutable_cache
from sc2.pixel_map import PixelMap
from sc2.player import Player, Race
from sc2.position import Point2, Rect, Size


class Ramp:

    def __init__(self, points: Set[Point2], game_info: GameInfo):
        """
        :param points:
        :param game_info:
        """
        self._points: Set[Point2] = points
        self.__game_info = game_info
        # Tested by printing actual building locations vs calculated depot positions
        self.x_offset = 0.5
        self.y_offset = 0.5
        # Can this be removed?
        self.cache = {}

    @property_immutable_cache
    def _height_map(self):
        return self.__game_info.terrain_height

    @property_immutable_cache
    def _placement_grid(self):
        return self.__game_info.placement_grid

    @property_immutable_cache
    def size(self) -> int:
        return len(self._points)

    def height_at(self, p: Point2) -> int:
        return self._height_map[p]

    @property_mutable_cache
    def points(self) -> Set[Point2]:
        return self._points.copy()

    @property_mutable_cache
    def upper(self) -> Set[Point2]:
        """ Returns the upper points of a ramp. """
        current_max = -10000
        result = set()
        for p in self._points:
            height = self.height_at(p)
            if height > current_max:
                current_max = height
                result = {p}
            elif height == current_max:
                result.add(p)
        return result

    @property_mutable_cache
    def upper2_for_ramp_wall(self) -> Set[Point2]:
        """ Returns the 2 upper ramp points of the main base ramp required for the supply depot and barracks placement properties used in this file. """
        if len(self.upper) > 5:
            # NOTE: this was way too slow on large ramps
            return set()  # HACK: makes this work for now
            # FIXME: please do

        return set(sorted(list(self.upper), key=lambda x: x.distance_to_point2(self.bottom_center), reverse=True)[:2])

    @property_immutable_cache
    def top_center(self) -> Point2:
        upper = self.upper
        length = len(upper)
        pos = Point2((sum(p.x for p in upper) / length, sum(p.y for p in upper) / length))
        return pos

    @property_mutable_cache
    def lower(self) -> Set[Point2]:
        current_min = 10000
        result = set()
        for p in self._points:
            height = self.height_at(p)
            if height < current_min:
                current_min = height
                result = {p}
            elif height == current_min:
                result.add(p)
        return result

    @property_immutable_cache
    def bottom_center(self) -> Point2:
        lower = self.lower
        length = len(lower)
        pos = Point2((sum(p.x for p in lower) / length, sum(p.y for p in lower) / length))
        return pos

    @property_immutable_cache
    def barracks_in_middle(self) -> Optional[Point2]:
        """ Barracks position in the middle of the 2 depots """
        if len(self.upper) not in {2, 5}:
            return None
        if len(self.upper2_for_ramp_wall) == 2:
            points = self.upper2_for_ramp_wall
            p1 = points.pop().offset((self.x_offset, self.y_offset))
            p2 = points.pop().offset((self.x_offset, self.y_offset))
            # Offset from top point to barracks center is (2, 1)
            intersects = p1.circle_intersection(p2, 5**0.5)
            anyLowerPoint = next(iter(self.lower))
            return max(intersects, key=lambda p: p.distance_to_point2(anyLowerPoint))
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_immutable_cache
    def depot_in_middle(self) -> Optional[Point2]:
        """ Depot in the middle of the 3 depots """
        if len(self.upper) not in {2, 5}:
            return None
        if len(self.upper2_for_ramp_wall) == 2:
            points = self.upper2_for_ramp_wall
            p1 = points.pop().offset((self.x_offset, self.y_offset))
            p2 = points.pop().offset((self.x_offset, self.y_offset))
            # Offset from top point to depot center is (1.5, 0.5)
            try:
                intersects = p1.circle_intersection(p2, 2.5**0.5)
            except AssertionError:
                # Returns None when no placement was found, this is the case on the map Honorgrounds LE with an exceptionally large main base ramp
                return None
            anyLowerPoint = next(iter(self.lower))
            return max(intersects, key=lambda p: p.distance_to_point2(anyLowerPoint))
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_mutable_cache
    def corner_depots(self) -> Set[Point2]:
        """ Finds the 2 depot positions on the outside """
        if not self.upper2_for_ramp_wall:
            return set()
        if len(self.upper2_for_ramp_wall) == 2:
            points = self.upper2_for_ramp_wall
            p1 = points.pop().offset((self.x_offset, self.y_offset))
            p2 = points.pop().offset((self.x_offset, self.y_offset))
            center = p1.towards(p2, p1.distance_to_point2(p2) / 2)
            depotPosition = self.depot_in_middle
            if depotPosition is None:
                return set()
            # Offset from middle depot to corner depots is (2, 1)
            intersects = center.circle_intersection(depotPosition, 5**0.5)
            return intersects
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_immutable_cache
    def barracks_can_fit_addon(self) -> bool:
        """ Test if a barracks can fit an addon at natural ramp """
        # https://i.imgur.com/4b2cXHZ.png
        if len(self.upper2_for_ramp_wall) == 2:
            return self.barracks_in_middle.x + 1 > max(self.corner_depots, key=lambda depot: depot.x).x
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_immutable_cache
    def barracks_correct_placement(self) -> Optional[Point2]:
        """ Corrected placement so that an addon can fit """
        if self.barracks_in_middle is None:
            return None
        if len(self.upper2_for_ramp_wall) == 2:
            if self.barracks_can_fit_addon:
                return self.barracks_in_middle
            else:
                return self.barracks_in_middle.offset((-2, 0))
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_immutable_cache
    def protoss_wall_pylon(self) -> Optional[Point2]:
        """
        Pylon position that powers the two wall buildings and the warpin position.
        """
        if len(self.upper) not in {2, 5}:
            return None
        if len(self.upper2_for_ramp_wall) != 2:
            raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")
        middle = self.depot_in_middle
        # direction up the ramp
        direction = self.barracks_in_middle.negative_offset(middle)
        return middle + 6 * direction

    @property_mutable_cache
    def protoss_wall_buildings(self) -> List[Point2]:
        """
        List of two positions for 3x3 buildings that form a wall with a spot for a one unit block.
        These buildings can be powered by a pylon on the protoss_wall_pylon position.
        """
        if len(self.upper) not in {2, 5}:
            return []
        if len(self.upper2_for_ramp_wall) == 2:
            middle = self.depot_in_middle
            # direction up the ramp
            direction = self.barracks_in_middle.negative_offset(middle)
            # sort depots based on distance to start to get wallin orientation
            sorted_depots = sorted(
                self.corner_depots, key=lambda depot: depot.distance_to(self.__game_info.player_start_location)
            )
            wall1 = sorted_depots[1].offset(direction)
            wall2 = middle + direction + (middle - wall1) / 1.5
            return [wall1, wall2]
        raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")

    @property_immutable_cache
    def protoss_wall_warpin(self) -> Optional[Point2]:
        """
        Position for a unit to block the wall created by protoss_wall_buildings.
        Powered by protoss_wall_pylon.
        """
        if len(self.upper) not in {2, 5}:
            return None
        if len(self.upper2_for_ramp_wall) != 2:
            raise Exception("Not implemented. Trying to access a ramp that has a wrong amount of upper points.")
        middle = self.depot_in_middle
        # direction up the ramp
        direction = self.barracks_in_middle.negative_offset(middle)
        # sort depots based on distance to start to get wallin orientation
        sorted_depots = sorted(self.corner_depots, key=lambda x: x.distance_to(self.__game_info.player_start_location))
        return sorted_depots[0].negative_offset(direction)


class GameInfo:

    def __init__(self, proto):
        self._proto = proto
        self.players: List[Player] = [Player.from_proto(p) for p in self._proto.player_info]
        self.map_name: str = self._proto.map_name
        self.local_map_path: str = self._proto.local_map_path
        self.map_size: Size = Size.from_proto(self._proto.start_raw.map_size)

        # self.pathing_grid[point]: if 0, point is not pathable, if 1, point is pathable
        self.pathing_grid: PixelMap = PixelMap(self._proto.start_raw.pathing_grid, in_bits=True, mirrored=False)
        # self.terrain_height[point]: returns the height in range of 0 to 255 at that point
        self.terrain_height: PixelMap = PixelMap(self._proto.start_raw.terrain_height, mirrored=False)
        # self.placement_grid[point]: if 0, point is not placeable, if 1, point is pathable
        self.placement_grid: PixelMap = PixelMap(self._proto.start_raw.placement_grid, in_bits=True, mirrored=False)
        self.playable_area = Rect.from_proto(self._proto.start_raw.playable_area)
        self.map_center = self.playable_area.center
        self.map_ramps: List[Ramp] = None  # Filled later by BotAI._prepare_first_step
        self.vision_blockers: Set[Point2] = None  # Filled later by BotAI._prepare_first_step
        self.player_races: Dict[int, Race] = {
            p.player_id: p.race_actual or p.race_requested
            for p in self._proto.player_info
        }
        self.start_locations: List[Point2] = [Point2.from_proto(sl) for sl in self._proto.start_raw.start_locations]
        self.player_start_location: Point2 = None  # Filled later by BotAI._prepare_first_step

        def equal_height_around(tile):
            # mask to slice array 1 around tile
            sliced = self.terrain_height.data_numpy[tile[1] - 1:tile[1] + 2, tile[0] - 1:tile[0] + 2]
            return true

        map_area = self.playable_area
        # all points in the playable area that are pathable but not placable
        return None

    def _find_groups(self, points: Set[Point2], minimum_points_per_group: int = 8):
        """
        From a set of points, this function will try to group points together by
        painting clusters of points in a rectangular map using flood fill algorithm.
        Returns groups of points as list, like [{p1, p2, p3}, {p4, p5, p6, p7, p8}]
        """
        # TODO do we actually need colors here? the ramps will never touch anyways.
        NOT_COLORED_YET = -1
        map_width = self.pathing_grid.width
        map_height = self.pathing_grid.height
        currentColor: int = NOT_COLORED_YET
        picture: List[List[int]] = [[-2 for _ in range(map_width)] for _ in range(map_height)]

        def paint(pt: Point2) -> None:
            picture[pt.y][pt.x] = currentColor

        nearby = [(a, b) for a in [-1, 0, 1] for b in [-1, 0, 1] if a != 0 or b != 0]

        remaining: Set[Point2] = set(points)
        for point in remaining:
            paint(point)
        currentColor = 1
        queue: Deque[Point2] = deque()
        while remaining:
            currentGroup: Set[Point2] = set()
            if not queue:
                start = remaining.pop()
                paint(start)
                queue.append(start)
                currentGroup.add(start)
            while queue:
                base: Point2 = queue.popleft()
                for offset in nearby:
                    px, py = base.x + offset[0], base.y + offset[1]
                    if not (0 <= px < map_width and 0 <= py < map_height):
                        continue
                    if picture[py][px] != NOT_COLORED_YET:
                        continue
                    point: Point2 = Point2((px, py))
                    remaining.discard(point)
                    paint(point)
                    queue.append(point)
                    currentGroup.add(point)
            if len(currentGroup) >= minimum_points_per_group:
                yield currentGroup
