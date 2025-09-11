
from __future__ import annotations
from jinja2 import Template
import json, pathlib

TEMPLATE = Template("""
<!doctype html>
<html><head>
<meta charset="utf-8">
<title>AV-SAFE Report</title>
<style>
body{font-family:system-ui,Arial,sans-serif;padding:2rem;max-width:900px;margin:auto}
h1,h2{margin:0.2rem 0}
.card{border:1px solid #ddd;border-radius:12px;padding:1rem;margin:1rem 0}
code{background:#f3f3f3;padding:2px 4px;border-radius:4px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:0.5rem;text-align:left}
.flag{color:#b30;font-weight:600}
</style>
</head><body>
<h1>AV-SAFE Audit Report</h1>
<div class="card">
  <h2>Summary</h2>
  <p>Minutes: {{res.n_minutes}}</p>
  {% if res.flags %}
    <p class="flag">Flags:</p>
    <ul>{% for f in res.flags %}<li>{{f}}</li>{% endfor %}</ul>
  {% else %}
    <p>No flags.</p>
  {% endif %}
</div>

<div class="card">
  <h2>Noise</h2>
  <p>LAeq limit (dB): {{res.noise.limit_db}} — Mean LAeq: {{'%.1f'|format(res.noise.mean_laeq or 0)}} — % over limit: {{'%.1f'|format(res.noise.pct_over)}}</p>
</div>

<div class="card">
  <h2>Flicker</h2>
  <p>Minutes evaluated: {{res.flicker.evaluated}} — Violations: {{res.flicker.violations}} ({{'%.1f'|format(res.flicker.pct_violations)}}%)</p>
</div>

<div class="card">
  <h2>Integrity (hash chain)</h2>
  <table><tr><th>#</th><th>Timestamp</th><th>Chain hash</th><th>Signed?</th></tr>
  {% for m in minutes[:200] %}
    <tr><td>{{m.idx}}</td><td>{{m.ts}}</td><td><code>{{m.chain.hash[:16]}}…</code></td><td>{{ '✓' if m.chain.signature_hex else '—' }}</td></tr>
  {% endfor %}
  </table>
  {% if minutes|length > 200 %}<p>Showing first 200 of {{minutes|length}} minutes.</p>{% endif %}
</div>
</body></html>
""")

def render(minutes_path: str, results_path: str, out_html: str) -> None:
    minutes = [json.loads(line) for line in open(minutes_path,'r',encoding='utf-8') if line.strip()]
    res = json.loads(open(results_path,'r',encoding='utf-8').read())
    html = TEMPLATE.render(minutes=minutes, res=res)
    pathlib.Path(out_html).write_text(html, encoding='utf-8')
