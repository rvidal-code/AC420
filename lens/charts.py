import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from lens.financials import bridge

NAMES = ["EBITDA bridge", "Revenue segmentation", "Stock price", "Debt maturities", "Revenue & profitability", "Free cash flow", "Liquidity & leverage"]
TEAL, BLUE, RED = "#22b8a8", "#69a8ff", "#f17f87"


def style(fig, money=True):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=25, b=25), height=390, font=dict(family="Arial", color="#dce6f3"),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    if money:
        fig.update_yaxes(title="USD millions", gridcolor="#243047", zerolinecolor="#46526a")
    return fig


def build(name, history, current, previous, segments, maturities, prices):
    v = current["values"]
    if name == "EBITDA bridge":
        data = bridge(previous, current) if previous else None
        if not data:
            return None, None
        fig = go.Figure(go.Waterfall(x=data["labels"], y=[n / 1e6 for n in data["values"]],
            measure=["absolute"] + ["relative"] * 4 + ["total"], increasing=dict(marker_color=TEAL), decreasing=dict(marker_color=RED), totals=dict(marker_color=BLUE)))
        return style(fig), {"previous_period": previous["end"], "previous_EBITDA_USD": previous["values"]["EBITDA"],
                            "current_period": current["end"], "current_EBITDA_USD": current["values"]["EBITDA"],
                            "component_changes_USD": {key: current["values"][key] - previous["values"][key] for key in ("Net income", "Interest", "Taxes", "D&A")},
                            "meaning": "Each component is a period-over-period CHANGE, not its absolute balance. Endpoints are EBITDA, not net income."}
    if name == "Revenue segmentation":
        if not segments:
            return None, None
        fig = go.Figure(go.Treemap(labels=["Revenue"] + [s["segment"] for s in segments],
            parents=[""] + ["Revenue"] * len(segments), values=[sum(s["value"] for s in segments)] + [s["value"] for s in segments],
            branchvalues="total", textinfo="label+percent parent", marker=dict(colors=[BLUE] + [TEAL] * len(segments))))
        return style(fig, False), segments
    if name == "Stock price":
        if not prices:
            return None, None
        frame = pd.DataFrame(prices)
        fig = px.line(frame, x="date", y="close", color_discrete_sequence=[TEAL])
        fig.update_yaxes(title="USD / share (unadjusted close)")
        return style(fig, False), {"start": prices[0], "end": prices[-1], "observations": len(prices)}
    if name == "Debt maturities":
        if not maturities:
            return None, None
        frame = pd.DataFrame(maturities)
        frame["USD millions"] = frame["value"] / 1e6
        return style(px.bar(frame, x="maturity", y="USD millions", color_discrete_sequence=[BLUE])), maturities
    if name == "Free cash flow":
        if any(v.get(k) is None for k in ("Operating cash flow", "Capital expenditures")):
            return None, None
        data = {k: v[k] for k in ("Operating cash flow", "Capital expenditures", "Free cash flow")}
        fig = go.Figure(go.Waterfall(x=list(data), y=[v["Operating cash flow"] / 1e6, -v["Capital expenditures"] / 1e6, v["Free cash flow"] / 1e6],
            measure=["absolute", "relative", "total"], increasing=dict(marker_color=TEAL), decreasing=dict(marker_color=RED), totals=dict(marker_color=BLUE)))
        return style(fig), data
    keys = ["Revenue", "Operating income", "Net income"] if name == "Revenue & profitability" else ["Cash", "Debt", "Net debt"]
    records = [{"Period ended": p["end"], "Metric": k, "USD millions": p["values"][k] / 1e6}
               for p in reversed(history) for k in keys if p["values"].get(k) is not None]
    if not records or not any(v.get(k) is not None for k in keys):
        return None, None
    fig = px.line(pd.DataFrame(records), x="Period ended", y="USD millions", color="Metric", markers=True,
                  color_discrete_sequence=[TEAL, BLUE, RED])
    return style(fig), records
