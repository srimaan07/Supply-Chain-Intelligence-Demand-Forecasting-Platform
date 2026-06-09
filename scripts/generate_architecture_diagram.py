#!/usr/bin/env python3
"""Generate architecture diagram for the platform."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUTPUT = Path(__file__).resolve().parent.parent / "architecture_diagram.png"


def draw_box(ax, x, y, w, h, text, color, fontsize=9):
    box = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.05",
        facecolor=color, edgecolor="#333333", linewidth=1.5, alpha=0.9
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", wrap=True)


def draw_arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#555555", lw=1.5))


def main():
    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Supply Chain Intelligence Platform - Architecture",
                 fontsize=16, fontweight="bold", pad=20)

    # Data Sources
    draw_box(ax, 0.5, 8, 2.5, 1.2, "Synthetic Data\nGenerator", "#E3F2FD")
    draw_box(ax, 0.5, 6.2, 2.5, 1.2, "CSV Raw Data\n(data/raw/)", "#BBDEFB")

    # ETL
    draw_box(ax, 4, 7, 2.5, 1.5, "ETL Pipeline\n(Pandas)", "#C8E6C9", 10)
    draw_box(ax, 4, 5, 2.5, 1.2, "Data Quality\n& Transform", "#A5D6A7")

    # Database
    draw_box(ax, 7.5, 6.5, 3, 2, "PostgreSQL\nDatabase", "#FFF9C4", 11)

    # Analytics Modules
    draw_box(ax, 11.5, 8.2, 2.5, 1, "KPI Engine", "#FFCCBC")
    draw_box(ax, 11.5, 6.8, 2.5, 1, "Inventory\nIntelligence", "#FFCCBC")
    draw_box(ax, 11.5, 5.4, 2.5, 1, "Supplier\nAnalytics", "#FFCCBC")
    draw_box(ax, 11.5, 4, 2.5, 1, "Logistics\nIntelligence", "#FFCCBC")

    # ML & Optimization
    draw_box(ax, 7.5, 3.5, 2.8, 1.2, "Demand Forecasting\n(ML Models)", "#E1BEE7")
    draw_box(ax, 10.8, 3.5, 2.8, 1.2, "Inventory\nOptimization", "#E1BEE7")

    # Outputs
    draw_box(ax, 0.5, 2.5, 2.5, 1.2, "FastAPI\nREST API", "#B2DFDB")
    draw_box(ax, 3.5, 2.5, 2.5, 1.2, "Power BI\nDashboard", "#B2DFDB")
    draw_box(ax, 6.5, 2.5, 2.5, 1.2, "Insights\nEngine", "#B2DFDB")
    draw_box(ax, 9.5, 2.5, 2.5, 1.2, "Reports &\nAlerts", "#B2DFDB")
    draw_box(ax, 12.5, 2.5, 2.5, 1.2, "SQL Analytics\n(40+ Queries)", "#B2DFDB")

    # Docker
    draw_box(ax, 5, 0.5, 6, 1.2, "Docker Compose (PostgreSQL + API + Pipeline)", "#CFD8DC", 10)

    # Arrows
    draw_arrow(ax, 3, 8.6, 4, 7.8)
    draw_arrow(ax, 3, 6.8, 4, 7.2)
    draw_arrow(ax, 6.5, 7.5, 7.5, 7.5)
    draw_arrow(ax, 9, 7, 11.5, 8.5)
    draw_arrow(ax, 9, 7, 11.5, 7.2)
    draw_arrow(ax, 9, 6.5, 11.5, 5.8)
    draw_arrow(ax, 9, 6.5, 11.5, 4.5)
    draw_arrow(ax, 9, 6.5, 8.5, 4.5)
    draw_arrow(ax, 9, 6.5, 11.5, 4)
    draw_arrow(ax, 8.5, 3.5, 8.5, 3.7)
    draw_arrow(ax, 10.5, 3.5, 10.5, 3.7)
    draw_arrow(ax, 9, 6.5, 1.75, 3.7)
    draw_arrow(ax, 9, 6.5, 4.75, 3.7)
    draw_arrow(ax, 9, 6.5, 7.75, 3.7)
    draw_arrow(ax, 9, 6.5, 10.75, 3.7)
    draw_arrow(ax, 9, 6.5, 13.75, 3.7)

    # Legend
    legend_items = [
        mpatches.Patch(color="#E3F2FD", label="Data Layer"),
        mpatches.Patch(color="#C8E6C9", label="Processing"),
        mpatches.Patch(color="#FFF9C4", label="Storage"),
        mpatches.Patch(color="#FFCCBC", label="Analytics"),
        mpatches.Patch(color="#E1BEE7", label="ML/AI"),
        mpatches.Patch(color="#B2DFDB", label="Output"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=8, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(OUTPUT, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Architecture diagram saved to {OUTPUT}")


if __name__ == "__main__":
    main()
