"""
Temporal & seasonal crime-pattern analytics — day-of-week, monthly seasonality,
and hour-of-day (§5 adjacent — not Hawkes/ETAS, just real date/time aggregation
over case_master).

Hour-of-day is honestly coverage-limited: CaseMaster only gained a
time-of-occurrence field recently (`incident_time`, nullable, never
backfilled/guessed for historical cases) — see app/models/case.py. This
reports the real coverage percentage rather than pretending every case has a
recorded hour, and returns an empty hour_of_day series when coverage is zero
instead of fabricating one.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseMaster

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class TemporalTrendsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_temporal_trends(
        self, district_id: int, crime_head_id: Optional[int] = None
    ) -> Dict[str, Any]:
        incident_date_expr = func.coalesce(CaseMaster.incident_from_date, CaseMaster.date_reported)
        filters = [incident_date_expr.is_not(None), CaseMaster.district_id == district_id]
        if crime_head_id is not None:
            filters.append(CaseMaster.crime_head_id == crime_head_id)

        rows = (
            await self.db.execute(
                select(incident_date_expr.label("incident_date"), CaseMaster.incident_time).where(*filters)
            )
        ).all()

        total = len(rows)
        if total == 0:
            return {
                "status": "insufficient_data",
                "total_cases": 0,
                "day_of_week": [],
                "weekday_vs_weekend": None,
                "monthly": [],
                "hour_of_day": [],
                "hour_of_day_coverage_pct": 0.0,
            }

        dow_counts = [0] * 7
        month_counts = [0] * 12
        hour_counts = [0] * 24
        time_covered = 0

        for incident_date, incident_time in rows:
            dow_counts[incident_date.weekday()] += 1
            month_counts[incident_date.month - 1] += 1
            if incident_time is not None:
                hour_counts[incident_time.hour] += 1
                time_covered += 1

        day_of_week = [
            {"day": name, "count": dow_counts[i], "pct": round(dow_counts[i] / total * 100, 1)}
            for i, name in enumerate(_DAY_NAMES)
        ]
        monthly = [
            {"month": name, "count": month_counts[i], "pct": round(month_counts[i] / total * 100, 1)}
            for i, name in enumerate(_MONTH_NAMES)
        ]
        coverage_pct = round(time_covered / total * 100, 1)
        hour_of_day = (
            [
                {"hour": h, "count": hour_counts[h], "pct": round(hour_counts[h] / time_covered * 100, 1)}
                for h in range(24)
                if hour_counts[h] > 0
            ]
            if time_covered > 0
            else []
        )

        weekday_total = sum(dow_counts[0:5])
        weekend_total = sum(dow_counts[5:7])

        return {
            "status": "ok",
            "total_cases": total,
            "day_of_week": day_of_week,
            "weekday_vs_weekend": {
                "weekday_pct": round(weekday_total / total * 100, 1),
                "weekend_pct": round(weekend_total / total * 100, 1),
            },
            "monthly": monthly,
            "hour_of_day": hour_of_day,
            "hour_of_day_coverage_pct": coverage_pct,
        }
