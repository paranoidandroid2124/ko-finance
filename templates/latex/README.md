# LaTeX Daily Brief Prototype

`templates/latex/main.tex.jinja` is the Jinja2 template for the **AI Daily Brief** PDF that will go out to Pro/Enterprise customers each morning. The layout skips a cover page and opens directly with signal cards, alerts/actions, evidence, and pipeline metrics.

## Payload Schema
The FastAPI/RAG pipeline should emit JSON that follows (or extends) this structure. Each section honours `report.top_n`: items beyond the cap automatically move to the appendix.

```jsonc
{
  "report": {
    "title": "AI Market Signals",
    "date": "2025-11-04",
    "headline": "Contract-related filings and KOGL policy updates occurred simultaneously.",
    "top_n": {
      "signals": 6,
      "alerts": 3,
      "actions": 2,
      "evidence": 4,
      "metrics": 5,
      "notes": 4
    }
  },
  "signals": [
    {
      "label": "OpenDART filings (24h)",
      "value": "86",
      "delta": "+18 vs D-1",
      "note": "Includes correction filings; three large contracts detected.",
      "severity": "primary"
    }
  ],
  "alerts": [
    {
      "title": "Contract watch",
      "body": "Two corrected filings and one new contract hit the same value chain.",
      "severity": "warn"
    }
  ],
  "actions": [
    {
      "title": "Immediate actions",
      "ordered": true,
      "items": [
        "Create 48h follow-up alerts for the three contract counterparties.",
        "Pin KOGL policy summaries to the dashboard header."
      ]
    }
  ],
  "evidence": [
    {
      "source": "OpenDART",
      "date": "2025-11-04",
      "title": "Correction: large-scale supply contract",
      "body": "Watchlist member B - revenue exposure 28%; supplier diversification risk.",
      "trace_id": "trace-123",
      "url": "https://dart.fss.or.kr/..."
    }
  ],
  "metrics": [
    {"label": "Reindex p50", "current": "27 min", "delta": "-5 min"}
  ],
  "notes": [
    "All insights include TraceIDs, enabling reproducibility.",
    "Policy classification Precision@K remains at 0.93; recheck scheduled in the evening batch."
  ],
  "appendix": {
    "sections": [
      {
        "title": "Positive filings",
        "type": "list",
        "items": ["Company D - new investment plan", "Company E - overseas order win"]
      }
    ]
  },
  "links": {
    "policy_digest_url": "https://...",
    "alert_id": "alert-001",
    "trace_id": "trace-999",
    "evidence_manifest_id": "manifest-abc"
  },
  "charts": {
    "sla_trend": {
      "path": "assets/sla_trend.pdf",
      "x": ["D-2", "D-1", "Today"],
      "series": [
        {"label": "p50", "values": [32, 29, 27]},
        {"label": "p95", "values": [52, 47, 44]}
      ]
    }
  }
}
```

## Rendering Pipeline
1. **Validate & prepare** - `scripts/render_daily_brief.py` loads the payload, checks required fields (`report.title`, `signals`, `evidence`, etc.), splits sections by `top_n`, and builds appendix sections for overflow items.
2. **Chart assets** - If chart metadata is provided, the script tries to render a simple line chart (Matplotlib). When Matplotlib is unavailable it simply keeps the declared path; the LaTeX template wraps chart inclusion in `\IfFileExists` so the page still renders.
3. **Render & compile** - The script feeds the context into `main.tex.jinja`, writes `daily_brief.tex`, and optionally runs `latexmk -lualatex`.

Example:
```bash
python scripts/render_daily_brief.py \
    --input templates/latex/sample_payload.json \
    --output-dir build/daily_brief \
    --compile
```
This creates `build/daily_brief/daily_brief.tex` (and a PDF when `--compile` is provided). Static assets and fonts from `templates/latex/` are copied into the build directory before compilation.

## Template Notes
- Text values are LaTeX-escaped by the renderer; avoid injecting raw TeX unless unavoidable.
- Actions support ordered (`ordered=true`) and unordered lists.
- Appendix sections support `list`, `cards`, and `table`; overflow data is converted automatically.
- Charts expect relative paths (e.g. `assets/sla_trend.pdf`). The renderer will create directories and try to generate placeholders.

## Next Steps
1. Wire the renderer into the actual RAG worker so live payloads generate PDFs.
2. Enrich appendix formats (e.g. positive/negative filings tables, watchlist deep dives).
3. Replace placeholder charts with richer visualisations when data quality improves.
4. Add the renderer to CI/CD (Phase 5 Step 5) so a sample payload compiles on every merge.

> Tip: run `python scripts/render_daily_brief.py --help` for CLI options. The script fails fast when required fields are missing, surfacing payload issues before TeX compilation.
