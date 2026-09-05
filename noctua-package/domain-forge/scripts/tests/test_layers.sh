#!/usr/bin/env bash
# test_layers.sh — end-to-end test of the layer platform
# (apply_layer.py / strip_layer.py / validate_model.py invariants 13–16),
# plus backward compatibility with the layers written by /model-chat and
# /inferred-questions.
#
# Usage:
#   domain-forge/scripts/tests/test_layers.sh [BASE_MODEL.html]
#     BASE_MODEL defaults to <repo>/test/base.pristine.html (never modified —
#     it is copied into a scratch directory first).
#   Environment: TEST_TMP=dir keeps the scratch files there (default: mktemp -d,
#                removed on success); CHROME=… selects the headless browser.
#
# Exit codes: 0 all checks passed, 1 at least one check failed,
#             2 could not set up (missing base model / scripts).
#
# Every check prints "OK:" or "FAIL:"; the last line is a summary.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$SCRIPTS/../.." && pwd)"
FIX="$HERE/fixtures"
BASE="${1:-$REPO/test/base.pristine.html}"
MC_APPLY="$REPO/model-chat/scripts/apply_layer.py"
IQ_APPLY="$REPO/inferred-questions/scripts/apply_layer.py"
PY="${PYTHON:-python3}"

for f in "$BASE" "$SCRIPTS/apply_layer.py" "$SCRIPTS/strip_layer.py" "$SCRIPTS/validate_model.py" \
         "$FIX/demo.data.json" "$FIX/demo.render.js"; do
  [ -f "$f" ] || { echo "ERROR: missing $f"; exit 2; }
done

if [ -n "${TEST_TMP:-}" ]; then W="$TEST_TMP"; mkdir -p "$W"; KEEP=1
else W="$(mktemp -d)"; KEEP=0; fi

PASSN=0; FAILN=0
ok()   { PASSN=$((PASSN+1)); echo "OK:   $*"; }
fail() { FAILN=$((FAILN+1)); echo "FAIL: $*"; }
check() { # check DESCRIPTION COMMAND...  → ok/fail on exit status
  local d="$1"; shift
  if "$@"; then ok "$d"; else fail "$d"; fi
}
# validate FILE → writes report to FILE.report, returns validator exit code
validate() { "$PY" "$SCRIPTS/validate_model.py" "$1" > "$1.report" 2>&1; }
has()  { grep -q -- "$2" "$1.report"; }
show() { grep -E 'invariant 1[3-6]' "$1.report" | sed 's/^/      /'; }

cp "$BASE" "$W/base.html"
echo "== scratch dir: $W"
echo "== base model:  $BASE ($(wc -c < "$W/base.html") bytes)"

# ---------------------------------------------------------------- 1. apply demo
echo "-- 1. apply_layer.py: demo layer (tab convention) on the base"
"$PY" "$SCRIPTS/apply_layer.py" "$W/base.html" --layer demo \
  --data "$FIX/demo.data.json" --render "$FIX/demo.render.js" --style "$FIX/demo.style.css" \
  --produced-by /demo --out "$W/demo.html" > "$W/apply.log"
check "apply_layer.py exits 0 and prints OK:" grep -q '^OK:' "$W/apply.log"
check "input base.html untouched" cmp -s "$W/base.html" "$BASE"
check "output is a strict byte superset (prefix + suffix of input preserved)" "$PY" - "$W/base.html" "$W/demo.html" <<'EOF'
import sys
a=open(sys.argv[1],'rb').read(); b=open(sys.argv[2],'rb').read()
i=a.rfind(b'</body>'); n=len(b)-len(a)
sys.exit(0 if n>0 and b[:i]==a[:i] and b[i+n:]==a[i:] else 1)
EOF
check "block layout: start header, data, render, style, end marker in order" "$PY" - "$W/demo.html" <<'EOF'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
pat=(r'<!-- @LAYER:start demo v1\n     produced-by: /demo\n     produced-at: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n'
     r'     input-digest: sha256:[0-9a-f]{64}\n     reverts-by: [^\n]+\n -->\n'
     r'<script id="layer-demo-data" type="application/json">\n[\s\S]*?</script>\n'
     r'<script id="layer-demo-render" type="text/javascript">\n[\s\S]*?</script>\n'
     r'<style id="layer-demo-style">\n[\s\S]*?</style>\n<!-- @LAYER:end demo -->\n</body>')
sys.exit(0 if re.search(pat,s) else 1)
EOF

# ---------------------------------------------------------------- 2. validate
echo "-- 2. validate_model.py on the layered file (expect exit 0, 13-16 PASS)"
validate "$W/demo.html"; rc=$?
show "$W/demo.html"
check "validator exit 0" test $rc -eq 0
for i in 13 14 15 16; do check "invariant $i PASS" has "$W/demo.html" "PASS  invariant $i:"; done
validate "$W/base.html"
for i in 13 14 15 16; do check "invariant $i on a layer-free model: 'no layers (skipped)'" has "$W/base.html" "PASS  invariant $i: no layers (skipped)"; done

# ---------------------------------------------------------------- 3. tamper → 14
echo "-- 3. tamper the Turtle in a copy (expect invariant 14 FAIL)"
"$PY" - "$W/demo.html" "$W/tampered.html" <<'EOF'
import sys
s=open(sys.argv[1],encoding='utf-8').read()
i=s.index('<script id="domain-model"'); j=s.index('</script>',i)
open(sys.argv[2],'w',encoding='utf-8').write(s[:j]+'\n# tampered after the layer was produced\n'+s[j:])
EOF
validate "$W/tampered.html"; rc=$?
show "$W/tampered.html"
check "validator exit 1" test $rc -eq 1
check "invariant 14 FAIL with expected/found digests and the regenerate hint" \
  grep -qE 'FAIL  invariant 14: .*expected sha256:[0-9a-f]{64}.*found sha256:[0-9a-f]{64}.*regenerate the layer or strip it' "$W/tampered.html.report"
check "invariants 13 and 15 still PASS on the tampered copy" bash -c "$(declare -f has); has '$W/tampered.html' 'PASS  invariant 13:' && has '$W/tampered.html' 'PASS  invariant 15:'"

# ---------------------------------------------------------------- 4. bad render → 15
echo "-- 4. render that writes into model-markdown (expect invariant 15 FAIL)"
"$PY" "$SCRIPTS/apply_layer.py" "$W/base.html" --layer demo \
  --data "$FIX/demo.data.json" --render "$FIX/bad.render.js" --out "$W/bad.html" > /dev/null
validate "$W/bad.html"; rc=$?
show "$W/bad.html"
check "validator exit 1" test $rc -eq 1
check "invariant 15 FAIL names model-markdown" grep -q "FAIL  invariant 15: .*model-markdown" "$W/bad.html.report"

# ---------------------------------------------------------------- 5. throwing render → 16
echo "-- 5. render that throws after load (expect invariant 16 FAIL, or WARN-skip without a browser)"
"$PY" "$SCRIPTS/apply_layer.py" "$W/base.html" --layer demo \
  --data "$FIX/demo.data.json" --render "$FIX/throw.render.js" --out "$W/throw.html" > /dev/null
validate "$W/throw.html"; rc=$?
show "$W/throw.html"
if has "$W/throw.html" "WARN  invariant 16: no headless browser"; then
  ok "invariant 16 WARN-skipped (no headless browser on this machine)"
else
  check "validator exit 1" test $rc -eq 1
  check "invariant 16 FAIL reports the uncaught error" grep -q "FAIL  invariant 16: .*uncaught error" "$W/throw.html.report"
  # a render that never mounts [data-layer="demo"]
  sed 's/pane.setAttribute(.data-layer., .demo.);//' "$FIX/demo.render.js" > "$W/nomount.render.js"
  "$PY" "$SCRIPTS/apply_layer.py" "$W/base.html" --layer demo \
    --data "$FIX/demo.data.json" --render "$W/nomount.render.js" --out "$W/nomount.html" > /dev/null
  validate "$W/nomount.html"; rc=$?
  show "$W/nomount.html" | grep 'invariant 16'
  check "invariant 16 FAIL when [data-layer=\"demo\"] is never mounted" bash -c "test $rc -eq 1 && grep -q 'FAIL  invariant 16: .*no element \[data-layer=\"demo\"\]' '$W/nomount.html.report'"
fi

# ---------------------------------------------------------------- 6. strip → identical
echo "-- 6. strip_layer.py: byte-identical round trip"
"$PY" "$SCRIPTS/strip_layer.py" "$W/demo.html" --list > "$W/list.log"
check "--list shows the demo layer with produced-by/at/digest" grep -qE -- '- demo v1 +produced-by=/demo +produced-at=[0-9T:Z-]+ +input-digest=sha256:[0-9a-f]{64} \(matches\)' "$W/list.log"
"$PY" "$SCRIPTS/strip_layer.py" "$W/demo.html" --layer demo --out "$W/demo.stripped.html" > /dev/null
check "strip(apply(base)) == base (byte-identical)" cmp -s "$W/demo.stripped.html" "$W/base.html"
"$PY" "$SCRIPTS/strip_layer.py" "$W/demo.html" --layer nope --out "$W/x.html" > "$W/strip-missing.log"; rc=$?
check "stripping an absent layer exits 1 with ERROR:" bash -c "test $rc -eq 1 && grep -q '^ERROR:' '$W/strip-missing.log'"

# ---------------------------------------------------------------- 7. update path
echo "-- 7. apply again with the same NAME (create-or-update; must be reported)"
"$PY" "$SCRIPTS/apply_layer.py" "$W/demo.html" --layer demo \
  --data "$FIX/demo.data.json" --render "$FIX/demo.render.js" --style "$FIX/demo.style.css" \
  --produced-by /demo --out "$W/demo2.html" > "$W/apply2.log"
check "replacement reported on stdout" grep -q "already present in the input — replaced" "$W/apply2.log"
check "exactly one demo layer after the update" test "$(grep -c '@LAYER:start demo' "$W/demo2.html")" = 1
"$PY" "$SCRIPTS/apply_layer.py" "$W/demo.html" --layer demo \
  --data "$FIX/demo.data.json" --render "$FIX/demo.render.js" --out "$W/demo.html" > "$W/same.log"; rc=$?
check "refuses --out == MODEL (exit 1, ERROR:)" bash -c "test $rc -eq 1 && grep -q '^ERROR:' '$W/same.log'"

# ---------------------------------------------------------------- 8. model-chat compat
echo "-- 8. backward compatibility: model-chat's own apply_layer.py"
if [ -f "$MC_APPLY" ]; then
  "$PY" "$MC_APPLY" "$W/base.html" --transcript "$FIX/transcript.json" --out "$W/chat.html" > /dev/null
  validate "$W/chat.html"; rc=$?
  show "$W/chat.html"
  check "model-chat layer: validator exit 0" test $rc -eq 0
  for i in 13 14 15 16; do check "model-chat layer: invariant $i PASS" has "$W/chat.html" "PASS  invariant $i:"; done
  "$PY" "$SCRIPTS/strip_layer.py" "$W/chat.html" --layer chat --out "$W/chat.stripped.html" > /dev/null
  check "model-chat layer: platform strip round-trips byte-identically" cmp -s "$W/chat.stripped.html" "$W/base.html"
else
  fail "model-chat apply_layer.py not found at $MC_APPLY"
fi

# ---------------------------------------------------------------- 9. inferred-questions compat
echo "-- 9. backward compatibility: inferred-questions' own apply_layer.py"
if [ -f "$IQ_APPLY" ]; then
  "$PY" "$IQ_APPLY" --input "$W/base.html" --questions "$FIX/questions.json" --output "$W/oq.html" --force > /dev/null
  validate "$W/oq.html"; rc=$?
  show "$W/oq.html"
  check "inferred-questions layer: validator exit 0" test $rc -eq 0
  for i in 13 14 15 16; do check "inferred-questions layer: invariant $i PASS" has "$W/oq.html" "PASS  invariant $i:"; done
  "$PY" "$SCRIPTS/strip_layer.py" "$W/oq.html" --layer open-questions --out "$W/oq.stripped.html" > /dev/null
  check "inferred-questions layer: platform strip round-trips byte-identically" cmp -s "$W/oq.stripped.html" "$W/base.html"
else
  fail "inferred-questions apply_layer.py not found at $IQ_APPLY"
fi

# ---------------------------------------------------------------- 10. stacked chain
echo "-- 10. stacked chain: open-questions -> chat -> demo, then --all strip"
if [ -f "$MC_APPLY" ] && [ -f "$IQ_APPLY" ]; then
  "$PY" "$MC_APPLY" "$W/oq.html" --transcript "$FIX/transcript.json" --out "$W/oq.chat.html" > /dev/null
  "$PY" "$SCRIPTS/apply_layer.py" "$W/oq.chat.html" --layer demo \
    --data "$FIX/demo.data.json" --render "$FIX/demo.render.js" --produced-by /demo --out "$W/stack.html" > /dev/null
  validate "$W/stack.html"; rc=$?
  show "$W/stack.html"
  check "three-layer file: validator exit 0" test $rc -eq 0
  check "invariant 13 lists all three layers in order" grep -q "invariant 13: 3 @LAYER block(s) well-formed (open-questions, chat, demo)" "$W/stack.html.report"
  "$PY" "$SCRIPTS/strip_layer.py" "$W/stack.html" --all --out "$W/stack.none.html" > /dev/null
  check "--all strip of the three-layer file == base (byte-identical)" cmp -s "$W/stack.none.html" "$W/base.html"
  "$PY" "$SCRIPTS/strip_layer.py" "$W/stack.html" --layer chat --out "$W/stack.nochat.html" > /dev/null
  validate "$W/stack.nochat.html"; rc=$?
  check "stripping the middle layer leaves a still-valid two-layer file" bash -c "test $rc -eq 0 && grep -q 'invariant 13: 2 @LAYER block(s) well-formed (open-questions, demo)' '$W/stack.nochat.html.report'"
fi

# ---------------------------------------------------------------- summary
echo
if [ $FAILN -eq 0 ]; then
  [ $KEEP -eq 0 ] && rm -rf "$W"
  echo "SUMMARY: all $PASSN checks passed (layer platform + model-chat + inferred-questions compatibility)"
  exit 0
else
  echo "SUMMARY: $FAILN of $((PASSN+FAILN)) checks FAILED — scratch files kept in $W"
  exit 1
fi
