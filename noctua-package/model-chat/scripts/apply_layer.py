#!/usr/bin/env python3
"""
apply_layer.py — write the pure-additive `chat` layer onto a domain-forge model.

Contract (see references/layer-contract.md): the output is a strict BYTE SUPERSET
of the input — every byte preserved, plus one @LAYER:start/end `chat` block
inserted just before the last </body>. The input file is never modified. Any
existing `chat` layer is stripped first (so this both creates and updates).

The rendered layer is not a static dump: each engine-grounded turn carries a
"re-run" button that re-executes its query against the model's LIVE engine
(window.__kg.runSparql / window.__plRun), so a reader can verify every answer.

This script owns only what is chat-specific: the transcript -> data JSON
shaping, the RENDER JS and the STYLE CSS. The block format, the input-digest
algorithm and the strip/replace logic are the layer platform's
(domain-forge/scripts/apply_layer.py), imported at run time — there is no
private copy and no fallback.

Usage:
  apply_layer.py MODEL.html --transcript transcript.json --out MODEL.chat.html
                 [--domain-forge-dir DIR]

Platform location: DIR from --domain-forge-dir, else $DOMAIN_FORGE_DIR, else the
sibling directory <skills>/domain-forge/scripts (DIR may be the domain-forge
root or its scripts/ directory).

transcript.json schema:
  { "turns": [ { "q", "paradigm", "reasoned"?, "query", "result", "answer",
                 "grounded" }, ... ] }
"""
import argparse, importlib.util, json, os, sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge


def load_platform(explicit=None):
    """Import domain-forge/scripts/apply_layer.py as a module. Exit 2 if absent."""
    base = explicit or os.environ.get("DOMAIN_FORGE_DIR") or \
        Path(__file__).resolve().parents[2] / "domain-forge" / "scripts"
    base = Path(base)
    path = base / "scripts" / "apply_layer.py"
    if not path.is_file():
        path = base / "apply_layer.py"
    if not path.is_file():
        print(f"ERROR: platform scripts not found at {base} — domain-forge is a "
              "required sibling of this skill", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("domain_forge_apply_layer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RENDER = r"""
(function(){
  if (document.querySelector('[data-layer="chat"]')) return;
  var data = JSON.parse(document.getElementById('layer-chat-data').textContent);
  var wrap = document.createElement('section');
  wrap.className = 'layer-chat'; wrap.setAttribute('data-layer','chat');
  var badge = {sparql:'SPARQL', swrl:'SWRL · reasoner', prolog:'Prolog', dmn:'DMN', refused:'no engine'};
  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function fmt(r){ if(r==null) return ''; if(typeof r==='string') return esc(r);
    if(r.rows){ return esc((r.rows||[]).map(function(row){return row.map(function(v){return String(v).split('#').pop();}).join('  ');}).join('\n')) || '(no rows)'; }
    if(r.sols){ return esc(r.sols.length? r.sols.map(function(s){return Object.keys(s).map(function(k){return k+'='+s[k];}).join(', ');}).join(' ; ') : (r.sols?'true':'false')); }
    return esc(JSON.stringify(r)); }
  var h = '<header class="lc-head"><h2>Model chat — engine-grounded Q&amp;A</h2>'
        + '<p class="lc-sub">Every answer below was produced by running the model’s own engine. '
        + 'Press <b>re-run</b> on any turn to re-execute its query live and confirm.</p></header>';
  data.turns.forEach(function(t, i){
    var grounded = t.grounded !== false && t.paradigm !== 'refused';
    h += '<article class="lc-turn'+(grounded?'':' lc-refused')+'">'
      +  '<div class="lc-q">'+esc(t.q)+'</div>'
      +  '<div class="lc-meta"><span class="lc-eng eng-'+esc(t.paradigm)+'">'+esc(badge[t.paradigm]||t.paradigm)+'</span>'
      +  (grounded?'<button class="lc-rerun" data-i="'+i+'">▷ re-run</button>':'')+'</div>'
      +  (grounded?'<pre class="lc-query">'+esc(t.query)+'</pre>':'')
      +  (grounded?'<div class="lc-res" id="lc-res-'+i+'"><span class="lc-res-label">result</span><pre>'+fmt(t.result)+'</pre></div>':'')
      +  '<div class="lc-ans">'+esc(t.answer)+'</div>'
      +  '</article>';
  });
  wrap.innerHTML = h;
  (document.querySelector('main')||document.body).appendChild(wrap);
  wrap.addEventListener('click', function(ev){
    var b = ev.target.closest('.lc-rerun'); if(!b) return;
    var t = data.turns[+b.dataset.i], box = document.getElementById('lc-res-'+b.dataset.i);
    var pre = box.querySelector('pre'); box.classList.add('lc-rerunning');
    try{
      var r;
      if(t.paradigm==='sparql'||t.paradigm==='swrl'){
        if(!window.__kg){ pre.textContent='(no SPARQL engine in this file)'; return; }
        try{ window.__kg.setReasoned(t.paradigm==='swrl'); }catch(e){}
        r = window.__kg.runSparql(t.query);
        pre.textContent = (r.rows||[]).map(function(row){return row.map(function(v){return String(v).split('#').pop();}).join('  ');}).join('\n') || '(no rows)';
      } else if(t.paradigm==='prolog' && typeof window.__plRun==='function'){
        r = window.__plRun(t.query);
        pre.textContent = r.sols && r.sols.length ? r.sols.map(function(s){return Object.keys(s).map(function(k){return k+'='+s[k];}).join(', ');}).join(' ; ') : (r.sols?'true':'false');
      } else { pre.textContent='(re-run not available for this engine here)'; }
      box.classList.add('lc-verified');
    }catch(e){ pre.textContent='error: '+e.message; }
    setTimeout(function(){ box.classList.remove('lc-rerunning'); }, 600);
  });
})();
"""

STYLE = r"""
.layer-chat{max-width:860px;margin:36px auto 64px;padding:0 24px;font-family:var(--sans,system-ui,sans-serif)}
.layer-chat .lc-head h2{font:600 22px var(--serif,Georgia,serif);color:var(--ink,#1a1814);margin:0 0 4px}
.layer-chat .lc-sub{font:400 13.5px var(--sans,system-ui);color:var(--muted,#6d685b);margin:0 0 18px}
.layer-chat .lc-turn{border:1px solid var(--border,#e6e1d5);border-left:3px solid var(--accent,#1b3a73);border-radius:6px;padding:13px 16px;margin:0 0 14px;background:var(--surface,#fff)}
.layer-chat .lc-turn.lc-refused{border-left-color:#b08900;background:#fbf8ef}
.layer-chat .lc-q{font:600 15.5px var(--serif,Georgia,serif);color:var(--ink,#1a1814);margin:0 0 7px}
.layer-chat .lc-meta{display:flex;align-items:center;gap:10px;margin:0 0 8px}
.layer-chat .lc-eng{font:600 10px var(--sans,system-ui);letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;border-radius:3px;background:var(--accent-soft,#eaeef6);color:var(--accent-ink,#15315f)}
.layer-chat .lc-eng.eng-refused{background:#f3ecd6;color:#7a5b00}
.layer-chat .lc-rerun{appearance:none;border:1px solid var(--border-strong,#d2ccbc);background:none;border-radius:3px;font:600 11px var(--sans,system-ui);color:var(--accent,#1b3a73);padding:2px 9px;cursor:pointer}
.layer-chat .lc-rerun:hover{background:var(--accent-soft,#eaeef6)}
.layer-chat .lc-query{background:var(--code-bg,#f7f5ee);border:1px solid var(--code-line,#e8e3d8);border-radius:4px;padding:9px 12px;font:11.5px/1.5 var(--mono,ui-monospace,monospace);overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 8px;color:var(--code-fg,#2a261f)}
.layer-chat .lc-res{margin:0 0 8px}
.layer-chat .lc-res-label{font:600 9px var(--sans,system-ui);letter-spacing:.1em;text-transform:uppercase;color:var(--muted,#6d685b)}
.layer-chat .lc-res pre{margin:3px 0 0;background:var(--panel,#f8f6f1);border:1px solid var(--border,#e6e1d5);border-radius:4px;padding:8px 11px;font:11.5px/1.5 var(--mono,ui-monospace,monospace);overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--ink-soft,#3a362d)}
.layer-chat .lc-res.lc-verified pre{border-color:#3d6a37;box-shadow:0 0 0 2px #eef4ec}
.layer-chat .lc-ans{font:15px/1.6 var(--serif,Georgia,serif);color:var(--ink-soft,#3a362d)}
.layer-chat .lc-ans b,.layer-chat .lc-ans strong{color:var(--ink,#1a1814)}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--transcript", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--domain-forge-dir", help="domain-forge root or scripts/ dir (default: sibling skill, or $DOMAIN_FORGE_DIR)")
    a = ap.parse_args()
    platform = load_platform(a.domain_forge_dir)

    html = open(a.model, encoding="utf-8").read()
    if not platform.is_model(html):
        print("error: not a domain-forge model (no #domain-model block)", file=sys.stderr); sys.exit(2)
    tr = json.load(open(a.transcript, encoding="utf-8"))
    now = platform.utc_now_iso()
    payload = {"version": 1, "produced_at": now, "input_digest": platform.domain_digest(html),
               "turns": tr.get("turns", tr if isinstance(tr, list) else [])}
    notes = []
    try:
        out = platform.apply_layer(html, "chat", json.dumps(payload, indent=1), RENDER,
                                   style_css=STYLE.strip("\n"), produced_by="/model-chat",
                                   version=1, produced_at=now, report=notes.append)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr); sys.exit(1)
    for n in notes:
        print("note: %s" % n, file=sys.stderr)
    open(a.out, "w", encoding="utf-8").write(out)
    print("wrote %s (%d turns, +%d bytes)" % (a.out, len(payload["turns"]), len(out) - len(html)))

if __name__ == "__main__":
    main()
