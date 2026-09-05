// ── capability: 10-subclass-closure ──────────────────────────────────
// RDFS9: A ⊑ B, B ⊑ C  ⟹  A ⊑ C. Reads R.classSupers, writes via R.inferSubC.
function inferSubClassClosure(R){
  let changed = false;
  Array.from(R.classSupers.entries()).forEach(([child, info]) => {
    const all = new Set([...info.asserted, ...info.inferred.keys()]);
    all.forEach(p => {
      const pi = R.classSupers.get(p);
      if (!pi) return;
      const gs = new Set([...pi.asserted, ...pi.inferred.keys()]);
      gs.forEach(gp => {
        if (R.inferSubC(child, gp, { kind:'subClassOf', through: p })) changed = true;
      });
    });
  });
  return changed;
}
