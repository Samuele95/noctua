// ── capability: 50-consistency ───────────────────────────────────────
// Post-fixpoint pass. Forward chaining can't detect contradictions on
// its own, so this is deliberately separate. Populates R.contradictions:
//   (1) Individual ∈ two owl:disjointWith classes (incl. inferred).
//   (2) Class inherits from two disjoint parents (transitively).
//   (3) owl:FunctionalProperty with >1 distinct value per subject.
//   (4) owl:InverseFunctionalProperty with >1 distinct subject per object.
// Not detected: restrictions, property chains, datatype facets, hasKey.
function detectContradictions(R){
  // Build (cls → Set<disjointCls>). disjointWith is symmetric — record
  // both directions so a single membership lookup catches violations.
  const disjointPairs = new Map();
  classes().forEach(c => {
    const dj = disjointWithOf(c);
    if (!dj.length) return;
    if (!disjointPairs.has(c['@id'])) disjointPairs.set(c['@id'], new Set());
    dj.forEach(other => {
      disjointPairs.get(c['@id']).add(other);
      if (!disjointPairs.has(other)) disjointPairs.set(other, new Set());
      disjointPairs.get(other).add(c['@id']);
    });
  });

  // (1) Individual ∈ two disjoint classes.
  R.indClasses.forEach((info, ind) => {
    const memberOf = new Set([...info.asserted, ...info.inferred.keys()]);
    memberOf.forEach(c1 => {
      const disjoints = disjointPairs.get(c1);
      if (!disjoints) return;
      disjoints.forEach(c2 => {
        if (memberOf.has(c2) && c1 < c2) {
          R.contradictions.push({
            kind: 'disjointIndividual',
            individual: ind,
            classes: [c1, c2],
            why: `${localName(ind)} is in both ${localName(c1)} and ${localName(c2)}, which are declared disjoint`,
          });
        }
      });
    });
  });

  // (2) Class ⊑ two disjoint parents (transitively).
  R.classSupers.forEach((info, child) => {
    const supers = new Set([...info.asserted, ...info.inferred.keys()]);
    supers.forEach(s1 => {
      const disjoints = disjointPairs.get(s1);
      if (!disjoints) return;
      disjoints.forEach(s2 => {
        if (supers.has(s2) && s1 < s2) {
          R.contradictions.push({
            kind: 'disjointSuperclass',
            cls: child,
            supers: [s1, s2],
            why: `${localName(child)} inherits from both ${localName(s1)} and ${localName(s2)}, which are declared disjoint`,
          });
        }
      });
    });
  });

  // (3) FunctionalProperty: at most one distinct value per subject.
  // (4) InverseFunctionalProperty: at most one distinct subject per object.
  [...objProps(), ...dataProps()].forEach(p => {
    const chars = characteristicsOf(p);
    const isFun = chars.includes('Functional');
    const isInv = chars.includes('InverseFunctional');
    if (!isFun && !isInv) return;
    const pIri = p['@id'];
    const facts = [...R.facts.asserted, ...R.facts.inferred]
      .filter(f => f.p === pIri && (f.kind === 'object' || f.kind === 'data'));
    if (isFun) {
      const bySubj = new Map();
      facts.forEach(f => {
        const v = f.kind === 'object' ? f.o : f.v;
        if (!bySubj.has(f.s)) bySubj.set(f.s, new Set());
        bySubj.get(f.s).add(JSON.stringify(v));
      });
      bySubj.forEach((vals, subj) => {
        if (vals.size > 1) {
          R.contradictions.push({
            kind: 'functionalViolation',
            property: pIri,
            subject: subj,
            values: [...vals].map(s => JSON.parse(s)),
            why: `${localName(pIri)} is Functional but ${localName(subj)} has ${vals.size} distinct values`,
          });
        }
      });
    }
    if (isInv && isType(p, 'owl:ObjectProperty')) {
      const byObj = new Map();
      facts.forEach(f => {
        if (!byObj.has(f.o)) byObj.set(f.o, new Set());
        byObj.get(f.o).add(f.s);
      });
      byObj.forEach((subjs, obj) => {
        if (subjs.size > 1) {
          R.contradictions.push({
            kind: 'inverseFunctionalViolation',
            property: pIri,
            object: obj,
            subjects: [...subjs],
            why: `${localName(pIri)} is InverseFunctional but ${localName(obj)} is the target of ${subjs.size} distinct subjects`,
          });
        }
      });
    }
  });
}
