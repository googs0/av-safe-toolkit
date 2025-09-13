# avsafe_descriptors/report/render_html.py
from __future__ import annotations

import json
import pathlib
from datetime import datetime
from typing import Dict, Any, List, Tuple

from jinja2 import Environment, Template, select_autoescape

# Chain & canonicalization
from ..integrity.hash_chain import chain_hash, canonical_json

# Optional Ed25519 verification (PyNaCl)
try:
    from nacl.signing import VerifyKey
    HAVE_NACL = True
except Exception:  # pragma: no cover
    HAVE_NACL = False

# --------------------------
# Template (inline)
# --------------------------
_HTML_TMPL = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>AV-SAFE Audit Report</title>
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <style>
      :root{
        --bg: #ffffff;
        --fg: #1b1f23;
        --muted: #6a737d;
        --card: #fafbfc;
        --border: #e1e4e8;
        --accent: #005fcc;
        --flag: #b03030;
        --ok: #1b8a4a;
        --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      }
      @media (prefers-color-scheme: dark) {
        :root{
          --bg: #111418;
          --fg: #eaeaea;
          --muted: #a0a7b0;
          --card: #161a20;
          --border: #2a2f36;
          --accent: #6bb6ff;
          --flag: #ff6b6b;
          --ok: #73d99f;
        }
      }
      html,body{background:var(--bg);color:var(--fg)}
      body{font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,"Helvetica Neue",Arial,sans-serif;margin:0;padding:2rem}
      .wrap{max-width:980px;margin:0 auto}
      h1{font-size:1.75rem;margin:.2rem 0 .8rem}
      h2{font-size:1.1rem;margin:0 0 .6rem;letter-spacing:.02em;text-transform:uppercase;color:var(--muted)}
      .meta{color:var(--muted);font-size:.9rem}
      .grid{display:grid;grid-template-columns:1fr;gap:1rem}
      @media (min-width: 900px){.grid{grid-template-columns:1fr 1fr}}
      .card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1rem}
      .flag{color:var(--flag);font-weight:600}
      .ok{color:var(--ok);font-weight:600}
      table{border-collapse:collapse;width:100%;font-size:.92rem}
      th,td{border:1px solid var(--border);padding:.45rem .5rem;text-align:left;vertical-align:top}
      code,pre{font-family:var(--mono);background:transparent;color:var(--fg)}
      .pill{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:.15rem .5rem;font-size:.85rem;margin-right:.25rem}
      .mono{font-family:var(--mono)}
      .truncate{max-width:360px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
      .footer{color:var(--muted);font-size:.85rem;margin-top:1.25rem}
      .small{font-size:.9rem}
      .muted{color:var(--muted)}
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>AV-SAFE Audit Report</h1>
      <div class="meta">
        Generated: {{ now_iso }}
        {% if meta.profile_id %} · Profile: <span class="mono">{{ meta.profile_id }}</span>{% endif %}
        {% if meta.rules_version %} · Rules: {{ meta.rules_version }}{% endif %}
      </div>

      <section class="card">
        <h2>Verification</h2>
        <p class="{{ 'ok' if verify.chain.ok and verify.sigs.invalid == 0 and verify.sigs.unverified == 0 else 'flag' }}">
          {{ verify.verdict }}
        </p>
        <p class="small muted">
          Chain: {{ 'contiguous' if verify.chain.ok else 'breaks @ ' ~ verify.chain.break_indices | join(', ') }}
          · Minutes: {{ verify.chain.n }}
          · Signatures: {{ verify.sigs.valid }}/{{ verify.sigs.total }} valid{% if verify.sigs.invalid %}, {{ verify.sigs.invalid }} invalid{% endif %}{% if verify.sigs.missing %}, {{ verify.sigs.missing }} missing{% endif %}{% if verify.sigs.unverified %}, {{ verify.sigs.unverified }} unverified (no crypto){% endif %}.
        </p>
      </section>

      <div class="grid">
        <section class="card">
          <h2>Summary</h2>
          <div class="small">
            <div>Minutes: <strong>{{ summary.n_minutes }}</strong>
              {% if summary.range %} · idx {{ summary.range.idx_min }}–{{ summary.range.idx_max }}{% endif %}
              {% if summary.ts_first %} · {{ summary.ts_first }} → {{ summary.ts_last }}{% endif %}
            </div>
            <div>
              Flags:
              {% if flags %}
                {% for f in flags %}<span class="pill flag">{{ f }}</span>{% endfor %}
              {% else %}
                <span class="ok">None</span>
              {% endif %}
            </div>
          </div>
        </section>

        <section class="card">
          <h2>Integrity</h2>
          <div class="small">
            <div>Signed minutes: <strong>{{ integrity.signed_count }}</strong> / {{ summary.n_minutes }}
                ({{ "%.1f"|format(integrity.signed_pct) }}%)</div>
            {% if integrity.schemes %}
              <div>Schemes:
                {% for s, n in integrity.schemes.items() %}
                  <span class="pill">{{ s }}: {{ n }}</span>
                {% endfor %}
              </div>
            {% endif %}
            {% if integrity.first_hash %}
              <div>First hash: <code class="mono">{{ integrity.first_hash }}</code></div>
              <div>Last hash: <code class="mono">{{ integrity.last_hash }}</code></div>
            {% endif %}
          </div>
        </section>
      </div>

      <section class="card">
        <h2>Noise (WHO-aligned)</h2>
        <div class="small">
          <div>Limit (dB): <strong>{{ noise.limit_db if noise.limit_db is not none else "—" }}</strong>
              · Mean LAeq: <strong>{{ "%.1f"|format(noise.mean_laeq or 0) }}</strong>
              · % over limit: <strong>{{ "%.1f"|format(noise.pct_over or 0) }}%</strong></div>
          {% if noise.percentiles %}
            <div>LAeq percentiles:
              {% for k in ["p50","p75","p90","p95"] if k in noise.percentiles %}
                <span class="pill">{{ k }} {{ "%.1f"|format(noise.percentiles[k]) }}</span>
              {% endfor %}
            </div>
          {% endif %}
        </div>
      </section>

      <section class="card">
        <h2>Flicker (IEEE-1789)</h2>
        <div class="small">
          <div>Evaluated: <strong>{{ flicker.evaluated }}</strong>
              · Violations: <strong>{{ flicker.violations }}</strong>
              ({{ "%.1f"|format(flicker.pct_violations or 0) }}%)</div>
          {% if flicker.notes %}<div class="muted">{{ flicker.notes }}</div>{% endif %}
        </div>
      </section>

      <section class="card">
        <h2>Integrity (hash chain view)</h2>
        <table>
          <thead>
            <tr><th>#</th><th>Timestamp</th><th>Chain hash</th><th>Signed?</th><th>Sig OK?</th></tr>
          </thead>
          <tbody>
            {% for m in table_minutes %}
              <tr>
                <td>{{ m.idx }}</td>
                <td class="truncate" title="{{ m.ts }}">{{ m.ts }}</td>
                <td class="mono truncate" title="{{ m.chain.hash }}">{{ m.chain.hash }}</td>
                <td>{{ "✓" if m.chain.signature_hex else "—" }}</td>
                <td>
                  {% if m._sig_status == 'valid' %}<span class="ok">✓</span>
                  {% elif m._sig_status == 'invalid' %}<span class="flag">✗</span>
                  {% elif m._sig_status == 'unverified' %}<span class="muted">—</span>
                  {% else %}<span class="muted">—</span>{% endif %}
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
        {% if summary.n_minutes > table_minutes|length %}
          <p class="muted small">Showing {{ table_minutes|length }} of {{ summary.n_minutes }} minutes (cap {{ table_cap }}).</p>
        {% endif %}
      </section>

      <section class="footer">
        <div>Privacy: AV-SAFE processes <strong>descriptors only</strong> (no raw speech, images, or video).
          Reports are <strong>tamper-evident</strong> via per-minute chain hashes and optional Ed25519 signatures.</div>
        {% if footnote %}<div class="muted">{{ footnote }}</div>{% endif %}
      </section>
    </div>
  </body>
</html>
"""

env = Environment(autoescape=select_autoescape(["html", "xml"]))
TEMPLATE: Template = env.from_string(_HTML_TMPL)


# ---------- Helpers ----------
def _read_head_minutes(path: str, cap: int) -> Tuple[List[dict], int, int]:
    """Read JSONL minutes up to `cap` for table display, and count totals."""
    head: List[dict] = []
    total = 0
    bad = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                rec = json.loads(line)
            except Exception:
                bad += 1
                continue
            if len(head) < cap:
                rec.setdefault("audio", {})
                rec.setdefault("light", {})
                rec.setdefault("chain", {})
                rec["chain"].setdefault("hash", "")
                rec["chain"].setdefault("signature_hex", None)
                head.append(rec)
    return head, total, bad


def _read_all_minutes(path: str) -> List[dict]:
    """Read all minutes (for full chain/signature verification)."""
    out: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rec.setdefault("audio", {})
            rec.setdefault("light", {})
            rec.setdefault("chain", {})
            rec["chain"].setdefault("hash", "")
            rec["chain"].setdefault("signature_hex", None)
            out.append(rec)
    return out


def _safe_get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _summarize_minutes(head: List[dict], total: int) -> Dict[str, Any]:
    idxs = [m.get("idx") for m in head if isinstance(m.get("idx"), int)]
    tss = [m.get("ts") for m in head if isinstance(m.get("ts"), str)]
    summary = {
        "n_minutes": total,
        "range": {"idx_min": min(idxs), "idx_max": max(idxs)} if idxs else None,
        "ts_first": tss[0] if tss else None,
        "ts_last": tss[-1] if tss else None,
    }
    signed_count = sum(1 for m in head if m.get("chain", {}).get("signature_hex"))
    schemes: Dict[str, int] = {}
    for m in head:
        s = m.get("chain", {}).get("scheme")
        if s:
            schemes[s] = schemes.get(s, 0) + 1
    first_hash = head[0]["chain"]["hash"][:16] + "…" if head else None
    last_hash = head[-1]["chain"]["hash"][:16] + "…" if head else None
    integrity = {
        "signed_count": signed_count,
        "signed_pct": (signed_count / total * 100.0) if total else 0.0,
        "schemes": schemes,
        "first_hash": first_hash,
        "last_hash": last_hash,
    }
    return summary, integrity


def _coerce_results(res: Dict[str, Any]) -> Dict[str, Any]:
    noise = {
        "limit_db": _safe_get(res, "noise.limit_db", None),
        "mean_laeq": _safe_get(res, "noise.mean_laeq", 0.0),
        "pct_over": _safe_get(res, "noise.pct_over", 0.0),
        "percentiles": _safe_get(res, "noise.percentiles", None),
    }
    flicker = {
        "evaluated": _safe_get(res, "flicker.evaluated", 0),
        "violations": _safe_get(res, "flicker.violations", 0),
        "pct_violations": _safe_get(res, "flicker.pct_violations", 0.0),
        "notes": _safe_get(res, "flicker.notes", None),
    }
    meta = {
        "profile_id": _safe_get(res, "trace.profile_id", None),
        "rules_version": _safe_get(res, "trace.rules_version", None),
    }
    flags = res.get("flags", []) or []
    return {"noise": noise, "flicker": flicker, "meta": meta, "flags": flags}


def _verify_chain_and_signatures(minutes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify hash chain continuity and Ed25519 signatures (if present).
    Annotates each minute with _sig_status: 'valid'|'invalid'|'missing'|'unverified'.
    """
    prev_hash: str | None = None
    chain_ok = True
    break_indices: List[int] = []

    sig_total = 0
    sig_valid = 0
    sig_invalid = 0
    sig_missing = 0
    sig_unverified = 0

    for i, rec in enumerate(minutes):
        payload = {k: v for k, v in rec.items() if k != "chain"}
        chain = rec.get("chain", {}) or {}
        rec_hash = chain.get("hash")

        # Chain check
        try:
            computed = chain_hash(prev_hash, payload)
        except Exception:
            computed = None

        if not rec_hash or not computed or rec_hash != computed:
            chain_ok = False
            break_indices.append(i)

        prev_hash = rec_hash

        # Default status
        rec["_sig_status"] = "missing"

        # Sig check
        scheme = (chain.get("scheme") or "").lower()
        sig_hex = chain.get("signature_hex")
        pk_hex = chain.get("public_key_hex")

        if scheme == "ed25519" and sig_hex and pk_hex:
            sig_total += 1
            if not HAVE_NACL:
                sig_unverified += 1
                rec["_sig_status"] = "unverified"
                continue
            try:
                vk = VerifyKey(bytes.fromhex(pk_hex))
                sig = bytes.fromhex(sig_hex)
                msg_dom = b"avsafe:sign:v1" + canonical_json(payload).encode("utf-8")
                ok = False
                try:
                    vk.verify(msg_dom, sig)
                    ok = True
                except Exception:
                    # Back-compat: raw payload
                    vk.verify(canonical_json(payload).encode("utf-8"), sig)
                    ok = True
                if ok:
                    sig_valid += 1
                    rec["_sig_status"] = "valid"
            except Exception:
                sig_invalid += 1
                rec["_sig_status"] = "invalid"
        else:
            sig_missing += 1
            rec["_sig_status"] = "missing"

    # Verdict
    if chain_ok:
        chain_part = f"Chain contiguous (n={len(minutes)})"
    else:
        sample = ", ".join(str(x) for x in break_indices[:5])
        more = "" if len(break_indices) <= 5 else f" (+{len(break_indices)-5} more)"
        chain_part = f"Chain breaks @ [{sample}]{more}"

    if sig_total == 0:
        sig_part = "no signatures"
    elif sig_invalid > 0:
        sig_part = f"{sig_valid}/{sig_total} valid, {sig_invalid} invalid"
    elif sig_unverified > 0:
        sig_part = f"{sig_total} signed, but {sig_unverified} unverified (crypto unavailable)"
    else:
        sig_part = f"{sig_valid}/{sig_total} valid"

    verdict = f"{chain_part}; signatures: {sig_part}."

    return {
        "chain": {"ok": chain_ok, "break_indices": break_indices, "n": len(minutes)},
        "sigs": {
            "total": sig_total,
            "valid": sig_valid,
            "invalid": sig_invalid,
            "missing": sig_missing,
            "unverified": sig_unverified,
        },
        "verdict": verdict,
    }


# ---------- Public API ----------
def render(
    minutes_path: str,
    results_path: str,
    out_html: str,
    *,
    max_rows: int = 200,
    footnote: str | None = None,
) -> None:
    """
    Render an HTML audit report with verification (chain & signatures).
    """
    # Read (1) capped head for table, (2) full list for verification
    table_minutes, total, skipped = _read_head_minutes(minutes_path, cap=max_rows)
    all_minutes = _read_all_minutes(minutes_path)

    # Load results (tolerate missing/bad file)
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            results_obj = json.load(f)
    except Exception:
        results_obj = {}

    # Summaries + verification
    summary, integrity = _summarize_minutes(table_minutes, total)
    coerced = _coerce_results(results_obj)
    verify = _verify_chain_and_signatures(all_minutes)

    # Propagate _sig_status to the table copy (match by index if present)
    idx_to_status = {m.get("idx"): m.get("_sig_status") for m in all_minutes}
    for m in table_minutes:
        m["_sig_status"] = idx_to_status.get(m.get("idx"), "missing")

    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    html = TEMPLATE.render(
        now_iso=now_iso,
        summary=summary,
        integrity=integrity,
        noise=coerced["noise"],
        flicker=coerced["flicker"],
        meta=coerced["meta"],
        flags=coerced["flags"],
        verify=verify,
        table_minutes=table_minutes,
        table_cap=max_rows,
        footnote=footnote or (f"{skipped} malformed line(s) skipped during parsing." if skipped else None),
    )
    pathlib.Path(out_html).write_text(html, encoding="utf-8")
