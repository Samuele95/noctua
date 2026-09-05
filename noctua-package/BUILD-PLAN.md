# Noctua v3 — piano di build (eseguito)

**Stato: eseguito il 3 settembre 2026.** I blocchi B1–B8 sono stati costruiti e verificati; questo documento resta come registro di cosa doveva esistere e con quali test, e i blocchi qui sotto sono da leggere come specifica di ciò che ora c'è. L'unica eccezione è **B7 sul folder reale CIC-IDS2017**, non eseguibile senza una sessione collegata a "samuele-fisso": l'equivalente è stato verificato su un folder sintetico della stessa forma. Esito complessivo: 13 tra script e asset, `tests/acceptance.py` **78 passed / 0 failed**. Il consuntivo — cosa ha dimostrato la build e quali difetti ha trovato — è in `CHANGES-v3.md`, sezione *La build (B1–B8) — eseguita*.

La sessione di progetto aveva consegnato i **prompt e i contratti**: `noctua/`, `data-lens/`, `dataset-shaper/` (SKILL.md, references, verifier) e le patch a `spec-analysis`, `blueprint`, `dataset-forge`, `domain-forge`. Le due skill nuove della corsia dati citavano script e asset che allora non esistevano. Questo documento era il brief della sessione di build: cosa costruire, in che ordine, con quali test, e il criterio di accettazione — i quattro criteri di fatto concordati.

## Ordine di build (un blocco per checkpoint)

### B1 — data-lens/scripts/analysis.py (il motore del pass automatico)
Input: dataset + `--model <html>` (legge `layer-geometry-data` per typing/basis/derivazioni/partizione), `--split`, `--modules`, `--seed`, `--out`. Output: `analysis.json` con un oggetto per modulo della tabella §3 di `analysis-contract.md`, ciascuno `{ran, skipped_because?, evidence}`; le chiavi di `importance` e `drift` sono fissate in §1 (le uniche lette da altre skill), le altre libere ma stabili. Figure SVG in `<run-dir>/fig-*.svg` (matplotlib, palette `dataviz` se installata). Dipendenze: pandas, numpy, scipy, scikit-learn; statsmodels opzionale (STL, ADF/KPSS) con degrado a `ran: false`; geopandas/pyproj/esda opzionali per `spatial`.
Regole non negoziabili nel codice: ogni test emette `assumptions_checked` e, se `violated`, esegue l'alternativa robusta del `method-catalog.md`; ogni p-value viaggia con effect size + CI + correzione (BH per famiglia); `importance` esclude leakage set e derivazioni della label e riporta il `leakage_probe`.
Test: `orders.csv` + `orders.geometry-layer.json` (fixture di dataset-forge) → tutti i moduli tranne `time_series`/`spatial`/`drift` con `ran: true`; un fixture sintetico con colonna data e lat/lon per i tre moduli condizionali; determinismo (`--seed` → JSON identico).

### B2 — data-lens/scripts/cell.py (il dialogo)
`cell.py <run-dir> --code <file.py>`: precarica `df`, `ctx` (contesto geometry), `prev` (risultati dei turni precedenti), `fig()` (SVG); esegue in sandbox (nessuna rete, nessuna scrittura fuori da `<run-dir>`), restituisce JSON `{result, figure?, stdout, error?}`. Timeout configurabile. Test: cella che calcola un Mann–Whitney; cella che fallisce → `error` e nessuna eccezione a monte.

### B3 — data-lens/scripts/bootstrap_base.py, apply_analysis_layer.py, smoke_analysis.py + assets
`bootstrap_base.py`: modello base minimo da `assets/template.html` di domain-forge (Record + una data property per colonna, `ex:sourceKind "dataset"`), validato 1–12/17–19. `apply_analysis_layer.py`: valida il JSON contro §1 (chiavi obbligatorie, `handoff.shaper_candidates`, `T<n>` unici, `seed`, ogni finding con test → `effect`+`correction`) e chiama **solo** `domain-forge/scripts/apply_layer.py` (stesso pattern di `apply_geometry_layer.py`: nessuna copia del formato o del digest). `assets/analysis-render.js` (≤ 60 KB, vanilla, quattro superfici del contratto §7, `window.__analysis`) e `analysis-layer.css`. `smoke_analysis.py --strict` (Chromium headless: tab montato, board e transcript, nessun errore JS). Test: round-trip `strip(apply(x)) == x`; `validate_model.py` 19/19 sul file a due layer (geometry + analysis); smoke 100 %.

### B4 — dataset-shaper/scripts/shape.py (compilatore-esecutore)
`--check-only` (schema, fasi, sorgenti contro i layer, regole strutturali, stances), esecuzione deterministica (seed) di ogni `op` del `step-catalog.md` per fase, con `fit_on` sulla sola parte train dopo `split`, target encoding out-of-fold, `custom` per parte; scrive dati (csv/parquet), `manifest.json`, `lineage.json`, `reproduce_<slug>.py` (standalone, asserisce i digest), `recipe.json` copiato nell'output dir; `--dry-run`; `--check` (riesegue `reproduce_*.py` e confronta i digest). Le op spaziali sono un modulo separato importato solo se richiesto (geopandas/pyproj/h3 opzionali; `ERROR:` chiaro se mancano).
Test: ricetta di riferimento per `orders.csv` (retype zip, drop id, drop_derived total/subtotal, select_partition late + drop_leakage delivered_days, split stratificato, impute, one-hot zip, scale robust) → output attesi committati come fixture; determinismo byte-identico; ricetta con `encode` prima di `split` → rifiutata con il messaggio giusto; step senza `source` → rifiutato; `winsorize` su colonna con stance `genuine-outliers` → rifiutato.

### B5 — dataset-shaper/scripts/verify_shape.py, apply_shape_layer.py, smoke_shape.py + assets
Verifiche §3 del contratto (strutturale, semantica con ricalcolo empirico delle derivazioni mantenute + `run_query.py` opzionale, PSI sulle colonne non toccate, igiene dello split, spaziale). `apply_shape_layer.py` come B3. `assets/shape-render.js` (tabella ricetta, before/after, grafo di lineage SVG, pannello verifiche, forks; `window.__shape`) e css. `smoke_shape.py`. Test: file a tre layer (geometry + analysis + shape) 19/19; round-trip; smoke.

### B6 — Catena end-to-end su `orders.csv` (criterio di fatto 2)
`/dataset-forge fixtures/orders.csv` → `/data-lens … --questions q.txt` → `/dataset-shaper … --goal train-ready --unattended` → `/blueprint … --mode pipeline --report-only`. Accettazione: ogni HTML 19/19 (13–16 inclusi), `shape.py --check` PASS, blueprint con trace integrity PASS e nessun tag `[geometry:…]`/`[analysis:…]` che non risolva a una chiave del layer.

### B7 — Noctua sul caso reale (criterio di fatto 1)
`/noctua` nella cartella CIC-IDS2017: ledger creato, sorgenti classificate (dataset + modello `_3` con `geometry` + spec), proposta = `/data-lens analysis/cicids2017.domain_3.html --dataset dataset/cicids2017.csv`, nessuna domanda già coperta da memoria. Poi `/noctua --goal shape` con l'utente presente.

### B8 — Regressione della corsia software (criterio di fatto 4)
`/spec-analysis` su un progetto piccolo → `/domain-forge` → `/blueprint`: comportamento invariato rispetto alla v2 (diff dei summary). In più: `/spec-analysis --kind database` su uno schema SQL di prova (DDL + migrazioni) e `--kind data-project` su un notebook + ETL.

## Verifiche di consegna della build
- I tre static verifier (già eseguiti sui prompt: SHIP) rieseguiti sui SKILL.md finali; il verifier di dataset-forge e di domain-forge rieseguiti sui file patchati.
- `domain-forge/scripts/tests/test_layers.sh` esteso con i layer `analysis` e `shape` (round-trip, invarianti 13–16, indipendenza 16 in headless).
- Un `noctua/scripts/env_check.py` (opzionale ma utile): stampa la riga **Environment** del ledger (librerie, browser, LaTeX, skill installate, script presenti).

## Cosa NON costruire
- Nessuna copia privata di `apply_layer.py`, del digest o del driver dei motori (regola della piattaforma v2).
- Nessun rendering JS generato per run: gli explorer sono asset.
- Nessuna trasformazione in data-lens; nessuna analisi in dataset-shaper.
- Nessun contratto nn-* inventato: l'hand-off di dataset-shaper è manifest + script di riproduzione.

## Requisiti di ambiente
Python ≥ 3.10 con `rdflib`, `numpy`, `pandas`, `scipy`, `scikit-learn`; `pyarrow` per parquet; `statsmodels` per le serie temporali; `geopandas`, `pyproj`, `shapely` (e `h3`, `esda` opzionali) per lo spaziale; Chromium/Chrome headless su PATH o `$CHROME` per gli smoke test e la verifica simbolica; `matplotlib` per le figure.
