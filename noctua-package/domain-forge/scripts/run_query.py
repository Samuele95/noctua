#!/usr/bin/env python3
"""
run_query.py — execute ONE query against a domain-forge model's OWN engines.

This is the grounding core of /model-chat. It never answers from an LLM: it
drives the engines the model already ships, headlessly, and returns their raw
result as JSON. The input HTML is treated read-only (a temp copy is used).

Engines, by paradigm:
  sparql  -> window.__kg.runSparql(q)                 (asserted graph)
  swrl    -> window.__kg.setReasoned(true) + runSparql (query the materialised
             RDFS/SWRL inferences — "run the reasoner, then SELECT")
  prolog  -> window.__plRun(goal) if present, else drive the .pl-input/.pl-run/
             .pl-out runner UI
  dmn     -> drive the #dmn-tester Test view (best-effort) from --dmn-inputs

Usage:
  run_query.py MODEL.html --engine sparql --query 'SELECT ?t WHERE { ?t a ex:Transaction }'
  run_query.py MODEL.html --engine swrl   --query 'SELECT ?t WHERE { ?t a ex:FraudulentTransaction }'
  run_query.py MODEL.html --engine prolog --query 'outcome(tx_r2, O).'
  run_query.py MODEL.html --engine dmn    --dmn-inputs '{"Payment Amount":11234, ...}'

Prints a JSON object to stdout:
  { "ok": bool, "engine": str, "query": str, "result": <any>, "raw": str, "error": str|null }
Exit code 0 if the query executed (ok=true), 1 otherwise (including: no
browser found — set $CHROME to a chrome/chromium binary, or put `chromium`
on PATH).

This is the only implementation of the headless engine driver:
model-chat/scripts/run_query.py is a shim that executes this file with the
same argv. The $CHROME environment variable takes precedence over the PATH
search.
"""
import argparse, json, subprocess, sys, tempfile, os, re, shutil

# Browser resolution: an explicit $CHROME wins (a path or a command name on
# PATH); otherwise the first of the usual binaries found on PATH.
def _find_chrome():
    env = os.environ.get("CHROME", "").strip()
    if env:
        if os.path.isfile(env) and os.access(env, os.X_OK):
            return env
        if shutil.which(env):
            return shutil.which(env)
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if shutil.which(c):
            return shutil.which(c)
    return None

CHROME = _find_chrome()

# The injected probe. {ENGINE}/{QUERY}/{DMN} are filled by str.replace (not %/format,
# so the JS braces are safe). It runs each engine and stashes JSON on <body data-mcq>.
PROBE = r"""
<script>
(function(){
  function done(o){ try{ document.body.setAttribute('data-mcq', JSON.stringify(o)); }catch(e){
    document.title='MCQ_ERR'; } }
  var ENGINE=__ENGINE__, QUERY=__QUERY__, DMN=__DMN__;
  function go(){
    try{
      if(ENGINE==='sparql' || ENGINE==='swrl'){
        if(!window.__kg){ return done({ok:false,error:'no SPARQL engine (window.__kg) in this model'}); }
        try{ window.__kg.setReasoned(ENGINE==='swrl'); }catch(e){}
        var r=window.__kg.runSparql(QUERY);
        return done({ok:true,engine:ENGINE,query:QUERY,reasoned:ENGINE==='swrl',
                     result:{vars:r.vars, rows:r.rows}, raw:JSON.stringify(r.rows)});
      }
      if(ENGINE==='prolog'){
        if(typeof window.__plRun==='function'){
          var pr=window.__plRun(QUERY);
          return done({ok:true,engine:'prolog',query:QUERY,result:pr,raw:JSON.stringify(pr)});
        }
        var inp=document.querySelector('.pl-input'), btn=document.querySelector('.pl-run'),
            out=document.querySelector('.pl-out');
        if(!inp||!btn||!out){ return done({ok:false,error:'no Prolog runner (window.__plRun or .pl-input/.pl-run) in this model'}); }
        if('value' in inp){ inp.value=QUERY; } else { inp.textContent=QUERY; }
        inp.dispatchEvent(new Event('input',{bubbles:true}));
        btn.click();
        return setTimeout(function(){ done({ok:true,engine:'prolog',query:QUERY,
          result:out.textContent.trim(), raw:out.textContent.trim()}); }, 350);
      }
      if(ENGINE==='dmn'){
        var host=document.querySelector('#dmn-tester')||document.querySelector('[data-logic-view="dmn"]');
        if(!host){ return done({ok:false,error:'no DMN tester (#dmn-tester) in this model'}); }
        var set=0;
        Object.keys(DMN||{}).forEach(function(k){
          var f=[].slice.call(host.querySelectorAll('input,select')).filter(function(el){
            var lab=(el.getAttribute('aria-label')||el.name||el.placeholder||
              (el.closest('[data-input]')&&el.closest('[data-input]').getAttribute('data-input'))||'')+'';
            return lab.toLowerCase().indexOf(String(k).toLowerCase())>=0; })[0];
          if(f){ f.value=DMN[k]; f.dispatchEvent(new Event('input',{bubbles:true}));
                 f.dispatchEvent(new Event('change',{bubbles:true})); set++; }
        });
        var run=host.querySelector('button[class*="run"],button[data-run],.dmn-run')||
                [].slice.call(host.querySelectorAll('button')).filter(function(b){
                  return /run|test|evaluate/i.test(b.textContent);})[0];
        if(run) run.click();
        return setTimeout(function(){ done({ok:set>0,engine:'dmn',query:JSON.stringify(DMN),
          inputs_set:set, result:host.textContent.replace(/\s+/g,' ').trim().slice(0,1200),
          raw:host.textContent.slice(0,2000),
          error:set>0?null:'could not match any DMN input field — drive the Test view manually'}); }, 400);
      }
      done({ok:false,error:'unknown engine: '+ENGINE});
    }catch(e){ done({ok:false,engine:ENGINE,error:String(e&&e.message||e)}); }
  }
  if(document.readyState==='complete') setTimeout(go,1400);
  else window.addEventListener('load', function(){ setTimeout(go,1400); });
})();
</script>
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--engine", required=True, choices=["sparql","swrl","prolog","dmn"])
    ap.add_argument("--query", default="")
    ap.add_argument("--dmn-inputs", default="{}")
    ap.add_argument("--timeout", type=int, default=20)
    a = ap.parse_args()

    if not CHROME:
        print(json.dumps({"ok": False, "error": "no Chrome/Chromium found (set $CHROME)"})); sys.exit(1)
    src = open(a.model, encoding="utf-8").read()
    probe = (PROBE
             .replace("__ENGINE__", json.dumps(a.engine))
             .replace("__QUERY__", json.dumps(a.query))
             .replace("__DMN__", a.dmn_inputs or "{}"))
    html = src.replace("</body>", probe + "</body>", 1) if "</body>" in src else src + probe

    tmp = tempfile.NamedTemporaryFile("w", suffix=".mcq.html", delete=False, encoding="utf-8")
    try:
        tmp.write(html); tmp.close()
        out = subprocess.run(
            [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--virtual-time-budget=%d" % (a.timeout * 1000),
             "--run-all-compositor-stages-before-draw", "--dump-dom", "file://" + tmp.name],
            capture_output=True, text=True, timeout=a.timeout + 15)
        m = re.search(r'data-mcq="([^"]*)"', out.stdout)
        if not m:
            print(json.dumps({"ok": False, "engine": a.engine, "query": a.query,
                              "error": "engine did not respond (no data-mcq); the model may lack this engine"}))
            sys.exit(1)
        res = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;","<").replace("&gt;",">"))
        print(json.dumps(res))
        sys.exit(0 if res.get("ok") else 1)
    finally:
        try: os.unlink(tmp.name)
        except OSError: pass

if __name__ == "__main__":
    main()
