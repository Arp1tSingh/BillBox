"""The fixed bill-type vocabulary shared by the prompt, tagging and UI."""

BILL_TYPES: tuple[tuple[str, str], ...] = (
    ("electricity", "Electricity"),
    ("water", "Water"),
    ("gas", "Gas"),
    ("internet-phone", "Internet and Phone"),
    ("maintenance", "Maintenance"),
    ("property-tax", "Property Tax"),
    ("electronics", "Electronics and Appliances"),
    ("medical", "Medical"),
    ("groceries", "Groceries"),
    ("dining", "Dining"),
    ("fuel", "Fuel"),
    ("insurance", "Insurance"),
    ("education", "Education"),
    ("repairs", "Repairs"),
    ("rent", "Rent"),
)

BILL_TYPE_SLUGS = frozenset(slug for slug, _ in BILL_TYPES)
BILL_TYPE_LABELS = dict(BILL_TYPES)
