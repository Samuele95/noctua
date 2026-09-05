(function(){
  /* BAD render: mounts fine, but overwrites the model's Markdown script —
     invariant 15 must reject this. */
  if (document.querySelector('[data-layer="demo"]')) return;
  var md = document.getElementById('model-markdown');
  if (md) { md.textContent = '# clobbered by the demo layer'; }
  var pane = document.createElement('section');
  pane.setAttribute('data-layer', 'demo');
  (document.querySelector('main') || document.body).appendChild(pane);
})();
