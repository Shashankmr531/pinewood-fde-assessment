CARE_LEVEL_MAP = {
    "il": "IL", "independent": "IL", "independent living": "IL",
    "assisted": "AL", "assisted living": "AL", "al": "AL",
    "memory": "MC", "memory care": "MC", "mc": "MC",
    "nan": None, "": None,
}

MOVE_REASON_MAP = {
    "financial": "Financial", "higher care needed": "Higher Care Needed",
    "family decision": "Family Decision", "hospital transfer": "Hospital Transfer",
    "deceased": "Deceased", "dissatisfied": "Dissatisfied", "other": "Other",
    "care transition": "Higher Care Needed", "changed care level": "Higher Care Needed",
    "health decline": "Higher Care Needed", "affordability": "Financial",
    "": None, "nan": None,
}

COMMUNITIES = [
    ("C001", "Pinewood Bend", "OR", "Pacific Northwest"), ("C002", "Pinewood Corvallis", "OR", "Pacific Northwest"),
    ("C003", "Pinewood Eugene", "OR", "Pacific Northwest"), ("C004", "Pinewood Salem", "OR", "Pacific Northwest"),
    ("C005", "Pinewood Phoenix", "AZ", "Southwest"), ("C006", "Pinewood Scottsdale", "AZ", "Southwest"),
    ("C007", "Pinewood Mesa", "AZ", "Southwest"), ("C008", "Pinewood Tucson", "AZ", "Southwest"),
    ("C009", "Pinewood Dallas", "TX", "South"), ("C010", "Pinewood Fort Worth", "TX", "South"),
    ("C011", "Pinewood Houston", "TX", "South"), ("C012", "Pinewood San Antonio", "TX", "South"),
    ("C013", "Pinewood Austin", "TX", "South"), ("C014", "Pinewood Round Rock", "TX", "South"),
]
COMMUNITY_IDS = tuple(row[0] for row in COMMUNITIES)
CARE_LEVELS = ("IL", "AL", "MC")
