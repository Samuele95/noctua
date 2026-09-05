(function(){
  /* Demo layer render — mounts one tab + one pane via the domain-forge
     tab convention (nav.tabs button[data-tab] + section.tab-pane[data-tab]).
     Reads ONLY its own data script. Idempotent. */
  if (document.querySelector('[data-layer="demo"]')) return;
  function ready(fn){ if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  function readData(){
    var el = document.getElementById('layer-demo-data');
    if (!el) return null;
    try { return JSON.parse(el.textContent || '{}'); } catch (e) { return null; }
  }
  // Reading a model-* script is allowed (right-hand side only).
  function modelTitle(){
    var md = document.getElementById('model-markdown');
    var m = md && (md.textContent || '').match(/^\s*#\s+(.+?)\s*$/m);
    return m ? m[1] : 'model';
  }
  function switchTab(name){
    document.querySelectorAll('nav.tabs button[data-tab]').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-tab') === name); });
    document.querySelectorAll('section.tab-pane').forEach(function(p){ p.classList.toggle('active', p.getAttribute('data-tab') === name); });
  }
  ready(function(){
    var data = readData() || {items: []};
    var pane = document.createElement('section');
    pane.className = 'layer-demo tab-pane';
    pane.setAttribute('data-layer', 'demo');
    pane.setAttribute('data-tab', 'demo');
    var h = document.createElement('h2'); h.textContent = 'Demo layer on ' + modelTitle(); pane.appendChild(h);
    var ul = document.createElement('ul');
    (data.items || []).forEach(function(it){ var li = document.createElement('li'); li.textContent = it.id + ': ' + it.label; ul.appendChild(li); });
    pane.appendChild(ul);
    var panes = document.querySelectorAll('section.tab-pane');
    var last = panes.length ? panes[panes.length - 1] : null;
    if (last && last.parentNode) last.parentNode.insertBefore(pane, last.nextSibling);
    else (document.querySelector('main') || document.body).appendChild(pane);
    var tabs = document.querySelector('nav.tabs');
    if (tabs){
      var btn = document.createElement('button');
      btn.setAttribute('data-tab', 'demo'); btn.setAttribute('role', 'tab');
      btn.textContent = 'Demo';
      btn.addEventListener('click', function(){ switchTab('demo'); });
      tabs.appendChild(btn);
    }
  });
})();
