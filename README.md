# C.R.U.C.I.B.L.E.

**Consortia Review Under Controlled Interrogation — Before Live Evaluation**

Open-source static analysis engine for Horizon Europe proposals. Detects **48+ anti-patterns** across 4 layers, estimates evaluator scores, and checks alignment with SMILE methodology — all in 60 seconds from a single PDF.

Built from a real post-mortem of a submitted Horizon Europe Innovation Action. Every detector maps to something evaluators actually flag.

> **TURTLESHELL** — the commercial SaaS product powered by CRUCIBLE — is available at [crucible.winniio.io](https://crucible.winniio.io). Upload your PDF, get a scored report with findings, SMILE radar, and export options. Free tier available.

```
  C.R.U.C.I.B.L.E. v5.1.0
  File:       proposal.pdf (246 pages)
  Part B:     pp. 148-246 (98 pages)
  Findings:   42

  Excellence       3.5/5.0  [##############......]  OK
  Impact           3.0/5.0  [############........]  OK
  Implementation   2.5/5.0  [##########..........]  WEAK
  TOTAL            9.0/15.0
  Threshold: AT RISK
```

## Install

```bash
pip install pymupdf
git clone https://github.com/Life-Atlas/horizon-proposal-analyzer.git
cd horizon-proposal-analyzer
```

## Quick Start

```bash
# Basic analysis
python crucible.py proposal.pdf

# With call text (enables Layer 2: Call Alignment)
python crucible.py proposal.pdf --call call_text.txt

# Full analysis with all modes
python crucible.py proposal.pdf --call call_text.txt --verbose --json report.json --budget --eic-pathfinder

# Debug: print extracted ProposalModel
python crucible.py proposal.pdf --model
```

## Architecture

CRUCIBLE uses a **two-pass architecture** that first extracts a structured model, then runs analysis against it.

```
PDF ──► Pass 0: PRE-FLIGHT (10 gatekeeper checks)
    ──► Pass 1: EXTRACTION (build ProposalModel)
    ──► Pass 2: ANALYSIS (4 layers, 48+ detectors)
    ──► Pass 3: STRATEGIC SCORING (EIC Pathfinder mode)
    ──► Pass 4: PESTELED (8-dimension regional environment)
    ──► Pass 5: EU INTEROPERABILITY FRAMEWORK (7 layers)
    ──► Pass 6: CONCEPT / CONTEXT / CRISIS (triple stress test)
    ──► COMPOSITE SCORE (6-component weighted grade)
```

### Pass 0: Pre-Flight Checklist

10 gatekeeper questions before analysis runs. Any BLOCKER = stop and fix before proceeding.

| # | Check | Weight |
|---|-------|--------|
| 1 | Call text loaded? | BLOCKER |
| 2 | Page count within limit? | BLOCKER |
| 3 | Passes all 3 gatekeepers? | BLOCKER |
| 4 | TRL targets aligned? | CRITICAL |
| 5 | Coordinator has institutional credibility? | CRITICAL |
| 6 | ≥3 partners from ≥3 eligible countries? | BLOCKER |
| 7 | Budget within call limits? | CRITICAL |
| 8 | Named key personnel with track records? | HIGH |
| 9 | Commitment letter from coordinator? | HIGH |
| 10 | All outputs open-access? | MEDIUM |

### Pass 1: Extraction → ProposalModel

Extracts structured data from the entire PDF (not just Part B):

- **Metadata**: acronym, title, call ID, action type, duration
- **Partners**: name, PIC, country, SME status, person-months
- **Work packages**: number, title, lead, start/end months, person-months
- **Tasks**: per-WP task breakdown
- **Deliverables**: number, title, type, due month, responsible partner
- **Milestones**: number, title, due month, verification means
- **Risks**: description, likelihood, severity, mitigation
- **KPIs**: targets with baseline detection
- **Citations**: reference extraction and counting
- **Budget**: total, EU contribution, per-partner breakdown
- **Researchers**: named personnel with roles

### Pass 2: Four-Layer Analysis

#### Layer 1: Structural Integrity

Cross-document consistency checks:

- Partner count mismatches (Part A vs Part B)
- Budget inconsistencies across sections
- Work package numbering gaps
- Deliverable/milestone orphans (referenced but undefined)
- Person-month allocation vs partner commitments
- Task-to-WP mapping completeness
- Duration claims vs Gantt chart

#### Layer 2: Call Alignment

Requires `--call` flag with call/topic text file:

- Terminology match (call keywords vs proposal text)
- Expected outcome coverage
- TRL range verification
- Action type requirements
- Cross-cutting priorities (gender, open science, SSH)
- Specific call conditions and eligibility

#### Layer 3: Field & SMILE

**Field awareness** — checks the proposal demonstrates knowledge of its domain:

- Named competitors and commercial alternatives
- Citation density and recency
- Standards body references
- Patent landscape awareness
- Regulatory framework acknowledgment

**SMILE methodology** — Sustainable Methodology for Impact Lifecycle Enablement:

| Phase | Abbr | What It Checks |
|-------|------|---------------|
| 1. Reality Emulation | RE | Digital twin / simulation / modeling language |
| 2. Concurrent Engineering | CE | Multi-stakeholder co-creation, parallel development |
| 3. Collective Intelligence | CI | AI/ML integration, crowd wisdom, feedback loops |
| 4. Contextual Intelligence | CX | Domain awareness, regulatory context, localization |
| 5. Continuous Intelligence | CN | Real-time monitoring, adaptive learning, evolution |
| 6. Perpetual Wisdom | PW | Knowledge management, institutional memory, long-term learning |

Three perspectives: **People**, **Systems**, **Planet**.

SMILE principle enforcement: _Impact first, data last_ — penalizes proposals that lead with data/technology before establishing the problem.

#### Layer 4: Anti-Patterns (48+ Detectors)

| Detector | Severity | What It Catches |
|----------|----------|-----------------|
| Unfilled Placeholders | CRITICAL | `[Page limit]`, `[insert...]`, `[TBD]` left in |
| Buzzword Density | HIGH | Adjective avalanche (>5% buzzwords per page) |
| Philosophy Opening | HIGH | Opening paragraph >250 chars before specifics |
| Phantom Baselines | HIGH | KPIs without defined baselines or citations |
| Ghost Partners | HIGH | Partner descriptions <130 chars with no evidence |
| Copy-Paste SSH | CRITICAL | SSH text >55% similar across pilots |
| Medium-High Everything | MEDIUM | All risks rated identical severity |
| Time-Travel Deliverables | HIGH | Integration WPs starting before components deliver |
| Exploitation Fog | HIGH | Generic "partners will exploit" without specifics |
| TAM Distraction | MEDIUM | Large market figures without segment drill-down |
| Output/Outcome Confusion | MEDIUM | Outputs presented as impacts |
| D&E Conflation | MEDIUM | Dissemination and exploitation treated as one activity |
| Governance Photocopier | MEDIUM | Standard governance without project-specific mechanisms |
| Reinvented Wheel (SotA) | HIGH | Beyond-SotA claims without naming competitors |
| Partner-Driven WPs | MEDIUM | WPs designed around partners, not objectives |
| Missing AI Disclosure | MEDIUM | AI tools used without proper disclosure |
| Lump Sum Issues | MEDIUM | Lump-sum budget without proper justification |
| Meeting Milestones | MEDIUM | Milestones that are just meetings |
| Budget Narrative Gaps | MEDIUM | Missing justification for major cost items |
| Consortium Diversity | LOW | Geographic/sector concentration |
| Orphaned Acronyms | LOW | Acronyms used but never defined |
| Evaluator Readability | HIGH | Flesch-Kincaid score too high, dense paragraphs |
| Theory of Change | CRITICAL | No causal chain from outputs → outcomes → impact |
| Gender Dimension | MEDIUM | Missing gender balance statement or gender research content |

### Pass 3: Strategic Scoring (EIC Pathfinder Mode)

Enabled with `--eic-pathfinder`. Adds:

**EIC Pathfinder Open sub-criteria scoring:**
- 1a: Long-term vision of radically new technology
- 1b: Concrete science-towards-technology breakthrough
- 1c: Objectives and methodology soundness
- 1d: Interdisciplinarity from distant disciplines
- 2a: Long-term transformative impact
- 2b: Innovation and exploitation potential
- 2c: Communication and dissemination
- 3a: Work plan quality
- 3b: Resource allocation
- 3c: Consortium quality

**Strategic dimensions:** Time to market, innovation depth, partnership strength, ecosystem play, regulatory readiness.

**Future Tech Radar:** 3-year / 5-year / 10-year technology horizon scoring.

### Pass 4: PESTELED — Regional Environment Analysis

8-dimension external environment scan (Political, Economic, Social, Technological, Environmental, Legal, Ethical, Demographic). Checks whether the proposal demonstrates awareness of its operating context beyond the technical domain.

### Pass 5: EU Interoperability Framework

7-layer assessment based on the European Interoperability Framework: Technical, Syntactic, Semantic, Organizational, Legal, Contextual, Social. Scores whether the proposal's outputs will actually integrate with existing EU infrastructure and standards.

### Pass 6: Concept / Context / Crisis — Triple Stress Test

Three-lens resilience test:
- **Concept** — Is the thesis falsifiable? Does it solve a real problem? Is there evidence it can work? What's the moat?
- **Context** — Is the timing right? Does it align with EU priorities? Is there market pull?
- **Crisis** — What if the approach fails? What if a partner drops out? What if the geopolitical context changes?

### Composite CRUCIBLE Score

6-component weighted grade (S/A/B/C/D):

| Component | Weight |
|-----------|--------|
| EIC Criteria | 35% |
| Strategic Dimensions | 15% |
| Future Readiness | 10% |
| PESTELED | 15% |
| EU Interoperability | 15% |
| Stress Test | 10% |

## CLI Reference

```
python crucible.py <pdf> [options]

Arguments:
  pdf                    Path to proposal PDF

Options:
  --call, -c PATH        Call/topic text file (enables Layer 2)
  --verbose, -v          Show extraction and analysis progress
  --json, -j PATH        Save full JSON output to file
  --output, -o PATH      Save text report to file
  --budget, -b           Enable budget analysis mode
  --model, -m            Print extracted ProposalModel and exit
  --eic-pathfinder, -e   EIC Pathfinder Open scoring mode
```

## Output Formats

### Terminal Report

Color-coded severity, grouped by layer, with score estimates and actionable suggestions for every finding.

### JSON Export

Full structured output including:
- Extracted ProposalModel (partners, WPs, deliverables, milestones, risks, KPIs, budget)
- All findings with pattern, severity, page, text, suggestion, category, layer
- Score estimates per criterion
- SMILE coverage scores
- Pre-flight checklist results
- EIC Pathfinder sub-criteria scores (if enabled)
- Strategic dimension scores (if enabled)

### Text Report

Same as terminal output, saved to file. Useful for sharing with consortium partners.

## Scoring Model

Base score: **3.0** per criterion (Excellence, Impact, Implementation).

```
Score = 3.0 + bonuses (up to +2.0) - penalties (up to -2.0)
Range: 1.0 — 5.0 per criterion
Total: 3.0 — 15.0
```

Severity penalty weights:
- **CRITICAL** (1.0): Will definitely cost points — fix immediately
- **HIGH** (0.5): Evaluators will likely flag
- **MEDIUM** (0.15): Weakens the proposal
- **LOW** (0.02): Minor quality signal

Threshold: **10/15** overall, **3/5** per criterion. Below threshold on any criterion = rejection regardless of total.

For Innovation Actions: Impact is weighted 1.5x.

## Supported Call Types

- **RIA** (Research and Innovation Action) — default
- **IA** (Innovation Action) — Impact weighted 1.5x
- **EIC Pathfinder Open** — full sub-criteria scoring with `--eic-pathfinder`
- **CSA** (Coordination and Support Action) — basic support
- Generic Horizon Europe proposals

Template v10.0 (Dec 2025) changes are reflected: 40-page limit for RIA/IA, Section 2.3 optional, equipment threshold >15%.

## Limitations

- Text extraction from PDF is imperfect — complex layouts, tables as images, or scanned documents may produce false positives
- Checks **form**, not **content** — a technically weak proposal with perfect formatting will score well
- SMILE assessment uses structural evidence (stakeholder tables, named ontologies, validation methodology), not just keywords
- Not a substitute for expert human review
- Call alignment (Layer 2) requires the actual call text as input

## Contributing

PRs welcome. To add a new anti-pattern detector:

1. Add a `check_*` function in `crucible.py`
2. Register it in the `detectors` list inside `run_analysis()`
3. Use the `result.add()` API with pattern name, severity, page, text, suggestion, category, and layer
4. Test against a real proposal PDF

To add a new call type:

1. Add criteria weights to the scoring model
2. Add call-specific pre-flight checks if needed
3. Add a CLI flag if the call type needs special handling

## Origin

Built from a post-mortem of the EDGE-VERSE proposal (HORIZON-CL4-2026-04-HUMAN-01), an 18-partner Innovation Action for Virtual Worlds and Web 4.0. The initial 25 anti-patterns grew to 45+ through systematic study of evaluator guidelines, the Horizon Europe Model Grant Agreement, and template v10.0.

## API Server

CRUCIBLE includes a FastAPI wrapper for SaaS integration:

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8100
```

**Endpoints:**
- `GET /health` — engine status and version
- `POST /analyze` — multipart/form-data with `pdf` (required), `call_text` (optional), `tier` (free/single/pro/enterprise)

Tier gating is handled in `server.py` — the CLI always returns full results.

## SMILE Methodology

CRUCIBLE is built on the [SMILE methodology](https://winniio.io) (Sustainable Methodology for Impact Lifecycle Enablement) — a framework that enforces **Impact first, data last**. Every proposal should flow from desired outcome backward to required data, not from available data forward to hoped-for impact.

SMILE is the foundational methodology that shapes the [Life Programmable Interface (LPI)](https://lifeatlas.online) — the sovereign consultation layer at the heart of Life Atlas. The six SMILE phases (Reality Emulation → Concurrent Engineering → Collective Intelligence → Contextual Intelligence → Continuous Intelligence → Perpetual Wisdom) provide the lifecycle structure; the LPI operationalizes it across all domains.

## License

MIT — [WINNIIO AB](https://winniio.io) / [Life Atlas](https://lifeatlas.online)
