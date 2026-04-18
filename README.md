# Horizon Europe Proposal Analyzer

Static analysis tool that scans Horizon Europe Part B proposals for **25 common anti-patterns** that cost points during evaluation.

Built from a real post-mortem analysis of a submitted Horizon Europe Innovation Action proposal. Each anti-pattern was identified by experienced evaluators and mapped to specific scoring impact.

## Quick Start

```bash
pip install pymupdf
python analyzer.py your_proposal.pdf
```

## What It Detects

### Document Quality
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 1 | The Unfinished Template | CRITICAL | `[Page limit]`, `[insert...]`, `[TBD]` placeholders left in |
| 2 | The Typo Graveyard | LOW | Merge artifacts, number-letter collisions, common typos |
| 3 | The Orphaned Acronym | LOW | Acronyms used but never defined |

### Technical Substance
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 4 | The Philosophy Lecture | HIGH | Opening paragraph >250 chars before project specifics |
| 5 | The Adjective Avalanche | MEDIUM | Buzzword density 3-5% per page |
| 6 | The Buzzword Bingo Card | HIGH | Buzzword density >5% per page |
| 7 | The Phantom Baseline | HIGH | KPIs (≥X%) without defined baselines or citations |
| 8 | The Reinvented Wheel | HIGH | Beyond-SotA claims without naming commercial competitors |
| 9 | The Monday Morning Test | MEDIUM | Task descriptions too vague to act on |

### Partner & Consortium
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 10 | The Ghost Partner | HIGH | Partner descriptions under 130 chars with no evidence |

### Impact & Exploitation
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 11 | The Exploitation Fog | HIGH | Generic "partners will exploit" without specifics |
| 12 | The TAM Distraction | MEDIUM | Large market figures without sub-segment drill-down |
| 13 | The All-For-All Trap | MEDIUM | Every objective validated in "All" pilots |
| 14 | The Compliance Recital | MEDIUM | Open Science lists frameworks but no data specs |

### SSH & Ethics
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 15 | The Copy-Paste SSH | CRITICAL | SSH text >55% similar across different pilots |

### Operations & Risk
| # | Pattern | Severity | What It Catches |
|---|---------|----------|-----------------|
| 16 | The Medium-High Everything | MEDIUM | All risks rated same severity |
| 17 | The Unmentionable Elephant | CRITICAL | Conflict-zone pilot with no risk mitigation |
| 18 | The Time-Travel Deliverable | HIGH | Integration WPs starting before components deliver |
| 19 | The Governance Photocopier | MEDIUM | Standard governance without project-specific mechanisms |

## Output

### Terminal Report
```
======================================================================
  HORIZON EUROPE PROPOSAL ANALYZER v1.0.0
======================================================================
  File:     proposal.pdf
  Pages:    246
  Findings: 42

  ESTIMATED SCORE (indicative, not a substitute for review)
  ------------------------------------------------------------------
  Excellence       3.5/5.0  [##############......]  OK
  Impact           3.0/5.0  [############........]  OK
  Implementation   2.5/5.0  [##########..........]  WEAK
  TOTAL            9.0/15.0
  Threshold: AT RISK
```

### JSON Export
```bash
python analyzer.py proposal.pdf --json results.json
```

### Save Report
```bash
python analyzer.py proposal.pdf --output report.txt
```

## Usage Options

```
python analyzer.py proposal.pdf              # Basic analysis
python analyzer.py proposal.pdf --verbose    # Show detector progress
python analyzer.py proposal.pdf --json out.json  # Machine-readable output
python analyzer.py proposal.pdf -o report.txt    # Save report to file
```

## Scoring

The tool estimates scores on the Horizon Europe 3-criterion scale (Excellence, Impact, Implementation), each 0-5. This is **indicative only** — actual evaluation depends on evaluator judgment, call specifics, and competitor proposals.

Severity weights:
- **CRITICAL** (1.0 points): Issues that will definitely cost points
- **HIGH** (0.5 points): Issues evaluators will likely flag
- **MEDIUM** (0.15 points): Issues that weaken the proposal
- **LOW** (0.02 points): Minor quality signals

## Limitations

- Text extraction from PDF is imperfect — complex layouts may produce false positives
- The tool checks **form**, not **content** — a technically weak proposal with perfect formatting will score well
- Anti-patterns are based on Innovation Actions; some may not apply to RIAs, CSAs, or other action types
- Not a substitute for expert review or evaluator feedback
- Does not check figures, tables rendered as images, or annexes

## Pre-Submission Checklist

The tool outputs a 19-item checklist. Key items:

- [ ] All placeholders removed
- [ ] Every KPI has a cited baseline
- [ ] Every partner: profile + prior work + named personnel
- [ ] Every task passes the "Monday morning test"
- [ ] No time-travel deliverables
- [ ] Each pilot has unique SSH analysis
- [ ] Exploitation names partner + product + market + timeline
- [ ] Spellcheck + final read by non-author

## Contributing

PRs welcome. To add a new anti-pattern:

1. Add a detector function in `analyzer.py`
2. Register it in the `detectors` list in `run_analysis()`
3. Add the pattern name to the appropriate criterion in `CRITERION_PATTERNS`
4. Update this README

## Origin

Built from a post-mortem of the EDGE-VERSE proposal (HORIZON-CL4-2026-04-HUMAN-01), an 18-partner Innovation Action for Virtual Worlds and Web 4.0. The 25 anti-patterns were identified through line-by-line evaluator analysis of the submitted Part B.

## License

MIT
