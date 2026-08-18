-- 1) Monthly occupancy rate by community
SELECT
    c.community_id,
    c.community_name,
    d.month_name,
    ROUND(f.occupancy_pct * 100, 2) AS occupancy_rate_pct
FROM gold.fact_occupancy_monthly f
JOIN gold.dim_community c USING (community_id)
JOIN gold.dim_date d ON d.month_start = f.month_start
ORDER BY d.month_start, c.community_id;

-- 2) Top three move-out reasons by community over the six-month period
WITH reason_counts AS (
    SELECT
        community_id,
        move_out_reason,
        COUNT(*) AS move_out_count
    FROM gold.fact_move_out
    WHERE move_out_date >= DATE '2025-01-01'
      AND move_out_date < DATE '2025-07-01'
    GROUP BY community_id, move_out_reason
),
community_totals AS (
    SELECT
        community_id,
        SUM(move_out_count) AS total_move_outs
    FROM reason_counts
    GROUP BY community_id
),
ranked AS (
    SELECT
        rc.community_id,
        rc.move_out_reason,
        rc.move_out_count,
        ct.total_move_outs,
        ROW_NUMBER() OVER (
            PARTITION BY rc.community_id
            ORDER BY rc.move_out_count DESC, rc.move_out_reason
        ) AS reason_rank
    FROM reason_counts rc
    JOIN community_totals ct USING (community_id)
)
SELECT
    community_id,
    move_out_reason,
    ROUND(100.0 * move_out_count / total_move_outs, 2) AS pct_of_total_move_outs
FROM ranked
WHERE reason_rank <= 3
ORDER BY community_id, reason_rank;

-- 3) Incident rate per 100 resident-days by community and care level
SELECT
    community_id,
    care_level,
    month_start,
    ROUND(100.0 * incident_count / NULLIF(resident_days, 0), 2) AS incident_rate_per_100_resident_days
FROM gold.fact_incident_care_monthly
ORDER BY month_start, community_id, care_level;
