"""Portable offline report with SVG. No network, trained model files or private data."""
import json
from pathlib import Path
from html import escape

def chart_svg(bars, lines, start, horizon=24, width=1000, height=380):
    sample=bars.iloc[start:];lo=float(sample.low.min());hi=float(sample.high.max())
    x=lambda i:45+(i-start)/max(1,len(sample)-1)*(width-65)
    y=lambda v:height-30-(v-lo)/max(hi-lo,1e-9)*(height-55)
    points=" ".join(f"{x(i):.1f},{y(float(bars.close.iloc[i])):.1f}" for i in range(start,len(bars)))
    elements=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Synthetic closing prices and causal candidate lines">',
        '<rect width="100%" height="100%" fill="#111827"/>',f'<polyline points="{points}" fill="none" stroke="#d1d5db" stroke-width="1.5"/>']
    visible=[l for l in lines if l.discovered_at>=start][-18:]
    for line in visible:
        end=min(len(bars)-1,line.discovered_at+horizon)
        color="#34d399" if line.side=="support" else "#fb7185"
        # Only draw from availability onward; anchors are not retrospectively tradable.
        elements.append(f'<line x1="{x(line.discovered_at):.1f}" y1="{y(line.value(line.discovered_at)):.1f}" x2="{x(end):.1f}" y2="{y(line.value(end)):.1f}" stroke="{color}" opacity=".65"><title>{escape(line.line_id)}</title></line>')
    elements.append('</svg>')
    return "".join(elements)

def write_report(output, report, bars, lines):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    svg=chart_svg(bars,lines,report['split_index'],report['label_horizon'])
    (output/'chart.svg').write_text(svg,encoding='utf-8')
    baseline=report['backtests']['baseline'];ml=report['backtests']['ml']
    md=f"""# 市场状态过滤器 research report

Evidence source: **{report['evidence_source']}**. This is an engineering demonstration, not performance evidence.

- Bars: {report['bars']}; temporal holdout starts at index {report['split_index']}.
- Candidates: {report['candidate_count']}; mature labels: {report['mature_count']}.
- Training samples: {report['model']['train_count']}; holdout samples: {report['model']['holdout_count']}.
- Holdout Brier score: {report['model']['brier']:.4f}; constant training-rate baseline: {report['model']['constant_baseline_brier']:.4f}.
- Capped duration MAE: {report['model']['capped_duration_mae']:.2f} bars.
- Public rule-score return: {baseline['net_return']:.2%}; ML-score return: {ml['net_return']:.2%}.
- Trades: rule-score {baseline['trade_count']}, ML-score {ml['trade_count']}.

The duration target is capped at the label horizon, including right-censored survivors. It is not an estimate of unlimited line lifetime. Model scores are not independently calibrated probabilities. Adjacent line samples overlap, so metrics are descriptive, not independent statistical evidence. This run cannot establish that ML improves trading.

Backtests use the same strategy and cost assumptions. Only the scorer changes. Long-only support bounce, next-open fills, 10% capital allocation, stop-first handling when both stop and target occur in one bar, explicit fees and slippage; no leverage or funding model. One temporal holdout, no optimization or automatic promotion.
"""
    (output/'report.md').write_text(md,encoding='utf-8')
    cards=f"<p>Source: <strong>{escape(report['evidence_source'])}</strong> · {report['bars']} bars · {report['candidate_count']} candidates</p>"
    table='<table><tr><th>Scorer</th><th>Net return</th><th>Drawdown</th><th>Trades</th></tr>'
    for name,result in report['backtests'].items():
        table+=f"<tr><td>{escape(name)}</td><td>{result['net_return']:.2%}</td><td>{result['max_drawdown']:.2%}</td><td>{result['trade_count']}</td></tr>"
    table+='</table>'
    html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>市场状态过滤器 report</title><style>body{font:16px system-ui;background:#0b1020;color:#e5e7eb;max-width:1000px;margin:40px auto;padding:20px}table{border-collapse:collapse;width:100%;margin:25px 0}td,th{padding:14px;text-align:left;border-bottom:1px solid #374151}svg{width:100%}aside{background:#25304a;padding:20px;border-radius:12px}h1{color:#a7f3d0}</style><h1>市场状态过滤器</h1><p>Causal line quality · temporal validation · strategy comparison</p>'+cards+svg+table+'<aside>Synthetic demo or local research only. No exchange orders. These results do not establish predictive edge, calibrated probabilities, or profitability. See report.md for assumptions.</aside></html>'
    (output/'report.html').write_text(html,encoding='utf-8')
