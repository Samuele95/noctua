// ── capability: 00-core ──────────────────────────────────────────────
// The reasoner's state shape and the four "infer*" / two "assert*"
// helpers that every capability uses to mutate R. Also the orchestrator
// runReasoner() that calls each capability once per fixpoint iteration.
function initReasonerState(){
  const R = {
    classSupers: new Map(),   // class IRI → { asserted: Set<IRI>, inferred: Map<IRI, prov> }
    propSupers:  new Map(),   // property IRI → same shape
    indClasses:  new Map(),   // individual IRI → same shape (membership)
    facts: { asserted: [], inferred: [] },  // { s, p, o|v, kind, prov? }
    iterations: 0,
    seenObj: new Set(), seenData: new Set(),
    seenMem: new Set(), seenSubC: new Set(), seenSubP: new Set(),
    contradictions: [],
  };
  const keyObj  = (s,p,o) => `${s}|${p}|${o}`;
  const keyData = (s,p,v) => `${s}|${p}|${typeof v === 'string' ? '"'+v+'"' : v}`;
  const keyMem  = (i,c)   => `${i}|${c}`;
  const keyK    = (a,b)   => `${a}|${b}`;
  R.keyMem = keyMem; R.keyK = keyK;
  R.assertObj = (s,p,o) => { const k=keyObj(s,p,o); if(R.seenObj.has(k)) return false;
    R.seenObj.add(k); R.facts.asserted.push({s,p,o,kind:'object'}); return true; };
  R.assertData = (s,p,v) => { const k=keyData(s,p,v); if(R.seenData.has(k)) return false;
    R.seenData.add(k); R.facts.asserted.push({s,p,v,kind:'data'}); return true; };
  R.inferObj = (s,p,o,prov) => { const k=keyObj(s,p,o); if(R.seenObj.has(k)) return false;
    R.seenObj.add(k); R.facts.inferred.push({s,p,o,kind:'object',prov}); return true; };
  R.inferData = (s,p,v,prov) => { const k=keyData(s,p,v); if(R.seenData.has(k)) return false;
    R.seenData.add(k); R.facts.inferred.push({s,p,v,kind:'data',prov}); return true; };
  R.inferSubC = (child,parent,prov) => { if(child===parent) return false;
    const k=keyK(child,parent); if(R.seenSubC.has(k)) return false; R.seenSubC.add(k);
    if (!R.classSupers.has(child)) R.classSupers.set(child, {asserted:new Set(), inferred:new Map()});
    R.classSupers.get(child).inferred.set(parent, prov); return true; };
  R.inferSubP = (child,parent,prov) => { if(child===parent) return false;
    const k=keyK(child,parent); if(R.seenSubP.has(k)) return false; R.seenSubP.add(k);
    if (!R.propSupers.has(child)) R.propSupers.set(child, {asserted:new Set(), inferred:new Map()});
    R.propSupers.get(child).inferred.set(parent, prov); return true; };
  R.inferMem = (ind,cls,prov) => { const k=keyMem(ind,cls); if(R.seenMem.has(k)) return false;
    R.seenMem.add(k);
    if (!R.indClasses.has(ind)) R.indClasses.set(ind, {asserted:new Set(), inferred:new Map()});
    R.indClasses.get(ind).inferred.set(cls, prov); return true; };
  return R;
}

function seedAssertedFacts(R){
  // Classes: asserted subClassOf + equivalentClass → bidirectional inferred subclass.
  classes().forEach(c => {
    const asserted = new Set(subClassesOf(c));
    R.classSupers.set(c['@id'], { asserted, inferred: new Map() });
    asserted.forEach(p => R.seenSubC.add(R.keyK(c['@id'], p)));
    equivalentClassesOf(c).forEach(eq => {
      R.inferSubC(c['@id'], eq, { kind:'equivalentClass', from: c['@id'], to: eq });
      R.inferSubC(eq, c['@id'], { kind:'equivalentClass', from: eq, to: c['@id'] });
    });
  });
  // Properties: asserted subPropertyOf.
  [...objProps(), ...dataProps()].forEach(p => {
    const asserted = new Set(subPropertyOf(p));
    R.propSupers.set(p['@id'], { asserted, inferred: new Map() });
    asserted.forEach(s => R.seenSubP.add(R.keyK(p['@id'], s)));
  });
  // Individuals: types + per-property facts.
  individuals().forEach(i => {
    const types = new Set(asArray(i['@type']));
    R.indClasses.set(i['@id'], { asserted: types, inferred: new Map() });
    types.forEach(t => R.seenMem.add(R.keyMem(i['@id'], t)));
    Object.keys(i).forEach(k => {
      if (k.startsWith('@') || k === 'component' || k === 'label' || k === 'comment') return;
      const prop = M.byId[k];
      if (!prop) return;
      const vals = asArray(i[k]);
      vals.forEach(v => {
        const out = (v && typeof v === 'object' && v['@id']) ? v['@id'] : v;
        if (isType(prop, 'owl:ObjectProperty')) R.assertObj(i['@id'], k, out);
        else if (isType(prop, 'owl:DatatypeProperty')) R.assertData(i['@id'], k, out);
      });
    });
  });
}

function runReasoner(){
  const R = initReasonerState();
  seedAssertedFacts(R);
  let changed = true;
  while (changed && R.iterations < 100) {
    changed = false;
    R.iterations++;
    if (inferSubClassClosure(R))            changed = true;
    if (inferClassMembershipInheritance(R)) changed = true;
    if (inferSubPropertyClosure(R))         changed = true;
    if (inferPropertyCharacteristics(R))    changed = true;
    if (inferSWRL(R))                       changed = true;
  }
  detectContradictions(R);
  return R;
}
