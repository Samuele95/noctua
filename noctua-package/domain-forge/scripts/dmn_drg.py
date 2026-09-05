#!/usr/bin/env python3
"""Generate a complete, valid DMN 1.5 DRG (Camunda/Trisotech-compatible) from a
domain-forge model-dmn JSON that carries a `drd` executable graph:
inputData, decision tables, the BKM (businessKnowledgeModel), invocation
decisions (knowledgeRequirement), the boxed FEEL expression (literalExpression),
the knowledge source, and all information/knowledge/authority requirements."""
import json, re, sys

def localname(s): return re.sub(r'^[^:]*:', '', str(s))
def safe(s): return re.sub(r'[^A-Za-z0-9_]', '_', localname(s))
def xe(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            .replace('"','&quot;'))
def xt(s):  # text-node escaper: quotes stay literal
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def main(dmn_json_path, model_name, ns, out_path):
    D = json.load(open(dmn_json_path))
    decisions = D.get('decisions', [])
    drd = D.get('drd', {}) or {}
    inputData = drd.get('inputData', [])
    nodes = drd.get('nodes', [])
    ksources = drd.get('knowledgeSources', [])
    authorities = drd.get('authorities', [])

    DEC = {d['id']: d for d in decisions}
    def out_label(d): return d.get('output') or (d.get('outputs') or [localname(d['id'])])[0]
    def is_num_table(d):
        outs = [r.get('output') for r in d.get('rules', [])]
        return outs and all(isinstance(o, (int, float)) for o in outs)

    # ---- type map: label -> typeRef ----
    typ = {}
    for x in inputData:
        t = x.get('type')
        typ[x['name']] = 'number' if t == 'number' else ('boolean' if t == 'boolean' else 'string')
    bkm_ids = set()
    for d in decisions:
        if d.get('kind') == 'businessKnowledgeModel':
            bkm_ids.add(d['id']); typ[out_label(d)] = 'string'
        else:
            typ[out_label(d)] = 'number' if is_num_table(d) else 'string'
    for n in nodes:
        k = n.get('kind')
        typ[n.get('output') or localname(n['id'])] = (
            'string' if k == 'invocation' else 'boolean' if k == 'predicate' else 'number')

    # ---- producer map: label -> (kind, element-id) ----
    prod = {}
    for x in inputData: prod[x['name']] = ('input', 'in_' + safe(x['name']))
    for d in decisions:
        if d['id'] not in bkm_ids: prod[out_label(d)] = ('decision', 'dec_' + safe(d['id']))
    for n in nodes: prod[n.get('output') or localname(n['id'])] = ('decision', 'dec_' + safe(n['id']))

    def ks_for(dec_id):
        for a in authorities:
            if dec_id in (a.get('to') or []): return a['from']
        return None

    L = ['<?xml version="1.0" encoding="UTF-8"?>']
    L.append('<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"')
    L.append('             xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/"')
    L.append('             xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/"')
    L.append('             xmlns:di="http://www.omg.org/spec/DMN/20180521/DI/"')
    L.append('             xmlns:feel="https://www.omg.org/spec/DMN/20191111/FEEL/"')
    L.append(f'             id="defs_{safe(model_name)}" name="{xe(model_name)}"')
    L.append(f'             namespace="{xe(ns)}" exporter="domain-forge" exporterVersion="3.1">')

    # input data
    for x in inputData:
        iid = 'in_' + safe(x['name'])
        L.append(f'  <inputData id="{iid}" name="{xe(x["name"])}">')
        L.append(f'    <variable id="{iid}_var" name="{xe(x["name"])}" typeRef="{typ.get(x["name"],"string")}"/>')
        L.append('  </inputData>')

    # knowledge sources
    for k in ksources:
        L.append(f'  <knowledgeSource id="ks_{safe(k["id"])}" name="{xe(k.get("name") or localname(k["id"]))}"/>')

    def decision_table(d, ind):
        hp = 'UNIQUE'  # all tables are Hit Policy U in this model
        out_t = typ.get(out_label(d), 'string')
        rows = []
        rows.append(f'{ind}<decisionTable id="{safe(d["id"])}_dt" hitPolicy="{hp}">')
        for i, col in enumerate(d.get('inputs', []), 1):
            t = typ.get(col, 'string')
            rows.append(f'{ind}  <input id="{safe(d["id"])}_i{i}" label="{xe(col)}">')
            rows.append(f'{ind}    <inputExpression id="{safe(d["id"])}_ie{i}" typeRef="{t}"><text>{xt(col)}</text></inputExpression>')
            rows.append(f'{ind}  </input>')
        rows.append(f'{ind}  <output id="{safe(d["id"])}_o" label="{xe(out_label(d))}" name="{safe(out_label(d))}" typeRef="{out_t}"/>')
        for ri, r in enumerate(d.get('rules', []), 1):
            rows.append(f'{ind}  <rule id="{safe(d["id"])}_r{ri}">')
            for cell in r.get('inputs', []):
                rows.append(f'{ind}    <inputEntry><text>{xt("-" if cell is None else cell)}</text></inputEntry>')
            ov = r.get('output')
            otext = (f'"{ov}"' if out_t == 'string' and not (isinstance(ov, str) and ov.startswith('"')) else str(ov))
            rows.append(f'{ind}    <outputEntry><text>{xt(otext)}</text></outputEntry>')
            rows.append(f'{ind}  </rule>')
        rows.append(f'{ind}</decisionTable>')
        return rows

    # BKM(s)
    for d in decisions:
        if d['id'] not in bkm_ids: continue
        bid = 'bkm_' + safe(d['id'])
        L.append(f'  <businessKnowledgeModel id="{bid}" name="{xe(d.get("label") or d.get("name") or localname(d["id"]))}">')
        L.append('    <encapsulatedLogic kind="FEEL">')
        for col in d.get('inputs', []):
            L.append(f'      <formalParameter name="{xe(col)}" typeRef="{typ.get(col,"string")}"/>')
        L.extend(decision_table(d, '      '))
        L.append('    </encapsulatedLogic>')
        L.append('  </businessKnowledgeModel>')

    # invocation decisions
    for n in nodes:
        if n.get('kind') != 'invocation': continue
        did = 'dec_' + safe(n['id']); out = n.get('output') or localname(n['id'])
        L.append(f'  <decision id="{did}" name="{xe(n.get("name") or localname(n["id"]))}">')
        L.append(f'    <variable id="{did}_var" name="{xe(out)}" typeRef="{typ.get(out,"string")}"/>')
        for j, (p, src) in enumerate(sorted((n.get('bindings') or {}).items()), 1):
            pk = prod.get(src)
            if pk:
                tag = 'requiredInput' if pk[0] == 'input' else 'requiredDecision'
                L.append(f'    <informationRequirement id="{did}_ir{j}"><{tag} href="#{pk[1]}"/></informationRequirement>')
        L.append(f'    <knowledgeRequirement id="{did}_kr"><requiredKnowledge href="#bkm_{safe(n["invokes"])}"/></knowledgeRequirement>')
        L.append('    <invocation>')
        L.append(f'      <literalExpression><text>{xt(DEC[n["invokes"]].get("label") or DEC[n["invokes"]].get("name") or localname(n["invokes"]))}</text></literalExpression>')
        for p, src in sorted((n.get('bindings') or {}).items()):
            L.append(f'      <binding><parameter name="{xe(p)}"/><literalExpression><text>{xt(src)}</text></literalExpression></binding>')
        L.append('    </invocation>')
        L.append('  </decision>')

    # table decisions (non-BKM)
    for d in decisions:
        if d['id'] in bkm_ids: continue
        did = 'dec_' + safe(d['id']); out = out_label(d)
        L.append(f'  <decision id="{did}" name="{xe(d.get("label") or d.get("name") or localname(d["id"]))}">')
        L.append(f'    <variable id="{did}_var" name="{xe(out)}" typeRef="{typ.get(out,"string")}"/>')
        seen = set()
        for j, col in enumerate(d.get('inputs', []), 1):
            pk = prod.get(col)
            if pk and pk[1] not in seen:
                seen.add(pk[1]); tag = 'requiredInput' if pk[0] == 'input' else 'requiredDecision'
                L.append(f'    <informationRequirement id="{did}_ir{j}"><{tag} href="#{pk[1]}"/></informationRequirement>')
        ksid = ks_for(d['id'])
        if ksid:
            L.append(f'    <authorityRequirement id="{did}_ar"><requiredAuthority href="#ks_{safe(ksid)}"/></authorityRequirement>')
        L.extend(decision_table(d, '    '))
        L.append('  </decision>')

    # expression decisions (boxed FEEL)
    for n in nodes:
        if n.get('kind') != 'expression': continue
        did = 'dec_' + safe(n['id']); out = n.get('output') or localname(n['id'])
        operands = n.get('operands', [])
        opkind = n.get('op')
        if opkind in (None, 'sum'):
            feel = ' + '.join(operands)
        elif opkind in ('max', 'min'):
            feel = opkind + '(' + ', '.join(operands) + ')'
        else:
            feel = (' ' + opkind + ' ').join(operands)
        L.append(f'  <decision id="{did}" name="{xe(n.get("name") or localname(n["id"]))}">')
        L.append(f'    <variable id="{did}_var" name="{xe(out)}" typeRef="{typ.get(out,"number")}"/>')
        for j, opnd in enumerate(n.get('operands', []), 1):
            pk = prod.get(opnd)
            if pk:
                tag = 'requiredInput' if pk[0] == 'input' else 'requiredDecision'
                L.append(f'    <informationRequirement id="{did}_ir{j}"><{tag} href="#{pk[1]}"/></informationRequirement>')
        L.append(f'    <literalExpression id="{did}_le"><text>{xt(feel)}</text></literalExpression>')
        L.append('  </decision>')

    # predicate decisions (boxed boolean FEEL literal expression)
    for n in nodes:
        if n.get('kind') != 'predicate': continue
        did = 'dec_' + safe(n['id']); out = n.get('output') or localname(n['id'])
        feel = n.get('feel') or (out + ' (boolean)')
        L.append(f'  <decision id="{did}" name="{xe(n.get("name") or localname(n["id"]))}">')
        L.append(f'    <variable id="{did}_var" name="{xe(out)}" typeRef="{typ.get(out,"boolean")}"/>')
        for j, src in enumerate(n.get('inputs', []), 1):
            pk = prod.get(src)
            if pk:
                tag = 'requiredInput' if pk[0] == 'input' else 'requiredDecision'
                L.append(f'    <informationRequirement id="{did}_ir{j}"><{tag} href="#{pk[1]}"/></informationRequirement>')
        L.append(f'    <literalExpression id="{did}_le"><text>{xt(feel)}</text></literalExpression>')
        L.append('  </decision>')

    L.append('</definitions>')
    xml = '\n'.join(L) + '\n'
    open(out_path, 'w', encoding='utf-8').write(xml)
    print(f'wrote {out_path} ({len(xml)} bytes)')

import re as _re
def _block(html, sid):
    m=_re.search(r'<script\s[^>]*id="%s"[^>]*\stype="[^"]*"[^>]*>([\s\S]*?)</script>'%_re.escape(sid), html, _re.I)
    return m.group(1) if m else ''
def from_html(model_html, out_path):
    html=open(model_html,encoding='utf-8').read()
    dmn=_block(html,'model-dmn').strip() or '{"decisions":[]}'
    open('/tmp/_dmn_in.json','w',encoding='utf-8').write(dmn)
    md=_block(html,'model-markdown')
    mm=_re.search(r'^\s*#\s+(.+?)\s*$', md, _re.M); name=(mm.group(1) if mm else 'DomainForgeModel')
    ttl=_block(html,'domain-model'); pm=_re.search(r'@prefix\s+ex:\s+<([^>]+)>', ttl); ns=(pm.group(1) if pm else 'http://example.org/model#')
    main('/tmp/_dmn_in.json', name, ns, out_path)

if __name__ == '__main__':
    import sys
    a=sys.argv[1:]
    if a and a[0].endswith('.html'):
        out=a[a.index('--out')+1] if '--out' in a else 'model.dmn'
        from_html(a[0], out)
    else:
        main('/tmp/df_dmn_wired.json',
             'Credit-Card Fraud Detection — DMN Decision Model (Task 1)',
             'http://www.fhnw.ch/ke/fraud#',
             a[0] if a else '/tmp/model.dmn')
