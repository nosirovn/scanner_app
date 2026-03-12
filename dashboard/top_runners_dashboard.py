"""Simple HTML renderer for top runners dashboard."""

from __future__ import annotations

from typing import Dict, List


def render_dashboard(rows: List[Dict]) -> str:
    trs = []
    for row in rows[:10]:
        trs.append(
            "<tr>"
            f"<td>{row.get('ticker','')}</td>"
            f"<td>${row.get('price',0):.2f}</td>"
            f"<td>{row.get('percent_change',0):+.2f}%</td>"
            f"<td>{row.get('relative_volume',0):.2f}x</td>"
            f"<td>{row.get('momentum_score',0):.2f}</td>"
            f"<td>{row.get('runner_score',0):.2f}</td>"
            f"<td>{row.get('pattern','None')}</td>"
            f"<td>{(row.get('trade_setup') or {}).get('setup','-')}</td>"
            "</tr>"
        )

    body = "".join(trs) if trs else "<tr><td colspan='8'>No runners yet</td></tr>"
    return f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Top Runners</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f7fb; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 14px; }}
    th {{ background: #111827; color: #fff; }}
    h1 {{ margin: 0 0 16px 0; font-size: 22px; }}
  </style>
</head>
<body>
  <h1>Top 10 Runners ($0-$20)</h1>
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Price</th>
        <th>Change %</th>
        <th>Relative Volume</th>
        <th>Momentum Score</th>
        <th>Runner Score</th>
        <th>Pattern</th>
        <th>Trade Setup</th>
      </tr>
    </thead>
    <tbody>{body}</tbody>
  </table>
</body>
</html>
"""
