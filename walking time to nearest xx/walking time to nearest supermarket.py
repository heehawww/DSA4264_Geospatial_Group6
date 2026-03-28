import json
import math
import re
from pathlib import Path

import pandas as pd


HDB_GEOJSON_PATH = Path("HDBExistingBuilding.geojson")
SUPERMARKET_GEOJSON_PATH = Path("SupermarketsGEOJSON.geojson")
OUTPUT_PATH = Path("hdb_supermarket_features.csv")

# We only have geographic coordinates, not a road network.
# We first compute Euclidean distance in a local planar approximation,
# then convert that into an estimated walking route distance.
WALKING_DETOUR_FACTOR = 1.2
WALKING_SPEED_KMPH = 4.8


def euclidean_distance_km(lat1, lon1, lat2, lon2):
    km_per_degree_lat = 111.32
    avg_lat_rad = math.radians((lat1 + lat2) / 2)
    km_per_degree_lon = 111.32 * math.cos(avg_lat_rad)

    delta_lat_km = (lat2 - lat1) * km_per_degree_lat
    delta_lon_km = (lon2 - lon1) * km_per_degree_lon
    return math.sqrt(delta_lat_km**2 + delta_lon_km**2)


def polygon_centroid(coordinates):
    ring = coordinates[0]
    lon_sum = 0.0
    lat_sum = 0.0

    for lon, lat, *_ in ring:
        lon_sum += lon
        lat_sum += lat

    num_points = len(ring)
    return lat_sum / num_points, lon_sum / num_points


def extract_description_field(description, field_name):
    pattern = rf"<th>{re.escape(field_name)}</th>\s*<td>(.*?)</td>"
    match = re.search(pattern, description)
    if not match:
        return None

    value = match.group(1)
    value = re.sub(r"<.*?>", "", value)
    value = value.replace("\\/", "/").strip()
    return value or None


def load_hdb_blocks(path):
    with path.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    records = []
    for feature in geojson["features"]:
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})

        if geometry.get("type") != "Polygon":
            continue

        latitude, longitude = polygon_centroid(geometry["coordinates"])
        records.append(
            {
                "blk_no": properties.get("BLK_NO"),
                "postal_code": properties.get("POSTAL_COD"),
                "entity_id": properties.get("ENTITYID"),
                "latitude": latitude,
                "longitude": longitude,
            }
        )

    return pd.DataFrame(records)


def load_supermarkets(path):
    with path.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    records = []
    for feature in geojson["features"]:
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})

        if geometry.get("type") != "Point":
            continue

        longitude, latitude, *_ = geometry["coordinates"]
        description = properties.get("Description", "")

        records.append(
            {
                "supermarket_name": extract_description_field(description, "LIC_NAME"),
                "supermarket_blk_house": extract_description_field(description, "BLK_HOUSE"),
                "supermarket_street": extract_description_field(description, "STR_NAME"),
                "supermarket_postcode": extract_description_field(description, "POSTCODE"),
                "supermarket_latitude": latitude,
                "supermarket_longitude": longitude,
            }
        )

    return pd.DataFrame(records)


def attach_nearest_supermarket_features(hdb_df, supermarkets_df):
    supermarket_rows = supermarkets_df.to_dict("records")
    enriched_rows = []

    for hdb_row in hdb_df.to_dict("records"):
        nearest_supermarket = None
        nearest_distance_km = float("inf")

        for supermarket in supermarket_rows:
            distance_km = euclidean_distance_km(
                hdb_row["latitude"],
                hdb_row["longitude"],
                supermarket["supermarket_latitude"],
                supermarket["supermarket_longitude"],
            )
            if distance_km < nearest_distance_km:
                nearest_distance_km = distance_km
                nearest_supermarket = supermarket

        estimated_walking_distance_km = nearest_distance_km * WALKING_DETOUR_FACTOR
        walking_time_minutes = estimated_walking_distance_km / WALKING_SPEED_KMPH * 60

        enriched_rows.append(
            {
                **hdb_row,
                **nearest_supermarket,
                "euclidean_distance_to_nearest_supermarket_km": round(
                    nearest_distance_km, 4
                ),
                "nearest_supermarket_estimated_walking_km": round(
                    estimated_walking_distance_km, 4
                ),
                "walking_time_to_nearest_supermarket_mins": round(
                    walking_time_minutes, 2
                ),
            }
        )

    return pd.DataFrame(enriched_rows)


def main():
    hdb_df = load_hdb_blocks(HDB_GEOJSON_PATH)
    supermarkets_df = load_supermarkets(SUPERMARKET_GEOJSON_PATH)
    feature_df = attach_nearest_supermarket_features(hdb_df, supermarkets_df)
    feature_df.to_csv(OUTPUT_PATH, index=False)

    print(
        f"Saved {len(feature_df)} HDB rows with supermarket walking-time features to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
