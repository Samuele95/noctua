// ── capability: 15-class-membership-inheritance ──────────────────────
// RDFS2: x ∈ A, A ⊑ B  ⟹  x ∈ B. Reads R.indClasses + R.classSupers,
// writes via R.inferMem.
function inferClassMembershipInheritance(R){
  let changed = false;
  Array.from(R.indClasses.entries()).forEach(([ind, info]) => {
    const all = new Set([...info.asserted, ...info.inferred.keys()]);
    all.forEach(c => {
      const ci = R.classSupers.get(c);
      if (!ci) return;
      const supers = new Set([...ci.asserted, ...ci.inferred.keys()]);
      supers.forEach(sup => {
        if (R.inferMem(ind, sup, { kind:'subClassOf', from: c, to: sup })) changed = true;
      });
    });
  });
  return changed;
}
