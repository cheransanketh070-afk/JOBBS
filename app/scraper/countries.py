# A curated list of countries offered in the search filter.
# LinkedIn's public jobs-guest search endpoint geocodes a plain place name
# passed in the "location" query parameter, so no internal geoId lookup
# table is required (those internal IDs are undocumented and change
# silently, which makes them an unreliable thing to hardcode).

COUNTRIES = [
    "Worldwide", "United States", "United Kingdom", "Canada", "Australia",
    "India", "Singapore", "Germany", "France", "Netherlands", "Ireland",
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Sri Lanka", "Pakistan",
    "Bangladesh", "Philippines", "Malaysia", "Indonesia", "Vietnam",
    "Thailand", "Japan", "South Korea", "China", "Hong Kong", "New Zealand",
    "South Africa", "Nigeria", "Kenya", "Egypt", "Brazil", "Mexico",
    "Argentina", "Chile", "Colombia", "Spain", "Italy", "Portugal",
    "Switzerland", "Sweden", "Norway", "Denmark", "Finland", "Poland",
    "Turkey", "Israel", "Russia", "Ukraine", "Greece", "Belgium", "Austria",
]

WORKPLACE_TYPES = {
    "any": {"label": "Any", "f_wt": ""},
    "onsite": {"label": "On-site", "f_wt": "1"},
    "remote": {"label": "Remote", "f_wt": "2"},
    "hybrid": {"label": "Hybrid", "f_wt": "3"},
}

DATE_POSTED = {
    "any": {"label": "Any time", "f_tpr": ""},
    "day": {"label": "Past 24 hours", "f_tpr": "r86400"},
    "week": {"label": "Past week", "f_tpr": "r604800"},
    "month": {"label": "Past month", "f_tpr": "r2592000"},
}

POPULAR_CATEGORIES = [
    "Software Engineer", "Data Engineer", "Data Scientist", "AI Engineer",
    "DevOps Engineer", "Product Manager", "UI/UX Designer", "QA Engineer",
    "Cybersecurity Analyst", "Business Analyst", "Marketing Manager",
    "Sales Executive", "Customer Support", "HR Manager", "Accountant",
    "Project Manager", "Mobile App Developer", "Cloud Engineer",
]
