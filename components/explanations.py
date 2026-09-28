"""
components/explanations.py
===========================
Builds the "why" narrative directly from the AssetScore object -- every
sentence traces back to an actual driver score computed from actual entered
data. Nothing here invents a claim that isn't already in top_bullish /
top_bearish / conflict_note.
"""

from config import ASSET_NAMES
from data_model import AssetScore


def build_summary(asset_score: AssetScore) -> str:
    name = ASSET_NAMES.get(asset_score.asset, asset_score.asset)
    lines = []
    lines.append(
        f"{name} ({asset_score.asset}) is fundamentally **{asset_score.bias.upper()}** "
        f"on a {asset_score.horizon.split(' (')[0].lower()} view, scoring {asset_score.final_score:+.1f} "
        f"(confidence {asset_score.confidence:.0f}%)."
    )

    if asset_score.top_bullish:
        lines.append("\n**Primarily driven higher by:**")
        for i, d in enumerate(asset_score.top_bullish, 1):
            lines.append(f"{i}. {d.label}: {d.explanation}")

    if asset_score.top_bearish:
        lines.append("\n**Partially offset by:**")
        for i, d in enumerate(asset_score.top_bearish, 1):
            lines.append(f"{i}. {d.label}: {d.explanation}")

    if asset_score.conflict_note:
        lines.append(f"\n**Note:** {asset_score.conflict_note} "
                      f"(Fundamental Alignment Score: {asset_score.alignment:.0f}%).")
    else:
        lines.append(f"\nMajor categories are broadly aligned with this direction "
                      f"(Fundamental Alignment Score: {asset_score.alignment:.0f}%).")

    if asset_score.data_coverage < 70:
        lines.append(f"\n**Caution:** only {asset_score.data_coverage:.0f}% of the model's weight is currently "
                      f"backed by entered data -- fill in more inputs for a more reliable read.")

    return "\n".join(lines)


def biggest_risks(asset_score: AssetScore):
    """Biggest risks to the current thesis = the strongest opposing-direction
    drivers, plus any crowding flags."""
    risks = []
    opposing = asset_score.top_bearish if asset_score.final_score >= 0 else asset_score.top_bullish
    for d in opposing[:3]:
        risks.append(f"{d.label} ({d.score:+.1f}): {d.explanation}")
    crowded = [d for c in asset_score.categories for d in c.drivers if d.crowding_flag]
    for d in crowded:
        risks.append(f"Positioning crowding risk -- {d.label}: {d.explanation}")
    if asset_score.data_coverage < 70:
        risks.append(f"Data coverage is only {asset_score.data_coverage:.0f}% -- the score may shift materially "
                      f"as more inputs are added.")
    return risks
