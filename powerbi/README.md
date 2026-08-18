# Power BI project

This folder contains the Power BI source-controlled project for the Pinewood COO dashboard. Because Power BI Desktop is Windows-only and this environment is not running the app, the repo stores the project metadata in pbip format and a placeholder semantic model reference.

Open the `pinewood_coo_dashboard.pbip` file in Power BI Desktop on a Windows machine, connect it to the DuckDB Gold database at `pipeline/warehouse/pinewood.duckdb`, and then apply the relationships and roles below.

Recommended model:
- `dim_community` -> `fact_occupancy_monthly` on `community_id`
- `dim_date` -> `fact_occupancy_monthly` on `month_start`
- `dim_community` -> `fact_move_out` on `community_id`
- `dim_community` -> `fact_incident_care_monthly` on `community_id`
- `dim_care_level` -> `fact_incident_care_monthly` on `care_level`
- `dim_date` -> `fact_incident_care_monthly` on `month_start`

Recommended RLS roles:
- `Regional Director`: filter `dim_community[region] = USERPRINCIPALNAME()` via a mapping table, or a static region filter when testing in Desktop.
- `Community Executive Director`: filter `dim_community[community_id] = USERNAME()` via a mapping table keyed to the executive's assigned community.

Dashboard design suggestion:
- Top KPIs: occupancy, move-out rate, incident rate, and rolling 90-day revenue trend.
- Trend line by month for occupancy and incidents.
- Community benchmark heatmap by region.
- Move-out reasons by community with executive commentary.
