"""LocalMind web chat — streaming answers, clickable sources, conversation memory.

Run:  localmind web    then open http://127.0.0.1:5007
Fully local; the only network call is to your configured model endpoint.
"""
from __future__ import annotations
import os, json, subprocess, sys, threading
from flask import Flask, request, jsonify, Response, stream_with_context

from . import core
from .config import Config, load as load_config

PAGE = r"""<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
 :root{--bg:#0f1714;--panel:#16211d;--card:#1b2925;--ink:#e8efe9;--mut:#8aa39a;--line:#26352f;--acc:#3fae7a;--acc2:#5b9bd5}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;height:100vh}
 header{padding:14px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
 .dot{width:9px;height:9px;border-radius:50%;background:var(--acc);box-shadow:0 0 8px var(--acc)}
 h1{margin:0;font-size:16px;font-weight:600} h1 span{color:var(--mut);font-weight:400;font-size:12px;margin-left:8px}
 .clear{margin-left:auto;color:var(--mut);font-size:12.5px;cursor:pointer;border:1px solid var(--line);padding:5px 11px;border-radius:8px}
 .clear:hover{color:var(--ink)}
 #chat{flex:1;overflow-y:auto;padding:24px} .inner{max-width:880px;margin:0 auto}
 .msg{margin:0 0 22px} .who{font-size:12px;color:var(--mut);margin-bottom:5px}
 .bubble{white-space:pre-wrap} .user .bubble{color:var(--acc2)}
 .src{margin-top:10px;font-size:13px}
 .src a{display:block;color:var(--mut);text-decoration:none;padding:4px 0;border-top:1px solid var(--line)}
 .src a:hover{color:var(--ink)} .src b{color:var(--acc)}
 .ex{color:var(--mut);font-size:13.5px} .ex span{cursor:pointer;text-decoration:underline}
 footer{border-top:1px solid var(--line);padding:14px 24px}
 .row{max-width:880px;margin:0 auto;display:flex;gap:10px}
 #q{flex:1;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--ink);font-size:15px}
 #send{padding:0 18px;background:var(--acc);border:none;border-radius:10px;color:#04130c;font-weight:600;cursor:pointer}
 #send:disabled{opacity:.5;cursor:default}
</style></head><body>
<header><span class=dot></span><h1>__TITLE__<span>local · private · your documents</span></h1>
<div class=clear onclick="hist=[];document.getElementById('chat').querySelector('.inner').innerHTML=intro()">clear</div></header>
<div id=chat><div class=inner></div></div>
<footer><div class=row>
  <input id=q placeholder="Ask about your library…" autocomplete=off>
  <button id=send>Ask</button>
</div></footer>
<script>
let hist=[];
const chat=document.getElementById('chat').querySelector('.inner');
const qEl=document.getElementById('q'),send=document.getElementById('send');
function intro(){return `<div class=ex>Try:&nbsp;
  <span onclick="ask(this.textContent)">What are the main themes in my library?</span> ·
  <span onclick="ask(this.textContent)">Summarize what I have on [topic]</span></div>`;}
chat.innerHTML=intro();
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function add(who,cls){const d=document.createElement('div');d.className='msg '+cls;
  d.innerHTML=`<div class=who>${who}</div><div class=bubble></div><div class=src></div>`;
  chat.appendChild(d);chat.parentElement.scrollTop=chat.parentElement.scrollHeight;return d;}
async function ask(q){q=(q||qEl.value).trim();if(!q)return;
  qEl.value='';send.disabled=true;
  add('you','user').querySelector('.bubble').textContent=q;
  const m=add('LocalMind','bot');const bub=m.querySelector('.bubble'),src=m.querySelector('.src');
  let answer='';
  const res=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({q,history:hist})});
  const reader=res.body.getReader(),dec=new TextDecoder();let buf='';
  while(true){const{value,done}=await reader.read();if(done)break;
    buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop();
    for(const ln of lines){if(!ln.startsWith('data:'))continue;
      const ev=JSON.parse(ln.slice(5));
      if(ev.t==='sources'){src.innerHTML=ev.v.map((h,i)=>
        `<a href="/open?path=${encodeURIComponent(h.path)}"><b>[${i+1}]</b> ${esc(h.source)} · ${esc(h.title)}</a>`).join('');}
      else if(ev.t==='delta'){answer+=ev.v;bub.textContent=answer;
        chat.parentElement.scrollTop=chat.parentElement.scrollHeight;}}}
  hist.push({role:'user',content:q});hist.push({role:'assistant',content:answer});
  send.disabled=false;qEl.focus();}
send.onclick=()=>ask();qEl.addEventListener('keydown',e=>{if(e.key==='Enter')ask();});
qEl.focus();
</script></body></html>"""


def create_app(cfg: Config) -> Flask:
    app = Flask(__name__)
    allowed_roots = [os.path.realpath(p) for p in cfg.corpus_paths()]

    @app.route("/")
    def home():
        return PAGE.replace("__TITLE__", cfg.web.get("title", "LocalMind"))

    @app.route("/ask", methods=["POST"])
    def ask():
        body = request.get_json(force=True)
        q = (body.get("q") or "").strip()
        history = body.get("history") or []

        @stream_with_context
        def gen():
            for kind, val in core.stream_answer(cfg, q, history):
                if kind == "sources":
                    src = [{"source": h["source"], "title": h["title"], "path": h["path"]} for h in val]
                    yield "data:" + json.dumps({"t": "sources", "v": src}) + "\n"
                elif kind == "delta":
                    yield "data:" + json.dumps({"t": "delta", "v": val}) + "\n"
            yield "data:" + json.dumps({"t": "done"}) + "\n"

        return Response(gen(), mimetype="text/event-stream")

    @app.route("/open")
    def open_file():
        """Open a source file with the OS default app — only within corpus roots."""
        path = request.args.get("path", "")
        rp = os.path.realpath(path)
        if not any(rp.startswith(root) for root in allowed_roots):
            return "forbidden", 403
        if not os.path.exists(rp):
            return "not found", 404
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", rp])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", rp])
            elif sys.platform.startswith("win"):
                os.startfile(rp)  # type: ignore
        except Exception:
            pass
        return "ok"

    return app


def run(cfg: Config | None = None):
    cfg = cfg or load_config()
    # serving keeps the embedder on CPU by default (low memory); override via env
    os.environ.setdefault("LOCALMIND_EMBED_DEVICE", cfg.embed.get("device", "cpu"))
    app = create_app(cfg)
    host, port = cfg.web["host"], int(cfg.web["port"])
    # warm the model + index in the background so the first query is fast
    threading.Thread(target=lambda: core.warmup(cfg), daemon=True).start()
    print(f"LocalMind chat -> http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)
