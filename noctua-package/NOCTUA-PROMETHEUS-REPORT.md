# Noctua — rapporto Prometheus (3 settembre 2026)

## 1. Forma inferita e collasso

Il messaggio iniziale metteva in sovrapposizione due forme: un **team di agenti** (orchestratore + specialisti) e un **loop agentico** (una skill che vive per sessioni su un progetto). Il collasso è avvenuto con la prima domanda dell'intervista — *router nella conversazione* — che fissa la topologia: **orchestratore-worker in cui i worker sono skill invocate nella stessa conversazione**, non subagenti. Le conseguenze: i fork interattivi delle skill (`FORK:` di dataset-forge, i bet di blueprint, il dialogo di data-lens) restano visibili all'utente; l'isolamento del contesto è delegato ai subagenti che ogni skill già dispatcha (spec-analysis, domain-extractor); i **contratti d'interfaccia sono artefatti su disco** (`spec-analysis.html`, `.domain.html` a layer, `blueprint-runs/`, `shaped/recipe.json`) e non schemi di messaggio.

Forma finale: **Shape 7** (team) con l'orchestratore in **Shape 5** (persona-router) + stato **Shape 1** (ledger); ogni skill nuova è un prompt di procedura nello stile delle skill v2 (persona → posizione nella catena → input → dipendenze per riferimento → procedura con marker → failure modes → done when). Dominio: engineering/research. Substrato: frontier (Claude Code) → istruzioni brevi, nessuno scaffold cognitivo, DO NOT solo su sharp edge note e ciascuno con il suo *because*.

## 2. Intervista (6 domande flat + 1 co-authoring + collasso)

| # | domanda | risposta |
|---|---|---|
| 1 | meccanismo (router / consigliere / subagenti) | router nella conversazione |
| co-auth | rosa e nomi | confermata: noctua, data-lens, dataset-shaper; spec-analysis e blueprint adattate |
| 2 | scope di data-lens | EDA/qualità, inferenza, relazioni/segmenti, serie temporali, "e ciò che dovrebbe esserci" → aggiunti spatial e drift |
| 3 | interazione di data-lens | layer automatico + dialogo guidato |
| 4 | "geometriche-spaziali" | spazio-feature + coordinate geografiche + trasformazioni da data-lens |
| 5 | output di dataset-shaper | dataset + ricetta + script + layer |
| 6 | blueprint su dataset / spec-analysis su DB | architettura pipeline dati/ML; schema DB + codice dati (DB vivo solo read-only) |
| done | quattro criteri di fatto | confermati |
| consegna | progetto + prompt ora, codice dopo | confermata |

Default assegnati nel collasso (accettati): skill di catena con output `<input-stem>.analysis.html` / `.shaped.html` tramite il writer di piattaforma; data-lens usa geometry se c'è, forgia altrimenti (`--standalone` per un modello minimo); la ricetta è la verità con provenance chiusa; ledger separato dalla memoria dei forge; utente presente → fork chiesti, `--unattended` → astensione; prompt in inglese.

## 3. Operatori per ruolo (cosa amplifica, cosa sopprime)

**noctua** — l'operatore più forte è la *regola di delega* ("You never do a stage's work"), messa prima della procedura perché ogni istruzione successiva vive nel sottospazio che essa proietta; il corollario *never delegate understanding* (argomenti composti da ledger e memoria) è l'operatore che evita la delega stantia. Il ledger è la memoria di Shape 1, con la separazione stanza-stato / stanza-decisioni. Le due reference (chain-map, ledger-contract) sono progressive disclosure: la SKILL.md non restate nessuna procedura di stadio (verificato: C1 non-blocking → risolto spostando i comportamenti unattended in una colonna del chain-map).

**data-lens** — persona = "l'analista che lavora come dice la disciplina": l'operatore forte è la triade *assunzione → effect size → correzione* e la regola di ammissione (decision test); il baseline geometrico ("non riscoprire le derivazioni") sopprime la modalità di fallimento più probabile (ripetere dataset-forge con altri nomi); il dialogo eredita da model-chat il principio *grounded* con la cella eseguita come motore invece dei motori simbolici. `method-catalog.md` è l'operatore-esempio: una riga per domanda con il fallback robusto.

**dataset-shaper** — persona = "decisions become data"; operatore forte = *nessun passo senza decisione tracciata* con insieme chiuso di sorgenti e rifiuto dell'esecutore; secondo operatore = l'ordine di fase come barriera meccanica contro il leakage (fit su train, target encoding out-of-fold, `custom` per parte). Il catalogo è l'interfaccia (nomi, param, fase, fitted, sorgente) — su substrato frontier vale più degli esempi.

**patch** — spec-analysis riceve un secondo dominio (dati/DB) con lockdown a strati sul DB vivo (strutturale: solo connessione read-only fornita dall'utente; prosa: "cannot and must not", con il perché); blueprint riceve un terzo input e `--mode pipeline` con i tag `[geometry:…] [analysis:…] [shape:…]` allineati alle chiavi JSON dei layer, e un DO NOT contro la ri-analisi.

## 4. Audit

**Ordinamento.** In ogni SKILL.md: persona e regola cardine → posizione nella catena → input/flag → dipendenze per riferimento → procedura → failure modes → done. Scambiando "failure modes" con "procedura" il comportamento cambierebbe (le prohibizioni verrebbero lette come commento a posteriori): coppia non commutante, ordine corretto. In noctua la regola di delega precede i trigger: se seguisse, `--goal` verrebbe letto come licenza a "portare a termine".

**Interferenza.** (a) data-lens: "insight solo se cambia una decisione" × "ogni modulo deve avere una reading" → rischio di reading vuote per riempire: risolto con "a module with nothing to say says so in one sentence". (b) dataset-shaper: "FORK per fase" × "unattended applica default" → risolto con la marcatura `default applied (unattended)` nel layer. (c) noctua: "never do a stage's work" × fallback "carry out its procedure inline when no Skill tool" → tensione voluta, delimitata al solo caso senza Skill tool (il verifier la segnala come seam da tenere stretto).

**Preservazione dell'informazione.** I tre canali di provenance di dataset-forge non vengono ridotti a valle: data-lens li copia in `context`, dataset-shaper li cita per chiave, blueprint li tagga. Ciò che deve restare ambiguo è marcato: partizione `abstained`/`none`, `symbolic: untested`, `custom` *unverified*, ruoli *guessed* in standalone.

**Misurazione.** Gli script deterministici (seed registrato nel layer) fanno sì che a temperature > 0 vari la prosa, non i numeri; il verifier V1/V2 chiede sempre il risultato del runner dietro ogni cifra.

**Static verifier (dogfood).** noctua: SHIP (0 blocking, 2 non-blocking → entrambi risolti). data-lens: SHIP (0 blocking, 2 non-blocking + 1 inconclusive → tutti risolti: seed richiesto, `handoff.shaper_candidates` richiesto, precondizione di `importance`). dataset-shaper: primo passaggio REVISE (0 blocking, 3 non-blocking: `custom` fuori fase, `lag` assente dall'enumerazione, restatement dei nomi upstream) → secondo passaggio **SHIP, 0/0/0**. Audit incrociato dei contratti: 22 rilievi (2 bloccanti: `partitions.chosen` letto come oggetto; `--unattended` inesistente negli stadi) → tutti risolti o parziali-cosmetici; secondo passaggio: 3 nuovi rilievi (1 bloccante: `--report-only` non produce un modello, quindi la corsia software non avanzava mai in unattended) → risolti (`forge-prose`/`refine` unattended = *not run, announced as pending*, con uscita esplicita dal loop `--goal`).

## 5. Valutazione onesta

| asse | voto | perché |
|---|---|---|
| Token economy | 8 | ogni SKILL.md sta tra 11 e 16 KB; le procedure non restatano i contratti; il punto debole è `method-catalog.md` (lungo, ma è consultato per riga, non caricato intero) |
| Task fit | 7 | copre i tre obiettivi e i quattro criteri di fatto **a livello di prompt e contratto**; il criterio 2 (catena end-to-end su orders.csv) e il 3 (verifier SHIP) sono verificabili solo dopo la build degli script — il rischio principale è che il contratto del layer `analysis` (§1) risulti troppo ricco da riempire in un run reale; il primo run lo dirà |
| Operator coherence | 8 | le tre skill condividono la spina delle v2 e si passano gli artefatti con nomi di chiave verificati incrociatamente; la tensione residua è il fallback inline di noctua |

**Scaffold → trigger (M5).** Nessuno scaffold cognitivo (substrato frontier, nessun fallimento al primo tentativo dichiarato). Verifier statici: sempre spediti. Verifier dinamici: non spediti — le stesse skill portano i propri test dinamici (validate, smoke, `--check`), che sono più forti di un giudice LLM. Cross-run: non spedito (non richiesto). Clarification-seeking: presente perché l'utente è presente e lo ha chiesto (fork per fase / step-2 forks / dialogo), con la floor di astensione `--unattended` in ogni stadio.

## 6. Specifica di verifica (tre strati)

- **Statico** (spedito, eseguito): i tre `verifiers/static-verifier.md`; i verifier v2 di dataset-forge e domain-forge da rieseguire sui file patchati nella build.
- **Dinamico a run singolo** (nella build, B3/B5/B6): `validate_model.py` 19/19 su file a 2 e 3 layer; `smoke_*.py --strict`; `shape.py --check`; round-trip `strip(apply(x)) == x`; ricette avvelenate rifiutate (encode prima di split, step senza source, winsorize contro stance).
- **Cross-run** (dopo la build, sul caso CIC-IDS2017): due run di `/data-lens --questions q.txt` con seed uguale → `analysis.json` identico e transcript con gli stessi `result`; due run di `/noctua` sullo stesso stato → stessa proposta.

## 7. Istruzioni d'uso

1. Installare le cartelle del pacchetto **al posto** delle attuali (v2 → v3): `domain-forge`, `dataset-forge`, `model-chat`, `inferred-questions` (invariate salvo le reference registrate), `spec-analysis`, `blueprint` (patchate), `noctua`, `data-lens`, `dataset-shaper` (nuove). `effective-java` resta com'è (dipendenza esterna di blueprint). Il pannello di revisione propone i tre SKILL.md nuovi; gli altri SKILL.md patchati viaggiano nello zip.
2. Fino alla build, `/noctua` chiuderà le corsie a `lens` e `shape` con `ERROR:` (script mancanti): è il comportamento previsto dal chain-map.
3. Primo run consigliato dopo la build: `/noctua` nella cartella CIC-IDS2017 (criterio 1), poi `/noctua --goal shape` con l'utente presente.
4. Parametri di ragionamento: Claude Code con effort medio-alto per data-lens (le letture e il dialogo sono il lavoro di giudizio), medio per noctua (routing) e dataset-shaper (compilazione); nessun budget di thinking manuale.

## 8. Cosa guardare al primo run

- Se data-lens produce findings che sono statistiche descrittive travestite, la regola di ammissione non sta proiettando abbastanza: aggiungere un secondo esempio negativo nel contratto §2.
- Se dataset-shaper chiede troppi fork, il preset `train-ready` sta aggiungendo troppi `shaper:default` con alternative: ridurre le alternative dei default a quelle con conseguenza concreta.
- Se noctua "aiuta" (edita un artefatto, risponde a un fork), la regola di delega va rafforzata con un secondo *because* nel punto in cui cede — probabilmente il fallback inline.
