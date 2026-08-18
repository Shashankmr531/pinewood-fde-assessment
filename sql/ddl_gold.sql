CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.dim_community (
    community_id VARCHAR PRIMARY KEY,
    community_name VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    region VARCHAR NOT NULL
);

CREATE OR REPLACE TABLE gold.dim_date (
    month_start DATE PRIMARY KEY,
    year_num INTEGER NOT NULL,
    month_num INTEGER NOT NULL,
    month_name VARCHAR NOT NULL
);

CREATE OR REPLACE TABLE gold.dim_care_level (
    care_level_code VARCHAR PRIMARY KEY,
    care_level_name VARCHAR NOT NULL
);

CREATE OR REPLACE TABLE gold.fact_occupancy_monthly (
    community_id VARCHAR NOT NULL,
    month_start DATE NOT NULL,
    occupied_units INTEGER NOT NULL,
    total_units INTEGER NOT NULL,
    occupancy_pct DECIMAL(5,4) NOT NULL,
    PRIMARY KEY (community_id, month_start)
);

CREATE OR REPLACE TABLE gold.fact_move_out (
    move_out_id VARCHAR PRIMARY KEY,
    resident_id VARCHAR NOT NULL,
    community_id VARCHAR NOT NULL,
    move_out_date DATE NOT NULL,
    move_out_reason VARCHAR NOT NULL,
    move_out_month DATE NOT NULL
);

CREATE OR REPLACE TABLE gold.fact_incident_care_monthly (
    community_id VARCHAR NOT NULL,
    care_level VARCHAR NOT NULL,
    month_start DATE NOT NULL,
    incident_count INTEGER NOT NULL,
    resident_days INTEGER NOT NULL,
    incident_rate_per_100_resident_days DECIMAL(10,4) NOT NULL,
    PRIMARY KEY (community_id, care_level, month_start)
);
