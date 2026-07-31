"""
Fallback centroid coordinates for Karnataka districts, keyed by District.name.

Used only when a district has no case-derived centroid yet (AVG of
CaseMaster.latitude/longitude) — real cases are always preferred where they
exist; this is a reference-point fallback, not a claim about any specific
case's location. Shared between socio_insights.py (header KPI map) and
gwr.py (spatial regression needs SOME coordinate per district to run at all,
even before enough cases have been geo-tagged).
"""

DEFAULT_DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "Bengaluru Urban": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Belagavi": (15.8497, 74.4977),
    "Mangaluru": (12.9141, 74.8560),
    "Dakshina Kannada": (12.9141, 74.8560),
    "Kalaburagi": (17.3297, 76.8343),
    "Hubballi-Dharwad": (15.3647, 75.1240),
    "Dharwad": (15.4589, 75.0078),
    "Shivamogga": (13.9299, 75.5681),
    "Ballari": (15.1394, 76.9214),
    "Tumakuru": (13.3379, 77.1173),
    "Udupi": (13.3409, 74.7421),
}
