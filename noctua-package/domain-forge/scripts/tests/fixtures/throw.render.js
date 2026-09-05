(function(){
  /* THROWING render: invariant 16 must catch the uncaught error. */
  var pane = document.createElement('section');
  pane.setAttribute('data-layer', 'demo');
  (document.querySelector('main') || document.body).appendChild(pane);
  window.addEventListener('load', function(){ undefinedFunctionCalledByDemoLayer(); });
})();
