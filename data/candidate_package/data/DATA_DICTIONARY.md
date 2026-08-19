# Pinewood Senior Living — Dataset Reference

You have six months of CSV exports from five source systems. Files are named with the pattern `{source}_{table}_{YYYY_MM}.csv`. Some files are monthly snapshots, others are transactional exports for that month.

The data is messy on purpose. Read the contents carefully before you trust the headers.

## Communities

Pinewood operates 14 communities across three states. Community master data is not provided as a file. You will need to derive it from the data, or hard-code it once you have inspected the sources. The states represented are Oregon, Arizona, and Texas. Community IDs follow the pattern `C001` through `C014`.

## PointClickCare (PCC)

`pcc_residents_{YYYY_MM}.csv`
Monthly snapshot of residents who were active at any point during that month. A resident is "active" if their admit_date is on or before the last day of the month, and either their discharge_date is null or it falls within or after the month.

| Column | Description |
|---|---|
| resident_id | Unique identifier within PCC |
| community_id | Community where resident lives |
| first_name, last_name | Resident name |
| dob | Date of birth |
| gender | M or F |
| admit_date | Date resident first moved into the community |
| discharge_date | Date of discharge if applicable, otherwise blank |
| care_level | Level of care: Independent Living, Assisted Living, or Memory Care |
| acuity_score | Clinical acuity score from 1 (low) to 10 (high) |

`pcc_incidents_{YYYY_MM}.csv`
Incidents that occurred during the month.

| Column | Description |
|---|---|
| incident_id | Unique incident identifier |
| resident_id | The resident involved |
| community_id | Community where the incident occurred |
| incident_date | Date of the incident |
| incident_type | Fall, Medication Error, Behavioral, Skin Tear, Elopement, Other |
| severity | 1 (minor) to 5 (critical) |
| reported_by | Employee ID who reported it |

`pcc_care_history_{YYYY_MM}.csv`
Care level change events that occurred during the month.

| Column | Description |
|---|---|
| resident_id | The resident |
| change_date | Date the new level took effect |
| previous_level | Care level before the change (blank for first record) |
| new_level | Care level after the change |
| reason | Reason for the change |

## Yardi Senior Living

`yardi_units_{YYYY_MM}.csv`
Snapshot of the unit inventory at the start of the month.

| Column | Description |
|---|---|
| unit_id | Unique unit identifier |
| community_id | Community the unit belongs to |
| unit_type | IL, AL, or MC |
| monthly_rent | Base rent for the unit |
| snapshot_date | First day of the snapshot month |

`yardi_leases_{YYYY_MM}.csv`
Lease records active or changed during the month. A lease appears in a month's file if it was created in that month or had its move_out recorded in that month.

| Column | Description |
|---|---|
| lease_id | Unique lease identifier |
| resident_id | Resident on the lease |
| unit_id | Unit being leased |
| community_id | Community |
| move_in_date | Move-in date |
| move_out_date | Move-out date, blank if still active |
| move_out_reason | Reason if moved out |
| monthly_rate | Actual monthly rate paid (may differ from list rent) |

## ADP

`adp_shifts_{YYYY_MM}.csv`
Staffing shifts worked during the month.

| Column | Description |
|---|---|
| shift_id | Unique shift identifier |
| community_id | Where the shift was worked |
| employee_id | The employee |
| role | Caregiver, Med Tech, LPN, RN, Admin, Maintenance, Dining |
| shift_date | Date the shift was worked |
| hours_worked | Number of hours |
| hourly_rate | Pay rate at the time of the shift |

## Google Business Profile

`gbp_reviews_{YYYY_MM}.csv`
Google reviews left for each community during the month.

| Column | Description |
|---|---|
| review_id | Unique review identifier |
| community_id | Community being reviewed |
| review_date | Date the review was posted |
| rating | 1 to 5 stars |
| review_text | The review text |
| response_text | Pinewood's response if any |
| responded_at | When the response was posted |

## HubSpot

`hubspot_leads_{YYYY_MM}.csv`
Sales leads created during the month.

| Column | Description |
|---|---|
| lead_id | Unique lead identifier |
| community_id | Community the lead was for |
| lead_source | Channel the lead came from |
| created_date | When the lead entered the CRM |
| tour_date | Date of the in-person tour if any |
| deposit_date | Date deposit was paid if any |
| move_in_date | Eventual move-in date if won |
| status | Won, Lost, or Open |
| lost_reason | Reason if status is Lost |

## A few things to watch for

You will find that the data does not always behave the way the schema suggests. Source systems are run by humans, exports break, and naming conventions drift. Part of this exercise is figuring out what is wrong with the data and deciding what to do about it.
