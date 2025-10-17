from __future__ import annotations
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse
import json

from oubon_os.core.db import recent_events, latest_forecast

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    events = recent_events(limit=20)
    fpoints = latest_forecast(limit=14)

    def fmt_evt(row):
        try:
            d = json.loads(row["details"] or "{}")
        except Exception:
            d = {"raw": row["details"]}
        return f"""
        <tr>
          <td>{row['id']}</td>
          <td>{row['ts']}</td>
          <td>{row['source']}</td>
          <td>{row['type']}</td>
          <td><pre style="white-space: pre-wrap; margin:0">{json.dumps(d, ensure_ascii=False)[:400]}</pre></td>
        </tr>
        """

    def fmt_fc(row):
        return f"""
        <tr>
          <td>{row['ts']}</td>
          <td>{row['sku']}</td>
          <td>{row['yhat']:.2f}</td>
          <td>{row['p10']:.2f}</td>
          <td>{row['p50']:.2f}</td>
          <td>{row['p90']:.2f}</td>
        </tr>
        """

    return f"""
    <html>
      <head>
        <title>Oubon Admin</title>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding:20px; }}
          table {{ border-collapse: collapse; width: 100%; }}
          th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; }}
          th {{ background: #f4f5f7; text-align: left; }}
          h1 {{ margin: 0 0 12px; }}
          .grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
          .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
        </style>
      </head>
      <body>
        <h1>Oubon Admin</h1>
        <div class="grid">
          <div class="card">
            <h2>Recent Events</h2>
            <table>
              <thead><tr><th>ID</th><th>Timestamp (UTC)</th><th>Source</th><th>Type</th><th>Details</th></tr></thead>
              <tbody>
                {''.join(fmt_evt(r) for r in events)}
              </tbody>
            </table>
          </div>
          <div class="card">
            <h2>Latest Forecast (any SKU)</h2>
            <table>
              <thead><tr><th>TS</th><th>SKU</th><th>yhat</th><th>p10</th><th>p50</th><th>p90</th></tr></thead>
              <tbody>
                {''.join(fmt_fc(r) for r in fpoints)}
              </tbody>
            </table>
          </div>
          <div class="card">
            <h2>Quick Links</h2>
            <ul>
              <li><a href="/health">/health</a></li>
              <li><a href="/admin/logs?limit=20">/admin/logs (JSON)</a></li>
              <li><a href="/admin/dashboard">/admin/dashboard (you are here)</a></li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """


@router.get("/logs")
def logs(limit: int = Query(default=50, ge=1, le=500)):
    rows = recent_events(limit=limit)
    items = []
    for r in rows:
        try:
            d = json.loads(r["details"] or "{}")
        except Exception:
            d = {"raw": r["details"]}
        items.append({
            "id": r["id"],
            "ts": r["ts"],
            "source": r["source"],
            "type": r["type"],
            "details": d
        })
    return JSONResponse({"ok": True, "count": len(items), "items": items})
