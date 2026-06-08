"""Build a single self-contained, searchable HTML dashboard from a summaries CSV.

No server needed — data is embedded inline, so it opens with a double-click.
Full-text search box + clickable theme facets + a duplicate-title flag.
"""
from __future__ import annotations
import os, csv, json, html
from collections import Counter

from .config import Config

_TMPL = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
 :root{--bg:#0f1714;--card:#1b2925;--ink:#e8efe9;--mut:#8aa39a;--line:#26352f;--acc:#3fae7a}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 header{padding:18px 24px;border-bottom:1px solid var(--line)}
 h1{margin:0;font-size:18px} .sub{color:var(--mut);font-size:13px;margin-top:4px}
 .wrap{max-width:1000px;margin:0 auto;padding:20px 24px}
 #q{width:100%;padding:11px 14px;background:var(--card);border:1px solid var(--line);
    border-radius:10px;color:var(--ink);font-size:15px}
 .facets{margin:14px 0;display:flex;flex-wrap:wrap;gap:7px}
 .facet{font-size:12.5px;color:var(--mut);border:1px solid var(--line);padding:4px 10px;
   border-radius:20px;cursor:pointer;user-select:none}
 .facet.on{background:var(--acc);color:#04130c;border-color:var(--acc);font-weight:600}
 .card{background:var(--card);border:1px solid var(--line);border-radius:10px;
   padding:14px 16px;margin:10px 0}
 .card h3{margin:0 0 6px;font-size:14.5px;font-weight:600}
 .card p{margin:0;color:#cfe0d7}
 .tags{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}
 .tag{font-size:11.5px;color:var(--mut);border:1px solid var(--line);padding:2px 8px;border-radius:12px}
 .dup{color:#e0a23f;font-size:11px;margin-left:8px}
 .count{color:var(--mut);font-size:13px;margin:8px 0}
</style></head><body>
<header><div class=wrap style="padding:0"><h1>__TITLE__</h1>
<div class=sub>__N__ documents · local summaries · search + filter</div></div></header>
<div class=wrap>
 <input id=q placeholder="Search summaries, titles, themes…" autocomplete=off>
 <div class=facets id=facets></div>
 <div class=count id=count></div>
 <div id=list></div>
</div>
<script>
const DATA = __DATA__;
const facetEl=document.getElementById('facets'),listEl=document.getElementById('list'),
      qEl=document.getElementById('q'),countEl=document.getElementById('count');
const active=new Set();
const themeCounts={};
DATA.forEach(d=>(d.themes||'').split(',').map(t=>t.trim()).filter(Boolean)
  .forEach(t=>themeCounts[t]=(themeCounts[t]||0)+1));
const topThemes=Object.entries(themeCounts).sort((a,b)=>b[1]-a[1]).slice(0,30);
topThemes.forEach(([t,n])=>{const el=document.createElement('span');el.className='facet';
  el.textContent=`${t} (${n})`;el.onclick=()=>{el.classList.toggle('on');
  active.has(t)?active.delete(t):active.add(t);render();};facetEl.appendChild(el);});
function render(){const q=qEl.value.toLowerCase();
  const rows=DATA.filter(d=>{
    const blob=((d.title||'')+' '+(d.summary||'')+' '+(d.themes||'')).toLowerCase();
    if(q&&!blob.includes(q))return false;
    for(const t of active){if(!(d.themes||'').toLowerCase().includes(t.toLowerCase()))return false;}
    return true;});
  countEl.textContent=`${rows.length} of ${DATA.length} shown`;
  listEl.innerHTML=rows.map(d=>{
    const tags=(d.themes||'').split(',').map(t=>t.trim()).filter(Boolean)
      .map(t=>`<span class=tag>${t}</span>`).join('');
    return `<div class=card><h3>${esc(d.title)}${d.dup?'<span class=dup>⚠ possible duplicate</span>':''}</h3>
      <p>${esc(d.summary)}</p><div class=tags>${tags}</div></div>`;}).join('');
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
qEl.oninput=render;render();
</script></body></html>"""


def build_dashboard(cfg: Config, csv_path: str, out_html: str | None = None,
                    title: str | None = None) -> str:
    csv_path = os.path.expanduser(csv_path)
    rows = []
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    # flag likely duplicate titles
    title_counts = Counter(r.get("title", "") for r in rows)
    data = [{"title": r.get("title", ""), "summary": r.get("summary", ""),
             "themes": r.get("themes", ""),
             "dup": title_counts[r.get("title", "")] > 1} for r in rows]

    out_html = out_html or os.path.join(os.path.dirname(csv_path) or ".", "dashboard.html")
    page = (_TMPL
            .replace("__TITLE__", html.escape(title or cfg.web.get("title", "LocalMind") + " — Library"))
            .replace("__N__", str(len(data)))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    with open(out_html, "w") as f:
        f.write(page)
    return out_html
