# Research and dependency register

| Resource | Gap / assessment | License / maintenance / risk | Decision |
|---|---|---|---|
| FastAPI (`fastapi.tiangolo.com`) | Maintained API framework already used | MIT; active; upgrade tested | Adopt upgraded 0.141.1 |
| Kite Connect Python (`github.com/zerodha/pykiteconnect`) | Broker REST/WebSocket boundary | MIT; maintained, but 5.2.2 pins vulnerable Autobahn 19.11.2 | REST-only supervised use; reject WebSocket enablement until resolved |
| pip-audit (`github.com/pypa/pip-audit`) | Python advisory scanning | Apache-2.0; PyPA maintained | Adopt as release gate |
| npm audit | Frontend dependency advisory scanning | npm ecosystem tool | Adopt as release gate |
| NSE holiday calendar | Session correctness | Runtime operator-managed file; provenance not automatically verified | Adapt with fail-closed validation; require operator review |

No external strategy code was copied. No new runtime framework was introduced. Expected measurable benefit is fewer false paper entries from incomplete candles/illiquid quotes and reproducible journal evidence; no profitability claim is made.
