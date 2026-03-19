# Step 1: Primary School -> URA Area Join

Script:
- `join_primary_schools_to_ura_landuse.py`
- `plot_primary_boundaries_interactive.py`
- `classify_good_schools_top59.py`
- `plot_shopping_centres_kaggle.py`
- `tag_mrt_stations_with_kaggle_lines.py`

Default inputs:
- Schools point CSV: `C:\Users\User\Projects\primary school location\outputs\school_estate_summary.csv`
- URA land-use polygons: `C:\Users\User\Downloads\MasterPlan2025LandUseLayer.geojson`

Run:
```powershell
python "C:\Users\User\Projects\primary school location\step1_primary_boundaries\join_primary_schools_to_ura_landuse.py"
```

Outputs (under `step1_primary_boundaries\outputs`):
- `primary_school_landuse_join_points.geojson`
- `primary_school_boundaries.geojson`
- `unmatched_primary_schools.csv`
- `primary_school_boundaries_plot.png`
- `primary_school_boundaries_interactive_map.html`
- `primary_school_boundaries_cleaned.geojson`
- `primary_school_boundaries_buffer_1km.geojson`
- `primary_school_boundaries_buffer_2km.geojson`
- `school_oversubscription_ranking.csv`
- `good_schools_top59.csv`
- `normal_schools_others.csv`
- `shopping_centres_points.geojson`
- `shopping_centres_points.csv`
- `shopping_centres_interactive_map.html`
- `shopping_centres_with_ura_join.geojson`
- `shopping_centres_with_ura_join.csv`
- `shopping_centres_ura_polygons.geojson`
- `shopping_centres_unmatched.csv`
- `mrt_exits_tagged_with_lines.csv`
- `mrt_exits_tagged_with_lines.geojson`
- `mrt_exits_tagged_with_lines_map.html`
