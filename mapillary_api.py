from typing import Optional, Dict, Any, List
import requests
import sys
import json
import math
from geopy import distance, Point
from dataclasses import dataclass

@dataclass
class Image:
    id: str
    point: Point
    image_url: str
    compass_angle: float
    @staticmethod
    def frommapillary(json) -> "Image":
        return Image(json.get('id'),
                     Image.pointfromgeojson(json.get('geometry')),
                     json.get('thumb_original_url'),
                     json.get('computed_compass_angle'))
    @staticmethod
    def pointfromgeojson(geojson) -> Point:
        if geojson.get('type') != 'Point':
            raise Exception(f"Non-point json provided: {geojson}")
        coords = geojson.get('coordinates')
        return Point(coords[1], coords[0])


class MapillaryApi:
    ENDPOINT = "https://graph.mapillary.com"
    LATITUDE_OFFSET = 10 * 1 / 111111  # 111,111 m ~ 1 deg latitude, so ~10 meters
    LONGITUDE_OFFSET = lambda latitude: 10 * 1 / (111111 * math.cos(latitude))

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _query(self, url: str, parameters: Dict[str, Any]):
        my_parameters = parameters.copy()
        my_parameters["access_token"] = self.api_key
        url = f"{self.ENDPOINT}/{url}"
        print(f"Mapillary query {url=} parameters={my_parameters}", file=sys.stderr)
        resp = requests.get(url, params=my_parameters)
        resp.raise_for_status()
        return resp.json()

    def _bb(self, lat, lng):
        OFFSET_METERS = 15
        point = (lat, lng)
        offset = distance.distance(meters=OFFSET_METERS)
        return (
            offset.destination(point, 270).longitude,
            offset.destination(point, 180).latitude,
            offset.destination(point, 90).longitude,
            offset.destination(point, 0).latitude,
        )

    def images_near(self, lat, lng) -> List[Image]:
        minlng, minlat, maxlng, maxlat = self._bb(lat, lng)
        images = self._query(
            "images",
            {
                "bbox": f"{minlng},{minlat},{maxlng},{maxlat}",
                "fields": ",".join(
                    [
                        "id",
                        "geometry",
                        #"thumb_256_url",
                        #"thumb_1024_url",
                        #"thumb_2048_url",
                        "thumb_original_url",
                        #"compass_angle",
                        "computed_compass_angle",
                    ]
                ),
                "limit": 100,
            },
        ).get('data')
        return [Image.frommapillary(image) for image in images]

    def angle_between(self, lat1, lng1, lat2, lng2) -> float:
        # https://www.movable-type.co.uk/scripts/latlong.html#bearing
        y = math.sin(lng2 - lng1) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lng2 - lng1)
        theta = math.atan2(y, x)
        bearing = (theta * 180 / math.pi + 360) % 360
        return bearing

    def images_near_facing(self, lat1, lng1, lat2, lng2) -> Optional[Image]:
        near = self.images_near(lat1, lng1)
        near.sort(key=lambda image: distance.distance(image.point, [lat1, lng1]).meters)
        bearing = self.angle_between(lat1, lng1, lat2, lng2)
        best = math.inf
        best_image = None
        for image in near:
            # breaks around 360?
            compass_diff = abs(image.compass_angle - bearing)
            compass_diff = compass_diff if compass_diff < 180 else 360 - compass_diff
            if best > compass_diff:
                best = compass_diff
                best_image = image
            if abs(image.compass_angle - bearing) < 20:
                return image
        return best_image



