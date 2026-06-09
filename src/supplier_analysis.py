"""
Supplier Performance Analytics Module.

Analyzes supplier reliability, lead times, defect rates,
and generates scorecards with rankings.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)


class SupplierAnalyzer:
    """Supplier performance analysis and scorecard generation."""

    def __init__(self, analysis_date: date | None = None):
        self.analysis_date = analysis_date or date.today()

    def get_supplier_performance(self) -> pd.DataFrame:
        return read_sql("SELECT * FROM v_supplier_performance ORDER BY on_time_pct DESC")

    def get_delayed_suppliers(self, delay_threshold_pct: float = 15) -> pd.DataFrame:
        perf = self.get_supplier_performance()
        perf["delay_rate"] = 100 - perf["on_time_pct"].fillna(0)
        return perf[perf["delay_rate"] >= delay_threshold_pct].sort_values("delay_rate", ascending=False)

    def generate_scorecards(self) -> pd.DataFrame:
        perf = self.get_supplier_performance()

        def grade(score):
            if score >= 95:
                return "A+"
            if score >= 90:
                return "A"
            if score >= 85:
                return "B+"
            if score >= 80:
                return "B"
            if score >= 70:
                return "C"
            return "D"

        records = []
        perf = perf.sort_values("on_time_pct", ascending=False).reset_index(drop=True)
        for rank, (_, row) in enumerate(perf.iterrows(), 1):
            on_time = row["on_time_pct"] if pd.notna(row["on_time_pct"]) else row["reliability_score"]
            records.append({
                "scorecard_date": self.analysis_date,
                "supplier_id": row["supplier_id"],
                "reliability_score": row["reliability_score"],
                "avg_lead_time": row["avg_actual_lead_time"] if pd.notna(row.get("avg_actual_lead_time")) else row["contracted_lead_time"],
                "on_time_pct": round(on_time, 2),
                "defect_rate": row["defect_rate"],
                "overall_grade": grade(on_time),
                "rank_position": rank,
            })

        df = pd.DataFrame(records)
        execute_sql("DELETE FROM supplier_scorecards WHERE scorecard_date = :d", {"d": self.analysis_date})
        bulk_insert_dataframe(df, "supplier_scorecards")
        logger.info("Generated scorecards for %d suppliers", len(df))
        return df

    def format_scorecard(self, supplier_id: str) -> str:
        query = """
            SELECT s.supplier_name, sc.*
            FROM supplier_scorecards sc
            JOIN suppliers s ON sc.supplier_id = s.supplier_id
            WHERE sc.supplier_id = :sid
            ORDER BY sc.scorecard_date DESC LIMIT 1
        """
        result = read_sql(query, {"sid": supplier_id})
        if result.empty:
            return f"No scorecard found for supplier {supplier_id}"

        row = result.iloc[0]
        return (
            f"Supplier: {row['supplier_name']}\n\n"
            f"Reliability Score: {row['reliability_score']}\n"
            f"Average Lead Time: {row['avg_lead_time']:.0f} Days\n"
            f"On-Time Deliveries: {row['on_time_pct']:.0f}%\n"
            f"Defect Rate: {row['defect_rate']*100:.2f}%\n"
            f"Overall Grade: {row['overall_grade']}\n"
            f"Rank: #{row['rank_position']}"
        )

    def rank_suppliers(self, top_n: int = 20) -> pd.DataFrame:
        return self.get_supplier_performance().head(top_n)

    def summary(self) -> dict[str, Any]:
        perf = self.get_supplier_performance()
        delayed = self.get_delayed_suppliers()
        return {
            "total_suppliers": len(perf),
            "avg_on_time_pct": float(perf["on_time_pct"].mean()),
            "avg_lead_time": float(perf["avg_actual_lead_time"].mean()),
            "high_risk_suppliers": len(delayed),
            "top_supplier": perf.iloc[0]["supplier_name"] if len(perf) else None,
            "worst_supplier": perf.iloc[-1]["supplier_name"] if len(perf) else None,
        }


def analyze_suppliers(analysis_date: date | None = None) -> dict[str, Any]:
    analyzer = SupplierAnalyzer(analysis_date)
    scorecards = analyzer.generate_scorecards()
    return {
        "summary": analyzer.summary(),
        "scorecards_generated": len(scorecards),
        "top_suppliers": analyzer.rank_suppliers(10).to_dict(orient="records"),
        "delayed_suppliers": analyzer.get_delayed_suppliers().head(10).to_dict(orient="records"),
    }
