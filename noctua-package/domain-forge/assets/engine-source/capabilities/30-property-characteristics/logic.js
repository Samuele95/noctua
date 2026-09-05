// ── capability: 30-property-characteristics ──────────────────────────
// OWL Symmetric, Transitive, InverseOf, plus the subPropertyOf-forward
// propagation onto every object/data fact. Reads R.facts + R.propSupers,
// writes via R.inferObj / R.inferData.
function inferPropertyCharacteristics(R){
  let changed = false;
  objProps().forEach(p => {
    const pIri = p['@id'];
    const chars = characteristicsOf(p);
    const inv = inverseOfProp(p);
    const allFacts = [...R.facts.asserted, ...R.facts.inferred]
      .filter(f => f.p === pIri && f.kind === 'object');

    if (chars.includes('Symmetric')) {
      allFacts.forEach(f => {
        if (R.inferObj(f.o, pIri, f.s, { kind:'symmetric', via: pIri })) changed = true;
      });
    }
    if (chars.includes('Transitive')) {
      allFacts.forEach(f1 => allFacts.forEach(f2 => {
        if (f1.o === f2.s && f1.s !== f2.o) {
          if (R.inferObj(f1.s, pIri, f2.o, { kind:'transitive', via: pIri, through: f1.o })) changed = true;
        }
      }));
    }
    if (inv) {
      allFacts.forEach(f => {
        if (R.inferObj(f.o, inv, f.s, { kind:'inverseOf', via: pIri })) changed = true;
      });
    }
    const supersInfo = R.propSupers.get(pIri);
    if (supersInfo) {
      const supers = new Set([...supersInfo.asserted, ...supersInfo.inferred.keys()]);
      supers.forEach(sup => {
        allFacts.forEach(f => {
          if (R.inferObj(f.s, sup, f.o, { kind:'subPropertyOf', via: pIri, sup })) changed = true;
        });
      });
    }
  });
  // Data property subPropertyOf forward propagation.
  dataProps().forEach(p => {
    const pIri = p['@id'];
    const supersInfo = R.propSupers.get(pIri);
    if (!supersInfo) return;
    const supers = new Set([...supersInfo.asserted, ...supersInfo.inferred.keys()]);
    if (!supers.size) return;
    const allFacts = [...R.facts.asserted, ...R.facts.inferred]
      .filter(f => f.p === pIri && f.kind === 'data');
    supers.forEach(sup => allFacts.forEach(f => {
      if (R.inferData(f.s, sup, f.v, { kind:'subPropertyOf', via: pIri, sup })) changed = true;
    }));
  });
  return changed;
}

// ── support: SWRL antecedent matching ──
// Pure helpers used by inferSWRL(). matchAtom dispatches on
// atom.type (class/objectProperty/dataProperty/builtin/sameAs/
// differentFrom); matchAntecedent threads bindings; unify
// implements first-order unification on variables/literals.
function matchAntecedent(atoms, R){
  let bindings = [{}];
  for (const atom of atoms){
    const next = [];
    for (const bind of bindings){
      const m = matchAtom(atom, bind, R);
      if (m.length) next.push(...m);
    }
    bindings = next;
    if (!bindings.length) break;
  }
  return bindings;
}

function unify(bind, arg, val){
  if (typeof arg === 'string' && arg.startsWith('?')) {
    if (bind[arg] !== undefined) return bind[arg] === val ? [bind] : [];
    return [{ ...bind, [arg]: val }];
  }
  return arg === val ? [bind] : [];
}

function matchAtom(atom, bind, R){
  if (atom.type === 'class') {
    const cls = atom['class'] || atom.iri;
    const arg = atom.args[0];
    const out = [];
    R.indClasses.forEach((info, ind) => {
      if (info.asserted.has(cls) || info.inferred.has(cls)) {
        unify(bind, arg, ind).forEach(b => out.push(b));
      }
    });
    return out;
  }
  if (atom.type === 'objectProperty' || atom.type === 'dataProperty') {
    const prop = atom.property;
    const kind = atom.type === 'objectProperty' ? 'object' : 'data';
    const allFacts = [...R.facts.asserted, ...R.facts.inferred].filter(f => f.p === prop && f.kind === kind);
    const [a1, a2] = atom.args;
    const out = [];
    allFacts.forEach(f => {
      const val = kind === 'object' ? f.o : f.v;
      unify(bind, a1, f.s).forEach(b1 =>
        unify(b1, a2, val).forEach(b2 => out.push(b2)));
    });
    return out;
  }
  if (atom.type === 'builtin') {
    const bn = (atom.builtin || '').replace(/^swrlb:/, '');
    // Arithmetic-ASSIGNMENT builtins: swrlb:add(?r, x1, x2, …), subtract(?r,x,y),
    // multiply, divide. args[0] is the RESULT — bound to the computed value when it
    // is an unbound variable, else checked. Enables aggregation (e.g. a summed score).
    const ARITH = { add:a=>a.reduce((s,x)=>s+x,0), subtract:a=>a[0]-a[1],
                    multiply:a=>a.reduce((s,x)=>s*x,1), divide:a=>a[0]/a[1] };
    if (ARITH[bn]) {
      const resArg = atom.args[0];
      const ops = atom.args.slice(1).map(a => bind[a] !== undefined ? bind[a] : a);
      if (ops.some(o => o === undefined || o === null || o === '' || isNaN(+o))) return [];
      const res = ARITH[bn](ops.map(Number));
      if (typeof resArg === 'string' && resArg.startsWith('?')) {
        if (bind[resArg] !== undefined) return (+bind[resArg] === res) ? [bind] : [];
        return [{ ...bind, [resArg]: res }];
      }
      return (+resArg === res) ? [bind] : [];
    }
    const v1 = bind[atom.args[0]] !== undefined ? bind[atom.args[0]] : atom.args[0];
    const v2 = bind[atom.args[1]] !== undefined ? bind[atom.args[1]] : atom.args[1];
    if (v1 === undefined || v2 === undefined) return [];
    const n1 = +v1, n2 = +v2;
    if (bn === 'greaterThan'        && n1 >  n2) return [bind];
    if (bn === 'greaterThanOrEqual' && n1 >= n2) return [bind];
    if (bn === 'lessThan'           && n1 <  n2) return [bind];
    if (bn === 'lessThanOrEqual'    && n1 <= n2) return [bind];
    if (bn === 'equal'              && v1 === v2) return [bind];
    if (bn === 'notEqual'           && v1 !== v2) return [bind];
    return [];
  }
  if (atom.type === 'sameAs') {
    const v1 = bind[atom.args[0]] !== undefined ? bind[atom.args[0]] : atom.args[0];
    const v2 = bind[atom.args[1]] !== undefined ? bind[atom.args[1]] : atom.args[1];
    return v1 === v2 ? [bind] : [];
  }
  if (atom.type === 'differentFrom') {
    const v1 = bind[atom.args[0]] !== undefined ? bind[atom.args[0]] : atom.args[0];
    const v2 = bind[atom.args[1]] !== undefined ? bind[atom.args[1]] : atom.args[1];
    if (typeof v1 === 'string' && v1.startsWith('?')) return [];
    if (typeof v2 === 'string' && v2.startsWith('?')) return [];
    return v1 !== v2 ? [bind] : [];
  }
  return [];
}
