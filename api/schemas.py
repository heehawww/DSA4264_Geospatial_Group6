from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    month: str | None = Field(default=None, description="Transaction month in YYYY-MM format")
    town: str | None = None
    flat_type: str | None = None
    flat_model: str | None = None
    floor_area_sqm: float | None = None
    lease_commence_date: int | None = None
    remaining_lease: str | None = Field(default=None, description="Example: '58 years 04 months'")
    storey_range: str | None = Field(default=None, description="Example: '04 TO 06'")
    nearest_mall_walking_distance_m: float | None = None
    malls_within_10min_walk: float | None = None
    nearest_mrt_walking_distance_m: float | None = None
    mrt_unique_lines_within_10min_walk: float | None = None
    school_count_1km: float | None = None
    good_school_count_1km: float | None = None
    school_count_2km: float | None = None
    good_school_count_2km: float | None = None
    nearest_bus_stop_walking_distance_m: float | None = None
    bus_stops_within_5min_walk: float | None = None
    nearest_hawker_centre_walking_distance_m: float | None = None
    hawker_centres_within_5min_walk: float | None = None
    nearest_supermarket_walking_distance_m: float | None = None
    supermarkets_within_10min_walk: float | None = None
    nearest_park_walking_distance_m: float | None = None
    parks_within_5min_walk: float | None = None
    nearest_pcn_walking_distance_m: float | None = None
    pcns_within_5min_walk: float | None = None


class HealthResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str


class MetadataResponse(BaseModel):
    data_dir: str
    feature_dataset_path: str
    feature_dataset_rows: int
    ols_terms: int
    rdd_rows: int
    premium_rows: int
    raw_resale_dataset_status: str
    raw_resale_dataset_path: str | None
    raw_resale_dataset_rows: int | None
    raw_resale_dataset_note: str
    model_metrics: dict[str, Any]
    rdd_summary: dict[str, Any]
    premium_summary: dict[str, Any]


class TabularResponse(BaseModel):
    count: int
    filters: dict[str, Any]
    rows: list[dict[str, Any]]


class PremiumListResponse(BaseModel):
    summary: dict[str, Any]
    filters: dict[str, Any]
    rows: list[dict[str, Any]]


class RawResalesResponse(BaseModel):
    dataset_kind: str
    dataset_path: str
    is_true_raw_dataset: bool
    note: str
    count: int
    rows: list[dict[str, Any]]


class ResalesSummaryResponse(BaseModel):
    dataset_kind: str
    dataset_path: str
    is_true_raw_dataset: bool
    note: str
    filters: dict[str, Any]
    summary: dict[str, Any]
    grouped_rows: list[dict[str, Any]]


class ResalesSchemaResponse(BaseModel):
    dataset_kind: str
    dataset_path: str
    is_true_raw_dataset: bool
    available_columns: list[str]
    supported_filters: dict[str, Any]
    supported_group_by: list[str]
    notes: list[str]


class PredictSchemaResponse(BaseModel):
    raw_request_fields: dict[str, Any]
    engineered_model_fields: list[str]
    defaults_used_when_omitted: dict[str, Any]
    allowed_categories_sample: dict[str, list[str]]
    notes: list[str]


class PredictResponse(BaseModel):
    predicted_price: float
    currency: str
    used_defaults: bool
    provided_raw_fields: list[str]
    defaulted_raw_fields: list[str]
    warning: str | None
    engineered_features_used: dict[str, Any]
    model: str
    note: str
