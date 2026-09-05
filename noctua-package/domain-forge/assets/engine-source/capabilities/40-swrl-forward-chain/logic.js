// ── capability: 40-swrl-forward-chain ────────────────────────────────
// For every SWRL rule, find every antecedent binding under the current
// model, and assert each consequent atom. Builtins: 6 numeric comparators +
// 4 arithmetic-assignment (add/subtract/multiply/divide, result = args[0]);
// antecedents: class / objectProperty / dataProperty / builtin / sameAs /
// differentFrom. See references/ke-vocabulary.md § SWRL semantics.
function inferSWRL(R){
  let changed = false;
  swrlRules().forEach(rule => {
    const bindings = matchAntecedent(rule.antecedent || [], R);
    bindings.forEach(bind => {
      (rule.consequent || []).forEach(atom => {
        const instArgs = (atom.args || []).map(a => bind[a] !== undefined ? bind[a] : a);
        const ruleRef = rule.id || rule.label;
        if (atom.type === 'class') {
          const cls = atom['class'] || atom.iri;
          if (instArgs[0] && cls &&
              R.inferMem(instArgs[0], cls, { kind:'swrl', rule: ruleRef, bind })) changed = true;
        } else if (atom.type === 'objectProperty') {
          if (instArgs[0] != null && instArgs[1] != null && atom.property &&
              R.inferObj(instArgs[0], atom.property, instArgs[1],
                         { kind:'swrl', rule: ruleRef, bind })) changed = true;
        } else if (atom.type === 'dataProperty') {
          if (instArgs[0] != null && atom.property &&
              R.inferData(instArgs[0], atom.property, instArgs[1],
                          { kind:'swrl', rule: ruleRef, bind })) changed = true;
        }
      });
    });
  });
  return changed;
}
