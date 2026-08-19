Power BI scaffolding for Pinewood COO dashboard

This folder contains a semantic-model description, DAX measures, RLS roles, and a placeholder pbip instruction so you can assemble the actual .pbip using Power BI Desktop.

Files:
- semantic_model.json — described tables, relationships, measures, and RLS roles to implement.
- pbip_instructions.txt — step-by-step to produce the .pbip using Power BI Desktop and Tabular Editor (or the built-in model editor).
- pinewood_coo_dashboard.pbip.placeholder — not a real pbip (Power BI Desktop is required). Replace by exporting a real .pbip after publishing your report.

Quick steps to produce the .pbip:
1. Open Power BI Desktop.
2. Connect to the DuckDB (ODBC) or import the Gold tables as CSVs (preferred for reproducibility).
3. Build relationships as described in semantic_model.json.
4. Add the four DAX measures from semantic_model.json and create two RLS roles (COO, FacilityViewer).
5. Build the executive page (single-page layout) and save. Use File > Export > Power BI template or save .pbip from the Desktop (if supported) and commit to this folder as pinewood_coo_dashboard.pbip.

Notes:
- The semantic_model.json is a human-readable spec — it is intended to be copy/pasted into Tabular Editor or used as a guideline when building fields/measures.
- RLS roles assume a FacilityID and Region field exist on dim_facility.

