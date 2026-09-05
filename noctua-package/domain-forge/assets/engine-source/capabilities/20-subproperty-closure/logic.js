// ── capability: 20-subproperty-closure ───────────────────────────────
// RDFS5: P ⊑ Q, Q ⊑ R  ⟹  P ⊑ R. Reads R.propSupers, writes via R.inferSubP.
function inferSubPropertyClosure(R){
  let changed = false;
  Array.from(R.propSupers.entries()).forEach(([child, info]) => {
    const all = new Set([...info.asserted, ...info.inferred.keys()]);
    all.forEach(p => {
      const pi = R.propSupers.get(p);
      if (!pi) return;
      const gs = new Set([...pi.asserted, ...pi.inferred.keys()]);
      gs.forEach(gp => {
        if (R.inferSubP(child, gp, { kind:'subPropertyOf', through: p })) changed = true;
      });
    });
  });
  return changed;
}
