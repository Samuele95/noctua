/* dataset-forge — `geometry` layer render script (contract: references/report-contract.md §6).
   Vanilla JS, no libraries, no network, inline SVG only. Reads ONLY #layer-geometry-data.
   Mounts one tab (data-layer="geometry") and draws four linked views:
     A Space — scree + scatter on named basis members (or the shipped PCA), hover row card, brush.
     B Derivation graph — columns as nodes, rules as edges, cycles re-orientable in place.
     C Orthogonality — heatmap of the shipped pair measures over the current basis.
     D Partition — label candidates as cards; selecting one drives B and A.
   The only computation done here is the basis after a re-orientation: the columns that are the
   head of no active rule. Rank, PCA and dependency measures are never recomputed; they are
   filtered, projected and joined. */
(function () {
  'use strict';
  if (document.querySelector('[data-layer="geometry"]')) return;

  var VERSION = 'dataset-forge/geometry-render@1';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var EXCLUDED_ROLES = { identity: 1, key: 1, degenerate: 1, constant: 1 };
  var PALETTE = ['#1b3a73', '#c8552f', '#2e8b57', '#8a6420', '#7a3c77', '#2c6570',
                 '#b5453d', '#4f6d2b', '#9a4f8a', '#6d685b', '#3b6fb6', '#d08a2b'];

  /* ---------------------------------------------------------------- helpers */
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }
  /* DOM helper: text goes through textContent only, never innerHTML. */
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'class') n.className = attrs[k];
      else if (k === 'text') n.textContent = attrs[k];
      else if (k.indexOf('on') === 0 && typeof attrs[k] === 'function') n[k] = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function svg(tag, attrs, kids) {
    var n = document.createElementNS(SVGNS, tag);
    if (attrs) for (var k in attrs) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k.indexOf('on') === 0 && typeof attrs[k] === 'function') n[k] = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function fmt(v) {
    if (v === null || v === undefined || v === '') return '·';
    if (!isNum(v)) return String(v);
    if (Math.round(v) === v) return String(v);
    var a = Math.abs(v);
    var s = a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(2) : v.toFixed(3);
    return s.indexOf('.') >= 0 ? s.replace(/\.?0+$/, '') : s;
  }
  function pct(v) { return isNum(v) ? (100 * v).toFixed(1) + '%' : '·'; }
  function contains(arr, x) { return (arr || []).indexOf(x) >= 0; }
  function subset(a, b) { return (a || []).every(function (x) { return contains(b, x); }); }
  function uniq(arr) { var s = {}, out = []; arr.forEach(function (x) { if (!s[x]) { s[x] = 1; out.push(x); } }); return out; }
  function without(arr, drop) { return (arr || []).filter(function (x) { return !contains(drop, x); }); }
  function keyed(fn) { return function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e); } }; }
  function chip(text, cls) { return el('span', { class: 'g-chip ' + (cls || ''), text: text }); }
  function para(text, cls) { return el('p', { class: cls || 'g-prose', text: text }); }
  function isDateStr(v) { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v); }

  /* ---------------------------------------------------------------- host tab plumbing
     Mirrors inferred-questions/scripts/apply_layer.py: nav.tabs buttons + section.tab-pane,
     visibility by the `active` class; we never call the host's own switcher. */
  function pickTabContainer() {
    return document.querySelector('nav.tabs') || document.querySelector('nav[role="tablist"]')
        || document.querySelector('[data-tabs]') || null;
  }
  function pickPaneSibling() {
    var panes = document.querySelectorAll('section.tab-pane');
    return panes.length ? panes[panes.length - 1] : null;
  }
  function switchTab(name) {
    document.querySelectorAll('nav.tabs button[data-tab], nav[role="tablist"] button[data-tab]')
      .forEach(function (b) { b.classList.toggle('active', b.getAttribute('data-tab') === name); });
    document.querySelectorAll('section.tab-pane')
      .forEach(function (p) { p.classList.toggle('active', p.getAttribute('data-tab') === name); });
  }
  function mount() {
    var pane = el('section', { class: 'layer-geometry tab-pane', 'data-layer': 'geometry',
                               'data-tab': 'geometry', id: 'tab-geometry', role: 'tabpanel',
                               'aria-label': 'Geometry' });
    var sib = pickPaneSibling();
    if (sib && sib.parentNode) sib.parentNode.insertBefore(pane, sib.nextSibling);
    else (document.querySelector('main') || document.body).appendChild(pane);
    var tabs = pickTabContainer();
    if (tabs) tabs.appendChild(el('button', { 'data-tab': 'geometry', 'data-layer': 'geometry', role: 'tab',
                                                onclick: function () { switchTab('geometry'); } }, ['Geometry']));
    return pane;
  }
  function readData() {
    var s = document.getElementById('layer-geometry-data');
    if (!s) return { error: 'missing' };
    try { return { data: JSON.parse(s.textContent || '{}') }; }
    catch (e) { return { error: 'unparseable: ' + e.message }; }
  }

  /* ---------------------------------------------------------------- model: indexes over the layer data */
  function buildModel(data) {
    var M = { data: data, typing: {}, byRule: {}, pairs: {} };
    (data.typing || []).forEach(function (t) { if (t && t.column) M.typing[t.column] = t; });
    M.derivations = (data.derivations || []).map(normRule);
    M.derivations.forEach(function (d) { M.byRule[d.rule_id] = d; });
    var src = (data.source && data.source.columns) || [];
    M.columns = uniq([].concat(src, Object.keys(M.typing),
      (data.basis && data.basis.members) || [],
      M.derivations.map(function (d) { return d.column; }),
      data.explore && data.explore.columns ? Object.keys(data.explore.columns) : []));
    M.role = function (c) {
      var t = M.typing[c];
      if (t && t.role) return t.role;
      return M.derivations.some(function (d) { return d.column === c; }) ? 'derived' : 'dimension';
    };
    M.excluded = function (c) { return !!EXCLUDED_ROLES[M.role(c)]; };
    M.typeOf = function (c) {
      var t = M.typing[c];
      if (t) return t.final_type || t.script_type || '?';
      var v = M.values(c);
      if (!v) return '?';
      var x = v.find(function (y) { return y !== null && y !== undefined; });
      return isNum(x) ? 'numeric' : isDateStr(x) ? 'datetime' : 'nominal';
    };
    var ex = data.explore;
    var okExplore = ex && ex.columns && typeof ex.columns === 'object';
    var n = 0;
    if (okExplore) Object.keys(ex.columns).forEach(function (c) { if (Array.isArray(ex.columns[c])) n = Math.max(n, ex.columns[c].length); });
    M.explore = (okExplore && n >= 10) ? ex : null;
    M.rows = M.explore ? n : 0;
    M.values = function (c) { return M.explore && Array.isArray(M.explore.columns[c]) ? M.explore.columns[c] : null; };
    M.pca = (M.explore && ex.pca && Array.isArray(ex.pca.scores) && ex.pca.scores.length === n) ? ex.pca : null;
    ((data.orthogonality && data.orthogonality.pairs) || []).forEach(function (p) {
      if (p && p.a && p.b) M.pairs[[p.a, p.b].sort().join('|')] = p;
    });
    M.pair = function (a, b) { return M.pairs[[a, b].sort().join('|')] || null; };
    M.thresholds = (data.orthogonality && data.orthogonality.thresholds) || { nmi: 0.5, pearson: 0.9, eta2: 0.8, cramers_v: 0.8 };
    M.fds = (data.functional_dependencies || []).filter(function (f) { return f && Array.isArray(f.lhs) && f.rhs; });
    M.disagreements = data.disagreements || [];
    M.markers = data.markers || [];
    M.stats = data.stats || {};
    M.cycles = normCycles(M);
    M.cycleOf = function (c) { return M.cycles.find(function (cy) { return contains(cy.members, c); }) || null; };
    M.stated = ((data.partitions && data.partitions.candidates) || []).filter(function (c) { return c && c.label; });
    return M;
  }
  function normRule(r) {
    var p = r.provenance || {};
    function ch(k) { var v = p[k] || {}; return { status: v.status || 'untested', note: v.note, evidence: v.evidence, verified_rows: v.verified_rows, of_rows: v.of_rows, rows: v.rows }; }
    return { column: r.column, rule_id: r.rule_id || ('rule-' + r.column), layer: r.layer || '?',
             formula: r.formula || '', body: r.body || [], cycle: r.cycle || null, cycle_id: r.cycle_id || null,
             consequences: r.consequences || null,
             provenance: { semantic: ch('semantic'), symbolic: ch('symbolic'), empirical: ch('empirical') } };
  }
  /* Cycles: from data.cycles when shipped (pre-written orientations), else grouped from the
     derivations' `cycle` fields with a single report orientation each. */
  function normCycles(M) {
    var out = [];
    var declared = (M.data.cycles || []).filter(function (c) { return c && Array.isArray(c.members); });
    declared.forEach(function (c, i) {
      var cy = { id: c.id || ('cycle-' + i), members: c.members.slice(), reading: c.reading || '', orientations: [] };
      (c.orientations || []).forEach(function (o, j) {
        cy.orientations.push({ id: o.id || ('o' + j), isDefault: !!o.default, basis: o.basis || [],
          consequences: o.consequences || null,
          rules: (o.rules || []).map(function (r) { return typeof r === 'string' ? (M.byRule[r] || null) : normRule(r); }).filter(Boolean) });
      });
      out.push(cy);
    });
    M.derivations.forEach(function (d) {
      if (!d.cycle || !d.cycle.length) return;
      var key = d.cycle.slice().sort().join('|');
      var hit = out.find(function (cy) { return cy.members.slice().sort().join('|') === key; });
      if (!hit) out.push({ id: d.cycle_id || d.cycle.join('-'), members: d.cycle.slice(), reading: '', orientations: [] });
      else if (d.cycle_id && !hit.id) hit.id = d.cycle_id;
    });
    out.forEach(function (cy) {
      if (!cy.orientations.some(function (o) { return o.isDefault; })) {
        var rules = M.derivations.filter(function (d) { return contains(cy.members, d.column); });
        cy.orientations.unshift({ id: 'report', isDefault: true, basis: without(cy.members, rules.map(function (r) { return r.column; })),
          rules: rules, consequences: rules.length ? rules[0].consequences : null });
      }
    });
    return out;
  }

  /* ---------------------------------------------------------------- build */
  function build() {
    var pane = mount();
    var head = el('div', { class: 'g-head' }, [el('h2', { text: 'Geometry' })]);
    pane.appendChild(head);
    var read = readData();
    if (read.error) {
      head.appendChild(para(read.error === 'missing'
        ? 'The geometry layer has no data: the layer-geometry-data script block is missing from this file. Nothing to explore; re-run /dataset-forge to produce the layer.'
        : 'The geometry layer data could not be parsed (' + read.error + '). Nothing to explore.', 'g-empty'));
      window.__geometry = { state: null, reorient: function () { return []; }, basis: function () { return []; }, candidates: function () { return []; }, version: VERSION };
      return;
    }
    var data = read.data;
    var M = buildModel(data);

    /* Cross-view state (§6): one object, every view reads it, any change redraws all. Not persisted. */
    var state = {
      selectedRows: null,          // null = all rows; else array of row indexes from the brush
      axes: null,                  // [xColumn, yColumn] among current basis members
      colourBy: 'none',            // column name or 'none'
      pca: false,                  // View A rotated axes toggle
      activeOrientation: {},       // cycleId -> orientationId ('' / absent = the report's orientation)
      activeCandidate: null,       // label of the selected partition card
      selectedNode: null,          // View B card
      selectedPair: null,          // View C detail
      hoverRow: null
    };

    /* ---- basis / rules / candidates: the one computation the contract allows ---- */
    function orientationOf(cy) {
      var oid = state.activeOrientation[cy.id];
      if (!oid) return cy.orientations.find(function (o) { return o.isDefault; }) || cy.orientations[0];
      if (oid.indexOf('adhoc:') === 0) {
        var col = oid.slice(6), def = cy.orientations.find(function (o) { return o.isDefault; }) || { basis: [], rules: [] };
        return { id: oid, adhoc: true, basis: uniq(def.basis.concat([col])),
                 rules: def.rules.filter(function (r) { return r.column !== col; }), consequences: null };
      }
      return cy.orientations.find(function (o) { return o.id === oid; }) || cy.orientations[0];
    }
    function activeRules() {
      var rules = [], reoriented = {};
      M.cycles.forEach(function (cy) { var o = orientationOf(cy); if (!o.isDefault) reoriented[cy.id] = o; });
      M.derivations.forEach(function (d) {
        var cy = M.cycleOf(d.column);
        if (cy && reoriented[cy.id]) return;
        rules.push(d);
      });
      Object.keys(reoriented).forEach(function (k) {
        reoriented[k].rules.forEach(function (r) {
          var c = Object.create(r); c.orientation = reoriented[k]; c.consequences = r.consequences || reoriented[k].consequences; rules.push(c);
        });
      });
      return rules;
    }
    function basis() {
      var heads = {};
      activeRules().forEach(function (r) { heads[r.column] = 1; });
      var order = uniq(((data.basis && data.basis.members) || []).concat(M.columns));
      return order.filter(function (c) { return contains(M.columns, c) && !M.excluded(c) && !heads[c]; });
    }
    function inferTask(col) {
      var t = M.typeOf(col);
      return t === 'boolean' ? 'binary classification' : (t === 'nominal' || t === 'ordinal') ? 'classification' : 'regression';
    }
    function candidates() {
      var B = basis(), out = [], seen = {};
      function add(label, ruleId, body, rule) {
        if (seen[label]) return; seen[label] = 1;
        var stated = M.stated.find(function (c) { return c.label === label; }) || null;
        var features = without(B, body);
        out.push({ label: label, rule_id: ruleId, body: body.slice(), features: features, dropped: body.slice(),
                   input_dim: features.length, structural: true, stated: stated, rule: rule,
                   task: (stated && stated.task) || inferTask(label) });
      }
      activeRules().forEach(function (r) { if (r.body.length && subset(r.body, B) && !M.excluded(r.column)) add(r.column, r.rule_id, r.body, r); });
      M.fds.forEach(function (f) {
        if (subset(f.lhs, B) && !M.excluded(f.rhs) && !contains(B, f.rhs)) add(f.rhs, 'fd:' + f.lhs.join('+'), f.lhs, null);
      });
      M.stated.forEach(function (c) {
        if (seen[c.label]) return; seen[c.label] = 1;
        out.push({ label: c.label, rule_id: c.rule_id, body: c.dropped_for_leakage || [], features: c.features || [],
                   dropped: c.dropped_for_leakage || [], input_dim: c.input_dim,
                   structural: false, stated: c, rule: null, task: c.task || inferTask(c.label) });
      });
      out.sort(function (a, b) { return (b.stated ? 1 : 0) - (a.stated ? 1 : 0) || a.label.localeCompare(b.label); });
      return out;
    }
    function reorient(column, orientationId) {
      var cy = M.cycleOf(column);
      if (!cy) { console.warn('[geometry] ' + column + ' is in no cycle'); return basis(); }
      var o = null;
      if (orientationId) o = cy.orientations.find(function (x) { return x.id === orientationId; });
      if (!o) o = cy.orientations.find(function (x) { return contains(x.basis, column) && x.id !== orientationOf(cy).id; });
      if (o) state.activeOrientation[cy.id] = o.isDefault ? '' : o.id;
      else if (!contains(orientationOf(cy).basis, column)) state.activeOrientation[cy.id] = 'adhoc:' + column;
      else return basis();
      dropStale(); redraw();
      return basis();
    }
    function resetOrientation(cyId) {
      if (cyId) delete state.activeOrientation[cyId]; else state.activeOrientation = {};
      dropStale(); redraw();
    }
    /* After a re-orientation, axes / pair choices that name columns no longer in the basis are dropped. */
    function dropStale() {
      var B = basis();
      if (state.axes && !(contains(B, state.axes[0]) && contains(B, state.axes[1]))) state.axes = null;
      if (state.selectedPair && !(contains(B, state.selectedPair[0]) && contains(B, state.selectedPair[1]))) state.selectedPair = null;
    }

    /* ---- shared render pieces ---- */
    function provenanceBlock(p) {
      var wrap = el('div', { class: 'g-prov' });
      ['semantic', 'symbolic', 'empirical'].forEach(function (k) {
        var v = p[k] || { status: 'untested' };
        var detail = v.note || v.evidence || (v.verified_rows !== undefined ? v.verified_rows + ' of ' + v.of_rows + ' rows' : '');
        if (v.status === 'refuted' && v.rows) detail += ' (rows ' + v.rows.join(', ') + ')';
        wrap.appendChild(el('div', { class: 'g-prov-row' }, [
          chip(k, 'g-chan'), chip(v.status, 'g-st-' + v.status), el('span', { class: 'g-prov-detail', text: detail || '' })]));
      });
      return wrap;
    }
    function consequenceBlock(c, title) {
      var box = el('div', { class: 'g-cons' }, [el('h5', { text: title || 'Consequences' })]);
      if (!c) { box.appendChild(para('No pre-written consequence block for this choice. Re-run /dataset-forge to author one; the explorer does not invent consequences.', 'g-muted')); return box; }
      box.appendChild(el('p', { class: 'g-decision', text: c.decision || '' }));
      var alts = c.alternatives || [];
      box.appendChild(el('p', { class: 'g-muted', text: alts.length ? 'Alternatives weighed: ' + alts.join('; ') : 'No alternatives: the decision was forced.' }));
      var dl = el('dl', { class: 'g-down' });
      var down = c.downstream || {};
      Object.keys(down).forEach(function (k) { dl.appendChild(el('dt', { text: k.replace(/_/g, ' ') })); dl.appendChild(el('dd', { text: String(down[k]) })); });
      if (Object.keys(down).length) box.appendChild(dl);
      return box;
    }
    function selectionSummary(col) {
      var v = M.values(col);
      if (!v || !state.selectedRows) return null;
      var sel = state.selectedRows.map(function (i) { return v[i]; }).filter(function (x) { return x !== null && x !== undefined; });
      if (!sel.length) return 'no values in the selection';
      if (isNum(sel[0])) { var lo = Infinity, hi = -Infinity; sel.forEach(function (x) { if (x < lo) lo = x; if (x > hi) hi = x; }); return 'selected rows: ' + fmt(lo) + ' to ' + fmt(hi); }
      var cnt = {}; sel.forEach(function (x) { cnt[x] = (cnt[x] || 0) + 1; });
      return 'selected rows: ' + Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }).slice(0, 5).map(function (k) { return k + ' ×' + cnt[k]; }).join(', ');
    }

    /* ---- layout ---- */
    var src = data.source || {};
    head.appendChild(el('p', { class: 'g-sub', text: (src.path || 'dataset') + ' — ' + (src.rows !== undefined ? src.rows + ' rows, ' : '') +
      ((src.columns && src.columns.length) || M.columns.length) + ' columns' + (M.explore ? ', sample of ' + M.rows + ' rows in the explorer' : ', no explorer sample shipped') }));
    var status = el('div', { class: 'g-status', role: 'status' });
    pane.appendChild(status);
    var grid = el('div', { class: 'g-grid' });
    pane.appendChild(grid);
    var VA = el('section', { class: 'g-view', 'data-view': 'space' }, [el('h3', { text: 'A · Space' })]);
    var VB = el('section', { class: 'g-view', 'data-view': 'derivations' }, [el('h3', { text: 'B · Derivation graph' })]);
    var VC = el('section', { class: 'g-view', 'data-view': 'orthogonality' }, [el('h3', { text: 'C · Orthogonality' })]);
    var VD = el('section', { class: 'g-view', 'data-view': 'partition' }, [el('h3', { text: 'D · Partition' })]);
    [VA, VB, VC, VD].forEach(function (v) { grid.appendChild(v); });
    var bodyA = el('div', { class: 'g-body' }), bodyB = el('div', { class: 'g-body' }), bodyC = el('div', { class: 'g-body' }), bodyD = el('div', { class: 'g-body' });
    VA.appendChild(bodyA); VB.appendChild(bodyB); VC.appendChild(bodyC); VD.appendChild(bodyD);
    pane.appendChild(statsTable());
    pane.appendChild(markersList());

    function statsTable() {
      var det = el('details', { class: 'g-stats' }, [el('summary', { text: 'Statistics (verbatim from geometry.json)' })]);
      var cols = Object.keys(M.stats);
      if (!cols.length) { det.appendChild(para('No stats section shipped.', 'g-muted')); return det; }
      var keys = uniq([].concat.apply([], cols.map(function (c) { return Object.keys(M.stats[c] || {}); })));
      var t = el('table'), thead = el('thead'), tr = el('tr', null, [el('th', { text: 'column' })]);
      keys.forEach(function (k) { tr.appendChild(el('th', { text: k })); });
      thead.appendChild(tr); t.appendChild(thead);
      var tb = el('tbody');
      cols.forEach(function (c) {
        var r = el('tr', null, [el('th', { text: c })]);
        keys.forEach(function (k) { var v = (M.stats[c] || {})[k]; r.appendChild(el('td', { text: v === undefined ? '' : fmt(v) })); });
        tb.appendChild(r);
      });
      t.appendChild(tb);
      det.appendChild(el('div', { class: 'g-scroll' }, [t]));
      return det;
    }
    function markersList() {
      var det = el('details', { class: 'g-markers' }, [el('summary', { text: 'Markers (' + M.markers.length + ')' })]);
      var ul = el('ul');
      M.markers.forEach(function (m) { ul.appendChild(el('li', { class: 'g-mk-' + String(m).split(':')[0].toLowerCase(), text: String(m) })); });
      det.appendChild(ul);
      return det;
    }

    /* ---- status bar ---- */
    function drawStatus() {
      clear(status);
      var B = basis();
      status.appendChild(chip('basis: ' + B.length + ' members', 'g-chip-strong'));
      var reor = M.cycles.filter(function (cy) { return !orientationOf(cy).isDefault; });
      status.appendChild(chip(reor.length ? 'orientation: ' + reor.map(function (cy) { return cy.id + ' → ' + orientationOf(cy).id; }).join(', ') : 'orientation: the report’s', ''));
      if (reor.length) status.appendChild(el('button', { class: 'g-btn', type: 'button', onclick: function () { resetOrientation(); } }, ['Reset orientation']));
      status.appendChild(chip(state.selectedRows ? 'selection: ' + state.selectedRows.length + ' of ' + M.rows + ' rows' : 'selection: all rows', ''));
      if (state.selectedRows) status.appendChild(el('button', { class: 'g-btn', type: 'button', onclick: function () { state.selectedRows = null; redraw(); } }, ['Clear selection']));
      status.appendChild(chip(state.activeCandidate ? 'label: ' + state.activeCandidate : 'label: none selected', ''));
      if (state.activeCandidate) status.appendChild(el('button', { class: 'g-btn', type: 'button', onclick: function () { state.activeCandidate = null; if (state.colourBy === 'label') state.colourBy = 'none'; redraw(); } }, ['Deselect label']));
    }

    /* ================================================================ View A — Space
       Contract: scree of the shipped singular values; scatter of the sample on two named basis
       members or the two leading shipped PCA components; hover row card; rectangle brush. */
    var ctrlA = el('div', { class: 'g-ctrl' });
    var selX = el('select', { 'aria-label': 'x axis' }), selY = el('select', { 'aria-label': 'y axis' }), selC = el('select', { 'aria-label': 'colour by' });
    var chkPCA = el('input', { type: 'checkbox', id: 'g-pca-toggle' });
    selX.onchange = function () { state.axes = [selX.value, selY.value]; redraw(); };
    selY.onchange = function () { state.axes = [selX.value, selY.value]; redraw(); };
    selC.onchange = function () { state.colourBy = selC.value; redraw(); };
    chkPCA.onchange = function () { state.pca = chkPCA.checked; redraw(); };
    ctrlA.appendChild(el('label', null, ['x ', selX]));
    ctrlA.appendChild(el('label', null, ['y ', selY]));
    ctrlA.appendChild(el('label', null, ['colour ', selC]));
    ctrlA.appendChild(el('label', { class: 'g-toggle' }, [chkPCA, ' rotated axes (PC1 × PC2)']));
    var figA = el('div', { class: 'g-figA' }), cardA = el('div', { class: 'g-card', 'aria-live': 'polite' });

    function plottable(c) { var v = M.values(c); return !!v && v.some(function (x) { return x !== null && x !== undefined; }); }
    function colourable(c) {
      var v = M.values(c); if (!v) return false;
      var t = M.typeOf(c); if (t === 'numeric' || t === 'datetime') return false;
      return uniq(v.map(String)).length <= PALETTE.length;
    }
    function fillSelect(sel, options, value) {
      var cur = value || sel.value; clear(sel);
      options.forEach(function (o) { sel.appendChild(el('option', { value: o.value, text: o.text })); });
      if (options.some(function (o) { return o.value === cur; })) sel.value = cur;
    }
    /* Project a column to axis coordinates: numbers as they are, dates as epoch ms, nominals as sorted category index. */
    function axisOf(c) {
      var v = M.values(c), first = v.find(function (x) { return x !== null && x !== undefined; });
      if (isNum(first)) return { kind: 'num', vals: v.map(function (x) { return isNum(x) ? x : null; }), label: c };
      if (isDateStr(first)) return { kind: 'date', vals: v.map(function (x) { var t = Date.parse(x); return isFinite(t) ? t : null; }), label: c };
      var cats = uniq(v.filter(function (x) { return x !== null && x !== undefined; }).map(String)).sort();
      var idx = {}; cats.forEach(function (k, i) { idx[k] = i; });
      return { kind: 'cat', cats: cats, vals: v.map(function (x) { return x === null || x === undefined ? null : idx[String(x)]; }), label: c };
    }
    function drawA() {
      clear(bodyA);
      if (!M.explore) {
        bodyA.appendChild(el('div', { class: 'g-empty' }, [
          para('No explorer sample. View A needs the layer’s `explore` object (a columnar sample of at least 10 rows plus the shipped PCA); this file ships ' + (data.explore ? M.rows + ' row(s)' : 'none') + '. Re-run dataset-forge/scripts/geometry.py with --explore-rows to produce it; the space reading below is unaffected.'),
          para((data.space && data.space.reading) || '', 'g-prose')]));
        return;
      }
      var B = basis().filter(plottable);
      var opts = B.map(function (c) { return { value: c, text: c }; });
      if (!state.axes || !contains(B, state.axes[0]) || !contains(B, state.axes[1])) state.axes = [B[0] || '', B[1] || B[0] || ''];
      fillSelect(selX, opts, state.axes[0]); fillSelect(selY, opts, state.axes[1]);
      var copts = [{ value: 'none', text: 'none' }];
      if (state.activeCandidate && M.values(state.activeCandidate)) copts.push({ value: 'label', text: 'label: ' + state.activeCandidate });
      M.columns.filter(colourable).forEach(function (c) { copts.push({ value: c, text: c }); });
      if (!copts.some(function (o) { return o.value === state.colourBy; })) state.colourBy = 'none';
      fillSelect(selC, copts, state.colourBy);
      chkPCA.checked = state.pca && !!M.pca; chkPCA.disabled = !M.pca;
      selX.disabled = selY.disabled = chkPCA.checked;
      bodyA.appendChild(ctrlA);
      var row = el('div', { class: 'g-rowA' }, [drawScree(), figA]);
      bodyA.appendChild(row);
      clear(figA);
      figA.appendChild(drawScatter());
      if (chkPCA.checked) figA.appendChild(loadingsPanel());
      bodyA.appendChild(cardA);
      if (!cardA.firstChild) cardA.appendChild(para('Hover a point for its row: basis values and derived values with the rule that produced them. Drag a rectangle to filter the other views.', 'g-muted'));
    }
    function drawScree() {
      var sv = (data.space && (data.space.singular_values || data.space.explained_variance_ratio)) || (M.pca && M.pca.explained) || [];
      var W = 150, H = 200, mL = 24, mB = 22, mT = 12;
      var s = svg('svg', { class: 'g-scree', viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': 'scree of singular values' });
      if (!sv.length) { s.appendChild(svg('text', { x: 8, y: 20, class: 'g-t', text: 'no scree shipped' })); return s; }
      var max = Math.max.apply(null, sv), bw = (W - mL - 6) / sv.length;
      s.appendChild(svg('text', { x: mL, y: 9, class: 'g-t g-tt', text: data.space && data.space.singular_values ? 'singular values' : 'explained variance' }));
      sv.forEach(function (v, i) {
        var h = (H - mT - mB) * (v / max);
        s.appendChild(svg('rect', { x: mL + i * bw + 1, y: H - mB - h, width: Math.max(1, bw - 2), height: h, class: 'g-bar' + (i < 2 && state.pca ? ' g-bar-hi' : '') }));
        if (sv.length <= 12) s.appendChild(svg('text', { x: mL + i * bw + bw / 2, y: H - mB + 10, class: 'g-t g-tc', text: String(i + 1) }));
      });
      var d95 = data.space && data.space.dims_95;
      if (isNum(d95)) {
        var x = mL + d95 * bw;
        s.appendChild(svg('line', { x1: x, y1: mT, x2: x, y2: H - mB, class: 'g-thr' }));
        s.appendChild(svg('text', { x: x + 3, y: mT + 10, class: 'g-t', text: '95% at ' + d95 }));
      }
      s.appendChild(svg('text', { x: mL, y: H - 2, class: 'g-t', text: 'rank ' + fmt(data.space && data.space.exact_rank) + ' · TwoNN ' + fmt(data.space && data.space.intrinsic_dim_twonn) }));
      return s;
    }
    function colourIndexer() {
      var col = state.colourBy === 'label' ? state.activeCandidate : state.colourBy;
      var v = col && col !== 'none' ? M.values(col) : null;
      if (!v) return null;
      var cats = uniq(v.filter(function (x) { return x !== null && x !== undefined; }).map(String)).sort();
      var idx = {}; cats.forEach(function (k, i) { idx[k] = i; });
      return { col: col, cats: cats, of: function (i) { var x = v[i]; return x === null || x === undefined ? -1 : idx[String(x)]; } };
    }
    function drawScatter() {
      var W = 440, H = 300, mL = 52, mR = 14, mT = 14, mB = 44;
      var ax, ay, title;
      if (chkPCA.checked) {
        var sc = M.pca.scores, e = M.pca.explained || [];
        ax = { kind: 'num', vals: sc.map(function (r) { return r[0]; }), label: 'PC1' + (e[0] !== undefined ? ' (' + pct(e[0]) + ')' : '') };
        ay = { kind: 'num', vals: sc.map(function (r) { return r[1]; }), label: 'PC2' + (e[1] !== undefined ? ' (' + pct(e[1]) + ')' : '') };
        title = 'rotated view: shipped PCA scores';
      } else { ax = axisOf(state.axes[0]); ay = axisOf(state.axes[1]); title = 'named axes'; }
      function extent(a) { var lo = Infinity, hi = -Infinity; a.vals.forEach(function (x) { if (x === null) return; if (x < lo) lo = x; if (x > hi) hi = x; }); if (!isFinite(lo)) { lo = 0; hi = 1; } if (lo === hi) { lo -= 1; hi += 1; } var pad = (hi - lo) * 0.04; return [lo - pad, hi + pad]; }
      var ex = extent(ax), ey = extent(ay);
      var sx = function (x) { return mL + (x - ex[0]) / (ex[1] - ex[0]) * (W - mL - mR); };
      var sy = function (y) { return H - mB - (y - ey[0]) / (ey[1] - ey[0]) * (H - mT - mB); };
      var s = svg('svg', { class: 'g-scatter', viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': 'scatter of ' + ax.label + ' by ' + ay.label });
      s.appendChild(svg('rect', { x: mL, y: mT, width: W - mL - mR, height: H - mT - mB, class: 'g-plot' }));
      /* ticks */
      function ticks(a, e, n) {
        if (a.kind === 'cat') return a.cats.map(function (k, i) { return { v: i, t: k.length > 9 ? k.slice(0, 8) + '…' : k }; });
        var out = [], step = (e[1] - e[0]) / n;
        for (var i = 0; i <= n; i++) { var v = e[0] + i * step; out.push({ v: v, t: a.kind === 'date' ? new Date(v).toISOString().slice(0, 10) : fmt(+v.toPrecision(3)) }); }
        return out;
      }
      ticks(ax, ex, 4).forEach(function (t) { var x = sx(t.v); s.appendChild(svg('line', { x1: x, y1: H - mB, x2: x, y2: H - mB + 4, class: 'g-axis' })); s.appendChild(svg('text', { x: x, y: H - mB + 14, class: 'g-t g-tc', text: t.t })); });
      ticks(ay, ey, 4).forEach(function (t) { var y = sy(t.v); s.appendChild(svg('line', { x1: mL - 4, y1: y, x2: mL, y2: y, class: 'g-axis' })); s.appendChild(svg('text', { x: mL - 6, y: y + 3, class: 'g-t g-tr', text: t.t })); });
      s.appendChild(svg('text', { x: mL + (W - mL - mR) / 2, y: H - 4, class: 'g-t g-tc g-tt', text: ax.label }));
      s.appendChild(svg('text', { x: 12, y: mT + (H - mT - mB) / 2, class: 'g-t g-tc g-tt', transform: 'rotate(-90 12 ' + (mT + (H - mT - mB) / 2) + ')', text: ay.label }));
      s.appendChild(svg('text', { x: W - mR, y: mT - 3, class: 'g-t g-tr', text: title }));
      var ci = colourIndexer();
      var selected = state.selectedRows ? state.selectedRows.reduce(function (m, i) { m[i] = 1; return m; }, {}) : null;
      var pts = svg('g', { class: 'g-pts' });
      for (var i = 0; i < M.rows; i++) {
        var x = ax.vals[i], y = ay.vals[i];
        if (x === null || y === null || x === undefined || y === undefined) continue;
        var k = ci ? ci.of(i) : -1;
        var jx = ax.kind === 'cat' ? (((i * 7919) % 17) / 17 - 0.5) * 0.5 : 0, jy = ay.kind === 'cat' ? (((i * 104729) % 13) / 13 - 0.5) * 0.5 : 0;
        pts.appendChild(svg('circle', { cx: sx(x + jx).toFixed(1), cy: sy(y + jy).toFixed(1), r: 3, 'data-i': i,
          fill: k >= 0 ? PALETTE[k % PALETTE.length] : 'currentColor', class: 'g-pt' + (selected && !selected[i] ? ' g-dim' : '') }));
      }
      s.appendChild(pts);
      if (ci) {
        var lg = svg('g', { class: 'g-legend' });
        ci.cats.forEach(function (c, j) {
          lg.appendChild(svg('circle', { cx: mL + 8, cy: mT + 10 + j * 13, r: 4, fill: PALETTE[j % PALETTE.length] }));
          lg.appendChild(svg('text', { x: mL + 16, y: mT + 13 + j * 13, class: 'g-t', text: ci.col + ' = ' + c }));
        });
        s.appendChild(lg);
      }
      /* hover → row card (delegated) */
      s.addEventListener('mousemove', function (e) {
        var t = e.target; if (!t || !t.getAttribute || t.getAttribute('data-i') === null) return;
        var i = +t.getAttribute('data-i'); if (i === state.hoverRow) return; state.hoverRow = i; rowCard(i);
      });
      /* brush: rectangle in plot coordinates → selectedRows */
      var brush = null, rect = svg('rect', { class: 'g-brush', x: 0, y: 0, width: 0, height: 0, visibility: 'hidden' });
      s.appendChild(rect);
      function pt(e) { var p = s.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; var m = s.getScreenCTM(); return m ? p.matrixTransform(m.inverse()) : p; }
      s.addEventListener('mousedown', function (e) { if (e.button !== 0) return; brush = pt(e); rect.setAttribute('visibility', 'visible'); e.preventDefault(); });
      s.addEventListener('mousemove', function (e) {
        if (!brush) return; var p = pt(e);
        rect.setAttribute('x', Math.min(brush.x, p.x)); rect.setAttribute('y', Math.min(brush.y, p.y));
        rect.setAttribute('width', Math.abs(p.x - brush.x)); rect.setAttribute('height', Math.abs(p.y - brush.y));
      });
      function finish(e) {
        if (!brush) return; var p = pt(e), x0 = Math.min(brush.x, p.x), x1 = Math.max(brush.x, p.x), y0 = Math.min(brush.y, p.y), y1 = Math.max(brush.y, p.y);
        brush = null; rect.setAttribute('visibility', 'hidden');
        if (x1 - x0 < 4 || y1 - y0 < 4) { if (state.selectedRows) { state.selectedRows = null; redraw(); } return; }
        var sel = [];
        for (var i = 0; i < M.rows; i++) { var cx = ax.vals[i], cy = ay.vals[i]; if (cx === null || cy === null) continue; var px = sx(cx), py = sy(cy); if (px >= x0 && px <= x1 && py >= y0 && py <= y1) sel.push(i); }
        state.selectedRows = sel; redraw();
      }
      s.addEventListener('mouseup', finish); s.addEventListener('mouseleave', function (e) { if (brush) finish(e); });
      return s;
    }
    function loadingsPanel() {
      var p = M.pca, cols = p.columns || [], box = el('div', { class: 'g-loadings' }, [el('h5', { text: 'What the components are made of' })]);
      [0, 1].forEach(function (k) {
        var L = (p.loadings || [])[k]; if (!L) return;
        var pairs = cols.map(function (c, i) { return { c: c, v: L[i] }; }).sort(function (a, b) { return Math.abs(b.v) - Math.abs(a.v); });
        var line = el('div', { class: 'g-load' }, [el('strong', { text: 'PC' + (k + 1) + (p.explained && p.explained[k] !== undefined ? ' (' + pct(p.explained[k]) + ')' : '') + ' = ' })]);
        pairs.slice(0, 6).forEach(function (q) { line.appendChild(chip((q.v >= 0 ? '+' : '−') + Math.abs(q.v).toFixed(2) + ' ' + q.c, Math.abs(q.v) >= 0.3 ? 'g-chip-strong' : '')); });
        box.appendChild(line);
      });
      box.appendChild(para('Loadings are the shipped PCA on standardized numeric columns; the rotation has no names of its own, which is why the report keeps the named basis.', 'g-muted'));
      return box;
    }
    function rowCard(i) {
      clear(cardA);
      cardA.appendChild(el('h5', { text: 'Row ' + (M.explore.index ? M.explore.index[i] : i) }));
      var B = basis(), rules = activeRules();
      var t = el('table', { class: 'g-kv' });
      B.forEach(function (c) { var v = M.values(c); if (!v) return; t.appendChild(el('tr', null, [el('th', { text: c }), el('td', { text: fmt(v[i]) }), el('td', { class: 'g-muted', text: 'basis' })])); });
      rules.forEach(function (r) {
        var v = M.values(r.column); if (!v) return;
        var pr = r.provenance, tag = r.rule_id + ' · ' + pr.semantic.status[0].toUpperCase() + '/' + pr.symbolic.status[0].toUpperCase() + '/' + pr.empirical.status[0].toUpperCase();
        t.appendChild(el('tr', { class: 'g-derived' }, [el('th', { text: r.column }), el('td', { text: fmt(v[i]) }), el('td', { class: 'g-muted', title: 'semantic/symbolic/empirical: ' + pr.semantic.status + '/' + pr.symbolic.status + '/' + pr.empirical.status, text: tag })]));
      });
      cardA.appendChild(t);
    }

    /* ================================================================ View B — Derivation graph
       Contract: nodes = columns; solid directed edges body → head for active rules; dashed
       edges for functional dependencies; cycles outlined; basis filled, derived hollow, identities
       greyed; click → card with typing, provenance, consequences, disagreements, re-orientation. */
    var graphWrap = el('div', { class: 'g-graph' }), cardB = el('div', { class: 'g-card' });
    function layoutGraph(rules) {
      var heads = {}; rules.forEach(function (r) { heads[r.column] = r; });
      var tier = {};
      function tierOf(c, seen) {
        if (tier[c] !== undefined) return tier[c];
        if (M.excluded(c) || !heads[c]) return (tier[c] = 0);
        seen = seen || {}; if (seen[c]) return 0; seen[c] = 1;
        var t = 0; heads[c].body.forEach(function (b) { if (contains(M.columns, b)) t = Math.max(t, tierOf(b, seen) + 1); });
        return (tier[c] = t);
      }
      M.columns.forEach(function (c) { tierOf(c); });
      /* components over rule edges (undirected), excluded columns kept apart */
      var comp = {}; M.columns.forEach(function (c) { comp[c] = c; });
      function find(c) { while (comp[c] !== c) c = comp[c]; return c; }
      rules.forEach(function (r) { r.body.forEach(function (b) { if (comp[b] !== undefined && !M.excluded(b) && !M.excluded(r.column)) comp[find(b)] = find(r.column); }); });
      var groups = {}; M.columns.forEach(function (c) { var k = M.excluded(c) ? '__excluded' : find(c); (groups[k] = groups[k] || []).push(c); });
      var order = Object.keys(groups).filter(function (k) { return k !== '__excluded'; }).sort(function (a, b) { return groups[b].length - groups[a].length || a.localeCompare(b); });
      if (groups.__excluded) order.push('__excluded');
      var pos = {}, y = 18, tierX = function (t) { return 70 + t * 175; }, rowH = 46, maxTier = 0;
      order.forEach(function (k) {
        var cols = groups[k].slice().sort(function (a, b) { return tier[a] - tier[b] || M.columns.indexOf(a) - M.columns.indexOf(b); });
        var rowsAt = {}, h = 0;
        cols.forEach(function (c) { var t = tier[c]; rowsAt[t] = rowsAt[t] || 0; pos[c] = { x: tierX(t), y: y + rowsAt[t] * rowH + 14, tier: t }; rowsAt[t]++; h = Math.max(h, rowsAt[t]); maxTier = Math.max(maxTier, t); });
        y += h * rowH + 14;
      });
      return { pos: pos, W: tierX(maxTier) + 110, H: y + 4, heads: heads };
    }
    function drawB() {
      clear(bodyB);
      var rules = activeRules(), L = layoutGraph(rules), B = basis();
      var cand = state.activeCandidate ? candidates().find(function (c) { return c.label === state.activeCandidate; }) : null;
      var s = svg('svg', { class: 'g-dag', viewBox: '0 0 ' + L.W + ' ' + L.H, width: L.W, height: L.H, role: 'group', 'aria-label': 'derivation graph' });
      var defs = svg('defs');
      defs.appendChild(svg('marker', { id: 'lg-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto' }, [svg('path', { d: 'M0,0 L10,5 L0,10 z', class: 'g-arrowhead' })]));
      defs.appendChild(svg('marker', { id: 'lg-arrow-fd', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto' }, [svg('path', { d: 'M0,0 L10,5 L0,10 z', class: 'g-arrowhead-fd' })]));
      s.appendChild(defs);
      /* cycle outlines */
      M.cycles.forEach(function (cy) {
        var ps = cy.members.filter(function (c) { return L.pos[c]; }).map(function (c) { return L.pos[c]; });
        if (!ps.length) return;
        var x0 = Math.min.apply(null, ps.map(function (p) { return p.x; })) - 22, x1 = Math.max.apply(null, ps.map(function (p) { return p.x; })) + 22;
        var y0 = Math.min.apply(null, ps.map(function (p) { return p.y; })) - 16, y1 = Math.max.apply(null, ps.map(function (p) { return p.y; })) + 26;
        var o = orientationOf(cy);
        s.appendChild(svg('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, rx: 12, class: 'g-cycle' + (o.isDefault ? '' : ' g-cycle-re') }));
        s.appendChild(svg('text', { x: x0 + 6, y: y0 - 3, class: 'g-t g-cyt', text: 'cycle ' + cy.id + (o.isDefault ? '' : ' · ' + o.id) }));
      });
      /* FD edges (dashed curves) */
      M.fds.forEach(function (f) {
        var h = L.pos[f.rhs]; if (!h) return;
        f.lhs.forEach(function (b) {
          var p = L.pos[b]; if (!p) return;
          var mx = (p.x + h.x) / 2, my = (p.y + h.y) / 2 - 24 - (p.x > h.x ? 12 : 0);
          s.appendChild(svg('path', { d: 'M' + (p.x + 9) + ',' + (p.y - 4) + ' Q' + mx + ',' + my + ' ' + (h.x - 9) + ',' + (h.y - 4), class: 'g-edge-fd', 'marker-end': 'url(#lg-arrow-fd)' }, [svg('title', { text: 'FD ' + f.lhs.join('+') + ' → ' + f.rhs + (f.exact ? ' (exact)' : '') })]));
        });
      });
      /* rule edges */
      rules.forEach(function (r) {
        var h = L.pos[r.column]; if (!h) return;
        r.body.forEach(function (b) {
          var p = L.pos[b]; if (!p) return;
          var dx = h.x - p.x, dy = h.y - p.y, d = Math.sqrt(dx * dx + dy * dy) || 1, ux = dx / d, uy = dy / d;
          s.appendChild(svg('line', { x1: p.x + ux * 10, y1: p.y + uy * 10, x2: h.x - ux * 11, y2: h.y - uy * 11, class: 'g-edge' + (r.layer === 'rules' || r.layer === 'horn' ? ' g-edge-horn' : ''), 'marker-end': 'url(#lg-arrow)' }, [svg('title', { text: r.rule_id + ': ' + r.formula })]));
        });
      });
      /* nodes */
      M.columns.forEach(function (c) {
        var p = L.pos[c]; if (!p) return;
        var kind = M.excluded(c) ? 'g-n-id' : contains(B, c) ? 'g-n-basis' : 'g-n-derived';
        var cls = 'g-node ' + kind + (state.selectedNode === c ? ' g-n-sel' : '');
        if (cand) { if (contains(cand.features, c)) cls += ' g-n-feat'; else if (contains(cand.dropped, c)) cls += ' g-n-leak'; else if (c === cand.label) cls += ' g-n-label'; }
        var g = svg('g', { class: cls, tabindex: 0, role: 'button', 'data-col': c, 'aria-label': c + ' (' + (M.excluded(c) ? M.role(c) : contains(B, c) ? 'basis' : 'derived') + ')' });
        g.appendChild(svg('title', { text: c + ' — ' + M.typeOf(c) + ', ' + M.role(c) }));
        if (cand && contains(cand.features, c)) g.appendChild(svg('circle', { cx: p.x, cy: p.y, r: 13, class: 'g-halo' }));
        g.appendChild(svg('circle', { cx: p.x, cy: p.y, r: 8 }));
        g.appendChild(svg('text', { x: p.x, y: p.y + 21, class: 'g-t g-tc g-nl', text: c }));
        if (cand && contains(cand.dropped, c)) g.appendChild(svg('line', { x1: p.x - c.length * 3.2, y1: p.y + 18, x2: p.x + c.length * 3.2, y2: p.y + 18, class: 'g-strike' }));
        var open = function () { state.selectedNode = c; redraw(); focusLater('[data-view="derivations"] [data-col="' + c + '"]'); };
        g.onclick = open; g.onkeydown = keyed(open);
        s.appendChild(g);
      });
      clear(graphWrap); graphWrap.appendChild(s);
      bodyB.appendChild(el('div', { class: 'g-legendB' }, [chip('● basis', 'g-lg-basis'), chip('○ derived', 'g-lg-derived'), chip('● identity / key', 'g-lg-id'), chip('→ rule (SWRL solid, Horn dotted)', ''), chip('⇢ functional dependency', ''), chip('▭ cycle', '')]));
      bodyB.appendChild(graphWrap);
      bodyB.appendChild(cardB);
      drawNodeCard(rules, B);
    }
    function drawNodeCard(rules, B) {
      clear(cardB);
      var c = state.selectedNode;
      if (!c) {
        cardB.appendChild(para(M.cycles.length ? 'Click a column for its card. Inside a cycle the card offers "make this the basis member": the basis is recomputed here as the columns that are the head of no active rule, and View D’s candidates follow.' : 'Click a column for its card: type, provenance triple, consequences.', 'g-muted'));
        var reor = M.cycles.filter(function (cy) { return !orientationOf(cy).isDefault; });
        reor.forEach(function (cy) { cardB.appendChild(consequenceBlock(orientationOf(cy).consequences, 'Orientation ' + cy.id + ' → ' + orientationOf(cy).id)); });
        return;
      }
      var t = M.typing[c] || {}, rule = rules.find(function (r) { return r.column === c; }), isB = contains(B, c);
      var h = el('div', { class: 'g-cardhead' }, [el('h4', { text: c }), chip(M.typeOf(c), ''), chip(M.excluded(c) ? M.role(c) : isB ? 'basis member' : 'derived', isB ? 'g-chip-strong' : '')]);
      if (t.script_type && t.final_type && t.script_type !== t.final_type) h.appendChild(chip('retyped ' + t.script_type + ' → ' + t.final_type, 'g-st-refuted'));
      cardB.appendChild(h);
      if (t.reason) cardB.appendChild(para(t.reason));
      var ss = selectionSummary(c); if (ss) cardB.appendChild(para(ss, 'g-muted'));
      if (rule) {
        cardB.appendChild(el('p', { class: 'g-formula' }, [el('code', { text: rule.formula }), ' ', chip(rule.rule_id + ' · ' + rule.layer, '')]));
        cardB.appendChild(provenanceBlock(rule.provenance));
        cardB.appendChild(consequenceBlock(rule.consequences, rule.orientation ? 'Consequences of orientation ' + rule.orientation.id : 'Consequences'));
      } else if (isB) {
        var heads = rules.filter(function (r) { return contains(r.body, c); });
        cardB.appendChild(para('Head of no active rule' + (heads.length ? '; body of ' + heads.map(function (r) { return r.rule_id + ' (' + r.column + ')'; }).join(', ') : '') + '.'));
        var cy0 = M.cycleOf(c); if (cy0) cardB.appendChild(consequenceBlock(orientationOf(cy0).consequences, 'Consequences of the current orientation'));
      } else if (M.excluded(c)) cardB.appendChild(para('Outside the span: ' + M.role(c) + ' columns determine (or point at) rows and are excluded from every dependency measure.'));
      var cy = M.cycleOf(c);
      if (cy) {
        var o = orientationOf(cy);
        var box = el('div', { class: 'g-cyclebox' }, [el('h5', { text: 'Cycle ' + cy.id + ': ' + cy.members.join(' · ') })]);
        if (cy.reading) box.appendChild(para(cy.reading, 'g-muted'));
        box.appendChild(para('Current orientation: ' + (o.isDefault ? 'the report’s (' + o.id + ')' : o.id + (o.adhoc ? ' (ad hoc: rule deactivated, no pre-written consequences)' : '')) + ' — basis members ' + o.basis.join(', ') + '.'));
        var alts = cy.orientations.filter(function (x) { return x.id !== o.id && contains(x.basis, c); });
        alts.forEach(function (x) {
          box.appendChild(el('button', { class: 'g-btn g-btn-primary', type: 'button', onclick: function () { reorient(c, x.id); focusLater('[data-view="derivations"] [data-col="' + c + '"]'); } },
            [(contains(o.basis, c) ? 'Keep ' + c + ' in the basis' : 'Make ' + c + ' the basis member') + (x.consequences && x.consequences.decision ? ' — ' + x.consequences.decision : ' (' + x.id + ')')]));
        });
        if (!alts.length && !contains(o.basis, c)) box.appendChild(el('button', { class: 'g-btn', type: 'button', onclick: function () { reorient(c); } }, ['Make ' + c + ' a basis member (no pre-written orientation: deactivates ' + (rule ? rule.rule_id : 'its rule') + ')']));
        if (!o.isDefault) box.appendChild(el('button', { class: 'g-btn', type: 'button', onclick: function () { resetOrientation(cy.id); } }, ['Reset this cycle to the report’s orientation']));
        cardB.appendChild(box);
      }
      var dis = M.disagreements.filter(function (d) { return d.column === c || contains(d.with || [], c) || (d.reading || '').indexOf(c) >= 0; });
      var mk = M.markers.filter(function (m) { return /^WARN/.test(String(m)) && String(m).indexOf(c) >= 0; });
      if (dis.length || mk.length) {
        var dbox = el('div', { class: 'g-dis' }, [el('h5', { text: 'Disagreements and warnings' })]);
        dis.forEach(function (d) { dbox.appendChild(el('p', null, [chip(d.kind || 'disagreement', 'g-st-refuted'), ' ', d.evidence ? el('span', { class: 'g-muted', text: d.evidence + ' — ' }) : null, d.reading || ''])); });
        mk.forEach(function (m) { dbox.appendChild(el('p', { class: 'g-mk-warn', text: String(m) })); });
        cardB.appendChild(dbox);
      }
    }

    /* ================================================================ View C — Orthogonality
       Contract: heatmap of the shipped pair measures among the current basis members, NMI as the
       common scale, thresholds from the data; click a cell → View A axes; independence reading beside. */
    function drawC() {
      clear(bodyC);
      var B = basis();
      if (!M.explore) {
        bodyC.appendChild(el('div', { class: 'g-empty' }, [
          para('No explorer sample, so the heatmap is withheld: its cells open pairs as the axes of View A, which has nothing to plot. The pair measures themselves are in the reading below.'),
          para((data.orthogonality && data.orthogonality.reading) || '', 'g-prose')]));
        return;
      }
      if (!Object.keys(M.pairs).length) {
        bodyC.appendChild(el('div', { class: 'g-empty' }, [para('No pair measures shipped (orthogonality.pairs is absent), so there is nothing to map.'), para((data.orthogonality && data.orthogonality.reading) || '', 'g-prose')]));
        return;
      }
      var cell = 34, mL = 96, mT = 92, n = B.length, W = mL + n * cell + 8, H = mT + n * cell + 8, thr = isNum(M.thresholds.nmi) ? M.thresholds.nmi : 0.5;
      var s = svg('svg', { class: 'g-heat', viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'group', 'aria-label': 'orthogonality heatmap' });
      B.forEach(function (c, i) {
        s.appendChild(svg('text', { x: mL - 6, y: mT + i * cell + cell / 2 + 4, class: 'g-t g-tr', text: c }));
        s.appendChild(svg('text', { x: mL + i * cell + cell / 2, y: mT - 6, class: 'g-t', transform: 'rotate(-60 ' + (mL + i * cell + cell / 2) + ' ' + (mT - 6) + ')', text: c }));
      });
      B.forEach(function (a, i) {
        B.forEach(function (b, j) {
          var x = mL + j * cell, y = mT + i * cell;
          if (i === j) { s.appendChild(svg('rect', { x: x, y: y, width: cell, height: cell, class: 'g-hc g-hc-diag' })); return; }
          var p = M.pair(a, b), v = p && isNum(p.nmi) ? p.nmi : null;
          var over = v !== null && v >= thr;
          var g = svg('g', { class: 'g-hcell' + (over ? ' g-hc-over' : '') + (state.selectedPair && state.selectedPair[0] === a && state.selectedPair[1] === b ? ' g-hc-sel' : ''), tabindex: 0, role: 'button', 'aria-label': a + ' × ' + b + ': nmi ' + (v === null ? 'not shipped' : fmt(v)) });
          g.appendChild(svg('title', { text: a + ' × ' + b + (v === null ? ': not shipped' : ': nmi ' + fmt(v) + measureText(p)) }));
          g.appendChild(svg('rect', { x: x, y: y, width: cell, height: cell, class: 'g-hc', 'fill-opacity': v === null ? 0 : Math.min(1, 0.08 + 0.92 * Math.pow(v / Math.max(thr * 2, 0.01), 0.7)) }));
          g.appendChild(svg('text', { x: x + cell / 2, y: y + cell / 2 + 3, class: 'g-t g-tc g-hv' + (v !== null && v >= thr ? ' g-hv-hi' : ''), text: v === null ? '–' : v.toFixed(2) }));
          var open = function () { state.selectedPair = [a, b]; if (plottable(a) && plottable(b)) { state.axes = [a, b]; state.pca = false; } redraw(); focusLater('[data-view="orthogonality"] [aria-label^="' + a + ' × ' + b + '"]'); };
          g.onclick = open; g.onkeydown = keyed(open);
          s.appendChild(g);
        });
      });
      bodyC.appendChild(el('div', { class: 'g-rowC' }, [el('div', { class: 'g-scrollx' }, [s]), pairDetail()]));
      bodyC.appendChild(para('Colour: NMI from 0 (paper) through the threshold nmi ≥ ' + thr + ' (outlined). Measures are computed on all ' + (src.rows || M.rows) + ' rows by geometry.py' + (state.selectedRows ? '; the brush selection does not recompute them' : '') + '.', 'g-muted'));
    }
    function measureText(p) {
      if (!p) return '';
      var out = [];
      ['pearson', 'spearman', 'eta2', 'cramers_v'].forEach(function (k) { if (isNum(p[k])) out.push(k + ' ' + fmt(p[k])); });
      return out.length ? ' · ' + out.join(', ') : '';
    }
    function pairDetail() {
      var box = el('div', { class: 'g-card g-pair' });
      if (!state.selectedPair) { box.appendChild(para('Click a cell: the pair opens as the axes of View A and its independence reading appears here.', 'g-muted')); return box; }
      var a = state.selectedPair[0], b = state.selectedPair[1], p = M.pair(a, b);
      box.appendChild(el('h5', { text: a + ' × ' + b }));
      if (!p) { box.appendChild(para('No measure shipped for this pair (it was not in the report’s basis when geometry.json was summarized).', 'g-muted')); return box; }
      var t = el('table', { class: 'g-kv' });
      ['nmi', 'pearson', 'spearman', 'eta2', 'cramers_v'].forEach(function (k) {
        if (!isNum(p[k])) return;
        var th = M.thresholds[k];
        t.appendChild(el('tr', null, [el('th', { text: k }), el('td', { text: fmt(p[k]) }), el('td', { class: 'g-muted', text: isNum(th) ? (Math.abs(p[k]) >= th ? 'at or above threshold ' + th : 'below threshold ' + th) : '' })]));
      });
      box.appendChild(t);
      box.appendChild(para(p.independence || 'no independence reading shipped for this pair', p.independence ? 'g-indep' : 'g-muted'));
      return box;
    }

    /* ================================================================ View D — Partition
       Contract: label candidates as selectable cards; selecting one highlights the remaining
       features on B, strikes the leakage set, shows the input dimension and consequences, and
       colours A by the label. Candidates follow the current basis (rule heads whose body ⊆ basis). */
    function drawD() {
      clear(bodyD);
      var cs = candidates(), P = data.partitions || {};
      bodyD.appendChild(para((P.chosen ? 'Report’s choice: ' + P.chosen + ' (' + (P.provenance || 'unstated') + '). ' : 'The report chose no partition. ') + (P.reading || ''), 'g-muted'));
      if (!cs.length) { bodyD.appendChild(el('div', { class: 'g-empty' }, [para('No label candidate: no active rule has its whole body in the current basis, and no functional dependency determines a column from it.')])); return; }
      var list = el('div', { class: 'g-cards', role: 'group', 'aria-label': 'partition candidates' });
      cs.forEach(function (c) {
        var on = state.activeCandidate === c.label;
        var btn = el('button', { class: 'g-cand' + (on ? ' g-cand-on' : '') + (c.stated ? '' : ' g-cand-struct'), type: 'button', 'aria-pressed': on ? 'true' : 'false', 'data-label': c.label,
          onclick: function () { state.activeCandidate = on ? null : c.label; state.colourBy = on ? 'none' : 'label'; redraw(); focusLater('[data-view="partition"] [data-label="' + c.label + '"]'); } },
          [el('strong', { text: c.label }), ' ', chip(c.task, ''), chip(c.rule_id, ''), chip(c.stated ? (c.structural ? 'stated by the report' : 'stated, not derivable from this basis') : 'structural only', c.stated ? 'g-chip-strong' : '')]);
        list.appendChild(btn);
      });
      bodyD.appendChild(list);
      var c = cs.find(function (x) { return x.label === state.activeCandidate; });
      if (c) {
        var box = el('div', { class: 'g-card' }, [el('h5', { text: c.label + ' as the label' })]);
        var feats = el('p', null, [el('strong', { text: 'features (' + c.features.length + '): ' })]);
        c.features.forEach(function (f) { feats.appendChild(chip(f, 'g-lg-basis')); });
        box.appendChild(feats);
        var leak = el('p', null, [el('strong', { text: 'dropped for leakage: ' })]);
        if (c.dropped.length) c.dropped.forEach(function (f) { leak.appendChild(chip(f, 'g-leak')); }); else leak.appendChild(document.createTextNode('none'));
        box.appendChild(leak);
        var dim = c.features.length;
        box.appendChild(para('Input dimension the downstream model receives: ' + dim + (c.stated && isNum(c.stated.input_dim) && c.stated.input_dim !== dim ? ' (the report stated ' + c.stated.input_dim + ' for its own orientation)' : '') + '.'));
        if (c.stated && c.stated.reading) box.appendChild(para(c.stated.reading));
        if (!c.stated) box.appendChild(para('The report did not defend this candidate; it is listed because its rule’s body lies in the current basis. Predicting arithmetic or a lookup is a rule, not a learning task.', 'g-muted'));
        var ld = labelDistribution(c.label); if (ld) box.appendChild(para(ld, 'g-muted'));
        box.appendChild(consequenceBlock(c.stated ? c.stated.consequences : null));
        bodyD.appendChild(box);
      }
      var hand = data.handoff || {};
      bodyD.appendChild(para(hand.nn_data_artifact ? 'Materialized: ' + hand.nn_data_artifact + '. ' + (hand.note || '') :
        'Materialize: the chosen partition becomes an nn-data artifact when /dataset-forge is re-run with --partition <label>; this layer cannot write files. ' + (hand.note || ''), 'g-note'));
    }
    function labelDistribution(label) {
      var v = M.values(label); if (!v) return null;
      var idx = state.selectedRows || null, cnt = {}, n = 0;
      (idx || v.map(function (_, i) { return i; })).forEach(function (i) { var x = v[i]; if (x === null || x === undefined) return; cnt[x] = (cnt[x] || 0) + 1; n++; });
      var ks = Object.keys(cnt).sort();
      if (ks.length > 8) return (idx ? 'Selected rows: ' : 'Sample: ') + ks.length + ' distinct values over ' + n + ' rows.';
      return (idx ? 'Selected rows: ' : 'Sample: ') + ks.map(function (k) { return k + ' ×' + cnt[k]; }).join(', ') + ' (' + n + ' rows).';
    }

    /* ---------------------------------------------------------------- redraw all */
    var pendingFocus = null;
    function focusLater(sel) { pendingFocus = sel; }
    function redraw() {
      drawStatus(); drawA(); drawB(); drawC(); drawD();
      if (pendingFocus) { var n = pane.querySelector(pendingFocus); pendingFocus = null; if (n && n.focus) try { n.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
    }
    redraw();

    /* Minimal test hook (contract: keep it tiny). */
    window.__geometry = { state: state, reorient: reorient, basis: basis, candidates: candidates, version: VERSION };
  }

  ready(function () { try { build(); } catch (e) { console.error('[geometry] render failed', e); } });
})();
