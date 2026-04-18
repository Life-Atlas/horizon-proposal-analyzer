#!/usr/bin/env python3
"""
C.R.U.C.I.B.L.E.
Consortia Review Under Controlled Interrogation — Before Live Evaluation

A SMILE-methodology-driven proposal analyzer for Horizon Europe.

Three-layer evaluation architecture:
  Layer 1: CALL ALIGNMENT  — Is the proposal a slave to what the call requires?
  Layer 2: FIELD AWARENESS  — Does it know the seminal work AND where the field is heading?
  Layer 3: ANTI-PATTERNS    — The 40+ mechanical checks that catch sloppy writing

Built on the S.M.I.L.E. methodology (Sustainable Methodology for Impact Lifecycle Enablement):
  Impact first, data last. Outcome → Action → Insight → Information → Data.

Usage:
  python crucible.py proposal.pdf --call call_text.txt
  python crucible.py proposal.pdf --call call_text.txt --verbose
  python crucible.py proposal.pdf --call call_text.txt --json results.json

License: MIT — WINNIIO AB / Life Atlas
"""

import sys
import re
import json
import argparse
from pathlib import Path
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz
except ImportError:
    print("ERROR: pymupdf required. Install with: pip install pymupdf")
    sys.exit(1)

__version__ = "2.0.0"

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Finding:
    pattern: str
    severity: str        # CRITICAL, HIGH, MEDIUM, LOW
    page: int
    text: str
    suggestion: str
    category: str = ""   # Call Alignment, Field Awareness, SMILE, Anti-Pattern
    layer: int = 3       # 1=Call, 2=Field, 3=Anti-Pattern


@dataclass
class AnalysisResult:
    findings: list = field(default_factory=list)

    def add(self, pattern, severity, page, text, suggestion, category="", layer=3):
        self.findings.append(Finding(pattern, severity, page, text, suggestion, category, layer))


# ============================================================
# PDF & CALL TEXT EXTRACTION
# ============================================================

def extract_text(pdf_path: str) -> tuple[dict, int]:
    doc = fitz.open(pdf_path)
    pages = {}
    for i in range(len(doc)):
        pages[i + 1] = doc[i].get_text()
    return pages, len(doc)


def find_part_b_start(pages: dict) -> int:
    for num in sorted(pages.keys()):
        text = pages[num]
        if "Part B" in text and num > 5:
            lower = text.lower()
            if any(w in lower for w in ['excellence', 'objectives', 'section 1']):
                return num
    for num in sorted(pages.keys()):
        if "Part B" in pages[num] and "Administrative forms" not in pages[num]:
            return num
    return 1


def is_admin_page(text: str) -> bool:
    indicators = [
        'Administrative forms', 'Participant Registry',
        'PIC\n', 'Legal name\n', 'SME Data', 'Gender Equality Plan',
        'Departments carrying out', 'Main contact person',
        'This proposal version was submitted by',
    ]
    return sum(1 for i in indicators if i in text) >= 2


def get_part_b_text(pages: dict, start: int) -> str:
    return " ".join(t for n, t in sorted(pages.items()) if n >= start and not is_admin_page(t))


def load_call_text(call_path: str) -> str:
    return Path(call_path).read_text(encoding='utf-8')


def extract_call_from_pdf(call_path: str) -> str:
    if call_path.lower().endswith('.pdf'):
        doc = fitz.open(call_path)
        return " ".join(doc[i].get_text() for i in range(len(doc)))
    return load_call_text(call_path)


# ============================================================
# SMILE METHODOLOGY FRAMEWORK
# ============================================================

SMILE_PHASES = {
    "reality_emulation": {
        "name": "Reality Emulation",
        "key_question": "What is the starting point and boundary of your sociotechnological ecosystem?",
        "proposal_markers": [
            "stakeholder mapping", "stakeholder analysis", "ecosystem boundary",
            "spatial context", "temporal context", "reality canvas",
            "operating context", "sociotechnological", "actor-network",
            "pesteled", "pestle", "5 whys", "root cause",
        ],
        "what_to_check": "Does the proposal define the reality it operates in? Stakeholders, boundaries, spatial-temporal context?",
    },
    "concurrent_engineering": {
        "name": "Concurrent Engineering",
        "key_question": "What does the Minimal Viable Twin look like?",
        "proposal_markers": [
            "minimal viable", "mvp", "mvt", "as-is", "to-be",
            "hypothesis", "validate", "simulation", "scenario",
            "virtual first", "prototype", "proof of concept",
        ],
        "what_to_check": "Does the proposal define what 'good enough' looks like before scaling? Is there a validation step?",
    },
    "collective_intelligence": {
        "name": "Collective Intelligence",
        "key_question": "How does the system connect to physical reality and meet initial KPIs?",
        "proposal_markers": [
            "sensor", "ontology", "kpi", "interoperability",
            "data model", "schema", "metadata", "standards",
            "integration", "connected", "iot",
        ],
        "what_to_check": "Does the proposal show how digital connects to physical? Are ontologies/standards defined?",
    },
    "contextual_intelligence": {
        "name": "Contextual Intelligence",
        "key_question": "Can the system make real-time decisions with context?",
        "proposal_markers": [
            "real-time", "command and control", "predictive",
            "analytics", "root cause", "decision support",
            "dashboard", "monitoring", "alert",
        ],
        "what_to_check": "Does the proposal move beyond data collection to contextual decision-making?",
    },
    "continuous_intelligence": {
        "name": "Continuous Intelligence",
        "key_question": "Does the system learn and prescribe, not just predict?",
        "proposal_markers": [
            "prescriptive", "ai-driven", "prognostic",
            "machine learning", "model training", "feedback loop",
            "continuous", "autonomous", "self-improving",
        ],
        "what_to_check": "Does the proposal show how the system improves over time? Is there an AI maturity path?",
    },
    "perpetual_wisdom": {
        "name": "Perpetual Wisdom",
        "key_question": "How does impact scale beyond the project?",
        "proposal_markers": [
            "open source", "ecosystem", "replication",
            "transferability", "sustainability", "circular",
            "planetary", "global", "share impact",
        ],
        "what_to_check": "Does the proposal show how results outlive the project? Open source? Standards? Ecosystem?",
    },
}

SMILE_PERSPECTIVES = {
    "people": {
        "name": "From People",
        "markers": ["stakeholder", "user", "citizen", "community", "participat", "co-design", "co-creation"],
    },
    "systems": {
        "name": "From Systems",
        "markers": ["ontology", "standard", "interoperab", "metadata", "schema", "protocol", "api"],
    },
    "planet": {
        "name": "From Planet",
        "markers": ["gis", "bim", "cim", "satellite", "spatial", "geospatial", "environmental", "sustainability"],
    },
}

IMPACT_SEQUENCE = ["outcome", "action", "insight", "information", "data"]


# ============================================================
# LAYER 1: CALL ALIGNMENT CHECKS
# ============================================================

def check_call_alignment(pages, result, part_b_start, call_text):
    """The proposal must be a slave to what the call requires."""
    if not call_text:
        result.add(
            "No Call Text Provided", "HIGH", 0,
            "Cannot verify call alignment without the call text",
            "Provide --call <file> with the work programme topic text",
            "Call Alignment", 1
        )
        return

    proposal_text = get_part_b_text(pages, part_b_start).lower()
    call_lower = call_text.lower()

    # Extract expected outcomes from call
    expected_outcomes = re.findall(
        r'expected outcome[s]?\s*[:\-]\s*(.*?)(?=\n\n|\nscope|\nexpected|$)',
        call_lower, re.DOTALL
    )

    # Extract scope requirements
    scope_sections = re.findall(
        r'scope[:\-]\s*(.*?)(?=\n\n|\nexpected|\ndestination|$)',
        call_lower, re.DOTALL
    )

    # Extract specific requirements/deliverables mentioned in call
    call_requirements = []
    requirement_patterns = [
        r'(?:should|must|shall|are expected to)\s+(.*?)(?:\.|;)',
        r'proposals\s+(?:should|must|shall)\s+(.*?)(?:\.|;)',
        r'(?:develop|create|deliver|demonstrate|validate|establish)\s+(.*?)(?:\.|;)',
    ]
    for pattern in requirement_patterns:
        matches = re.findall(pattern, call_lower)
        call_requirements.extend(matches)

    # Check: does the proposal address each expected outcome?
    if expected_outcomes:
        outcome_text = ' '.join(expected_outcomes)
        key_phrases = extract_key_phrases(outcome_text)
        missing = []
        for phrase in key_phrases:
            if phrase not in proposal_text:
                missing.append(phrase)
        if missing:
            sample = ', '.join(missing[:5])
            result.add(
                "Call Outcome Gap", "CRITICAL", 0,
                f"Call expected outcomes mention concepts not found in proposal: {sample}",
                "Map every expected outcome to a specific WP/task/deliverable",
                "Call Alignment", 1
            )

    # Check: does the proposal use call-specific terminology?
    call_keywords = extract_domain_keywords(call_lower)
    proposal_keywords = extract_domain_keywords(proposal_text)
    call_only = call_keywords - proposal_keywords
    if len(call_only) > 5:
        sample = ', '.join(sorted(call_only)[:8])
        result.add(
            "Call Terminology Gap", "HIGH", 0,
            f"Call uses {len(call_only)} domain terms not in proposal: {sample}",
            "Mirror the call's language — evaluators match your text to call requirements",
            "Call Alignment", 1
        )

    # Check: is the proposal paraphrasing the work programme instead of translating?
    call_sentences = [s.strip() for s in call_lower.split('.') if len(s.strip()) > 40]
    verbatim_count = 0
    for sent in call_sentences[:30]:
        words = sent.split()
        if len(words) >= 8:
            phrase = ' '.join(words[:8])
            if phrase in proposal_text:
                verbatim_count += 1
    if verbatim_count > 3:
        result.add(
            "Work Programme Parrot", "MEDIUM", 0,
            f"{verbatim_count} call sentences appear verbatim in proposal",
            "Translate the WP into YOUR project's context — don't parrot it",
            "Call Alignment", 1
        )

    # Check: TRL alignment
    call_trl = re.findall(r'TRL\s*(\d)', call_lower)
    proposal_trl = re.findall(r'TRL\s*(\d)', proposal_text)
    if call_trl and proposal_trl:
        call_trl_set = set(call_trl)
        proposal_trl_set = set(proposal_trl)
        if not call_trl_set & proposal_trl_set:
            result.add(
                "TRL Mismatch", "CRITICAL", 0,
                f"Call mentions TRL {','.join(sorted(call_trl_set))}, proposal mentions TRL {','.join(sorted(proposal_trl_set))}",
                "Align your TRL targets with what the call specifies",
                "Call Alignment", 1
            )

    # Check: action type alignment (RIA vs IA)
    if 'innovation action' in call_lower or 'horizon-ia' in call_lower:
        if 'trl' in proposal_text:
            low_trl = re.findall(r'TRL\s*[12]', proposal_text, re.IGNORECASE)
            if low_trl:
                result.add(
                    "Action Type Mismatch", "HIGH", 0,
                    f"Innovation Action call but proposal targets TRL 1-2 (basic research)",
                    "IAs target TRL 5-7+. Adjust scope or submit as RIA",
                    "Call Alignment", 1
                )

    # Check: EU policy alignment
    eu_policies = {
        'green deal': 'European Green Deal',
        'digital decade': 'Digital Decade',
        'fit for 55': 'Fit for 55',
        'ai act': 'AI Act',
        'data act': 'Data Act',
        'chips act': 'Chips Act',
        'industrial strategy': 'Industrial Strategy',
        'twin transition': 'Twin Transition',
    }
    call_policies = [name for key, name in eu_policies.items() if key in call_lower]
    if call_policies:
        missing_policies = [p for p in call_policies if p.lower() not in proposal_text]
        if missing_policies:
            result.add(
                "Policy Alignment Gap", "MEDIUM", 0,
                f"Call references {', '.join(call_policies)} but proposal misses: {', '.join(missing_policies)}",
                "Reference the same EU policies the call mentions — evaluators check for this",
                "Call Alignment", 1
            )


def extract_key_phrases(text):
    stop = {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or', 'is', 'are',
            'be', 'with', 'that', 'this', 'by', 'on', 'at', 'as', 'from', 'it',
            'will', 'should', 'must', 'shall', 'their', 'they', 'have', 'has',
            'been', 'were', 'was', 'which', 'such', 'these', 'those', 'can',
            'also', 'may', 'not', 'but', 'into', 'its', 'all', 'more', 'new',
            'between', 'through', 'including', 'both', 'each', 'other', 'about'}
    words = re.findall(r'\b[a-z][\w-]+\b', text)
    bigrams = []
    for i in range(len(words) - 1):
        if words[i] not in stop and words[i+1] not in stop and len(words[i]) > 3 and len(words[i+1]) > 3:
            bigrams.append(f"{words[i]} {words[i+1]}")
    return list(set(bigrams))[:20]


def extract_domain_keywords(text):
    stop = {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or', 'is', 'are',
            'be', 'with', 'that', 'this', 'by', 'on', 'at', 'as', 'from', 'will',
            'should', 'must', 'shall', 'their', 'they', 'have', 'has', 'been',
            'were', 'was', 'which', 'such', 'these', 'those', 'can', 'also',
            'may', 'not', 'but', 'into', 'its', 'all', 'more', 'new', 'project',
            'proposal', 'work', 'programme', 'horizon', 'europe', 'call', 'topic',
            'action', 'grant', 'consortium', 'partner', 'result', 'activity',
            'expected', 'outcome', 'impact', 'scope', 'objective', 'deliverable'}
    words = set(re.findall(r'\b[a-z][\w-]{4,}\b', text))
    return words - stop


# ============================================================
# LAYER 2: FIELD AWARENESS CHECKS
# ============================================================

def check_field_awareness(pages, result, part_b_start):
    """Does the proposal know the seminal work AND where the field is heading?"""
    proposal_text = get_part_b_text(pages, part_b_start)
    lower = proposal_text.lower()

    # Check: citation recency
    years = re.findall(r'\((?:\w+[\s,]+)?(\d{4})\)', proposal_text)
    years += re.findall(r'\[(\d{4})\]', proposal_text)
    years = [int(y) for y in years if 1990 <= int(y) <= 2027]
    if years:
        recent = [y for y in years if y >= 2024]
        old = [y for y in years if y < 2020]
        pct_recent = len(recent) / len(years) * 100 if years else 0
        if pct_recent < 20:
            result.add(
                "Stale References", "HIGH", 0,
                f"Only {pct_recent:.0f}% of {len(years)} citations are from 2024+",
                "At least 30% of references should be from the last 2 years",
                "Field Awareness", 2
            )
        if not old:
            result.add(
                "No Foundational Citations", "MEDIUM", 0,
                "No references older than 2020 — missing seminal/foundational work",
                "Include foundational papers that established the field, not just recent work",
                "Field Awareness", 2
            )
    else:
        result.add(
            "No Detectable Citations", "HIGH", 0,
            "Could not detect any year-based citations in the proposal",
            "Include properly formatted citations with years",
            "Field Awareness", 2
        )

    # Check: self-citation ratio
    all_citations = re.findall(r'\(([^)]{5,60}?,\s*\d{4})\)', proposal_text)
    if len(all_citations) > 5:
        # Look for repeated author names (likely self-citations)
        author_counts = Counter()
        for cite in all_citations:
            author = cite.split(',')[0].strip().split()[-1]
            author_counts[author] += 1
        top_author, top_count = author_counts.most_common(1)[0]
        if top_count > len(all_citations) * 0.4:
            result.add(
                "Self-Citation Overload", "MEDIUM", 0,
                f"'{top_author}' appears in {top_count}/{len(all_citations)} citations ({top_count/len(all_citations)*100:.0f}%)",
                "Balance self-citations with external validation. >40% self-citation signals arrogance",
                "Field Awareness", 2
            )

    # Check: does the proposal reference competing/adjacent projects?
    project_indicators = ['h2020', 'fp7', 'horizon 2020', 'horizon europe',
                          'project', 'funded by', 'grant agreement']
    prior_projects = sum(1 for p in project_indicators if p in lower)
    if prior_projects < 2:
        result.add(
            "Prior Art Blindness", "HIGH", 0,
            "No references to prior EU-funded projects in the same domain",
            "Show awareness of what's been funded before and what gap remains",
            "Field Awareness", 2
        )

    # Check: does the proposal mention standards bodies / emerging standards?
    standards_indicators = ['iso ', 'iec ', 'ieee ', 'w3c', 'oasis', 'etsi',
                            'buildingsmart', 'ogc', 'ietf', 'ecma']
    standards_found = [s for s in standards_indicators if s in lower]
    if not standards_found:
        result.add(
            "Standards Blindness", "MEDIUM", 0,
            "No reference to relevant standards bodies (ISO, IEEE, W3C, ETSI, etc.)",
            "Reference applicable standards — evaluators check for standardization awareness",
            "Field Awareness", 2
        )

    # Check: forward-looking language
    future_markers = ['roadmap', 'future work', 'emerging', 'next generation',
                      'post-project', 'beyond the project', '2030', '2035',
                      'long-term', 'vision', 'evolution']
    future_found = [m for m in future_markers if m in lower]
    if len(future_found) < 2:
        result.add(
            "No Forward Vision", "MEDIUM", 0,
            "Proposal lacks forward-looking positioning (roadmap, post-project evolution)",
            "Show where the field is heading and how this project positions for it",
            "Field Awareness", 2
        )


# ============================================================
# SMILE METHODOLOGY ASSESSMENT
# ============================================================

def check_smile_alignment(pages, result, part_b_start):
    """Evaluate proposal against SMILE phases and principles."""
    proposal_text = get_part_b_text(pages, part_b_start).lower()

    # Check each SMILE phase
    phase_scores = {}
    for phase_id, phase in SMILE_PHASES.items():
        markers_found = [m for m in phase["proposal_markers"] if m in proposal_text]
        coverage = len(markers_found) / len(phase["proposal_markers"]) * 100
        phase_scores[phase["name"]] = coverage

        if coverage < 15:
            result.add(
                f"SMILE Gap: {phase['name']}", "MEDIUM", 0,
                f"Phase '{phase['name']}' coverage: {coverage:.0f}% — {phase['what_to_check']}",
                f"Key question: {phase['key_question']}",
                "SMILE Methodology", 2
            )

    # Check: Impact-first principle (Outcome → Action → Insight → Information → Data)
    # Does the proposal start with outcomes or start with data/technology?
    for num in range(part_b_start, min(part_b_start + 3, max(pages.keys()) + 1)):
        text = pages.get(num, "").lower()
        if 'excellence' in text or 'section 1' in text:
            first_500 = text[:500]
            data_first_words = ['data', 'sensor', 'algorithm', 'platform', 'technology',
                                'system', 'framework', 'architecture', 'infrastructure']
            impact_first_words = ['impact', 'outcome', 'benefit', 'challenge', 'problem',
                                  'need', 'gap', 'opportunity', 'society', 'citizen']
            data_count = sum(1 for w in data_first_words if w in first_500)
            impact_count = sum(1 for w in impact_first_words if w in first_500)
            if data_count > impact_count * 2:
                result.add(
                    "SMILE Violation: Data First", "HIGH", num,
                    f"Opening is technology-first ({data_count} tech terms vs {impact_count} impact terms)",
                    "SMILE principle: Impact first, data last. Lead with the problem, not the solution",
                    "SMILE Methodology", 2
                )
            break

    # Check: Three perspectives coverage
    for persp_id, persp in SMILE_PERSPECTIVES.items():
        markers_found = [m for m in persp["markers"] if m in proposal_text]
        if len(markers_found) < 2:
            result.add(
                f"SMILE Perspective Gap: {persp['name']}", "LOW", 0,
                f"Weak coverage of '{persp['name']}' perspective ({len(markers_found)}/{len(persp['markers'])} markers)",
                "SMILE requires People + Systems + Planet perspectives",
                "SMILE Methodology", 2
            )

    return phase_scores


# ============================================================
# LAYER 3: ANTI-PATTERN DETECTORS (expanded from v1)
# ============================================================

def check_unfilled_placeholders(pages, result, start):
    placeholders = [
        (r'\[Page limit\]', '[Page limit]'),
        (r'\[insert\s+\w+', '[insert ...]'),
        (r'\[TBD\]', '[TBD]'),
        (r'\[TODO\]', '[TODO]'),
        (r'\[XX+\]', '[XX]'),
        (r'\[fill\s+in\]', '[fill in]'),
        (r'\[placeholder\]', '[placeholder]'),
    ]
    seen = set()
    for num, text in pages.items():
        if num < start:
            continue
        for pattern, label in placeholders:
            if re.search(pattern, text, re.IGNORECASE):
                key = (label, num)
                if key not in seen:
                    seen.add(key)
                    result.add("The Unfinished Template", "CRITICAL", num,
                               f"Placeholder: {label}",
                               "Search for '[', 'insert', 'TBD' before submission",
                               "Anti-Pattern", 3)


def check_buzzwords(pages, result, start):
    buzzwords = {
        'human-centric', 'human-centred', 'socio-technical', 'trustworthy',
        'interoperable', 'scalable', 'holistic', 'synergy', 'paradigm',
        'ecosystem', 'cutting-edge', 'novel', 'innovative', 'groundbreaking',
        'transformative', 'disruptive', 'seamless', 'robust', 'comprehensive',
        'unprecedented', 'game-changing', 'next-generation', 'leveraging',
    }
    flagged = 0
    for num, text in pages.items():
        if num < start or is_admin_page(text) or flagged >= 5:
            continue
        words = text.lower().split()
        if len(words) < 50:
            continue
        count = sum(1 for w in words if any(b in w for b in buzzwords))
        density = count / len(words) * 100
        if density > 4 and flagged < 5:
            flagged += 1
            sev = "HIGH" if density > 5 else "MEDIUM"
            result.add("Buzzword Overload", sev, num,
                       f"Density {density:.1f}% ({count}/{len(words)})",
                       "For every buzzword, add one concrete technical specification",
                       "Anti-Pattern", 3)


def check_opening(pages, result, start):
    for num in range(start, min(start + 5, max(pages.keys()) + 1)):
        text = pages.get(num, "")
        if 'excellence' not in text.lower():
            continue
        lines = [l.strip() for l in text.split('\n')
                 if len(l.strip()) > 30 and not any(s in l.lower() for s in ['call:', 'horizon', 'eu grants', 'part b'])]
        if lines and len(lines[0]) > 250:
            result.add("The Philosophy Lecture", "HIGH", num,
                       f"Opening: {len(lines[0])} chars before specifics",
                       "Project name + problem + solution in ≤100 words",
                       "Anti-Pattern", 3)
        break


def check_baselines(pages, result, start):
    found = 0
    for num, text in pages.items():
        if num < start or is_admin_page(text) or found >= 8:
            continue
        matches = re.findall(r'>=?\s*\d+\s*%|≥\s*\d+\s*%', text)
        if matches:
            lower = text.lower()
            has_ref = any(b in lower for b in ['baseline defined', 'compared to', 'current state-of', 'measured against'])
            has_cite = bool(re.search(r'\(\w+[\s,]+\d{4}\)|\[\d+\]', text))
            if not has_ref and not has_cite:
                found += 1
                result.add("The Phantom Baseline", "HIGH", num,
                           f"KPI '{matches[0]}' without baseline",
                           "Every KPI: metric + SotA value (cited) + target + method",
                           "Anti-Pattern", 3)


def check_ghost_partners(pages, result, start):
    for num, text in pages.items():
        if num < start:
            continue
        if 'capacity of participant' not in text.lower() and 'consortium as a whole' not in text.lower():
            continue
        for line in text.split('\n'):
            stripped = line.strip()
            if 20 < len(stripped) < 130 and re.match(r'^[A-Z]{2,10}\s+(contributes?|supports?|leads?|is supporting|provides?)\b', stripped):
                result.add("The Ghost Partner", "HIGH", num,
                           f"Thin description ({len(stripped)} chars): '{stripped[:100]}'",
                           "Each partner: org profile + prior projects + named personnel",
                           "Anti-Pattern", 3)


def check_copy_paste(pages, result, start):
    blocks = []
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        for m in re.findall(r'(?:SSH|Human.centric|[Ss]ociet\w+)\s*(?:dimension|relevance)[:\s]+(.*?)(?:\n\n|\n[A-Z])', text, re.DOTALL):
            clean = ' '.join(m.split())[:300]
            if len(clean) > 60:
                blocks.append((num, clean))
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if blocks[i][0] == blocks[j][0]:
                continue
            wa, wb = set(blocks[i][1].lower().split()), set(blocks[j][1].lower().split())
            if wa and wb and len(wa & wb) / max(len(wa), len(wb)) > 0.55:
                result.add("Copy-Paste SSH", "CRITICAL", blocks[j][0],
                           f"SSH text ~similar to page {blocks[i][0]}",
                           "Each pilot needs unique SSH analysis",
                           "Anti-Pattern", 3)


def check_risks(pages, result, start):
    all_lower = get_part_b_text(pages, start).lower()
    has_conflict = any(w in all_lower for w in ['post-conflict', 'war zone', 'kharkiv', 'reconstruction'])

    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'risk' not in lower or ('likelihood' not in lower and 'severity' not in lower):
            continue
        medium = len(re.findall(r'\bmedium\b', lower))
        if medium >= 4 and len(re.findall(r'\blow\b', lower)) == 0:
            result.add("The Medium-High Everything", "MEDIUM", num,
                       f"All risks same severity (Medium: {medium})",
                       "Vary ratings. Add management + market + regulatory risks",
                       "Anti-Pattern", 3)
        # Check for technical-only risks
        tech_risk_words = ['technical', 'performance', 'integration', 'data', 'system']
        mgmt_risk_words = ['personnel', 'partner', 'management', 'coordination', 'key person']
        market_risk_words = ['market', 'regulatory', 'competition', 'adoption', 'commercial']
        has_tech = any(w in lower for w in tech_risk_words)
        has_mgmt = any(w in lower for w in mgmt_risk_words)
        has_market = any(w in lower for w in market_risk_words)
        if has_tech and not has_mgmt and not has_market:
            result.add("Technical-Only Risk Table", "MEDIUM", num,
                       "Risk register only covers technical risks",
                       "Add management risks (personnel, coordination) and market risks (regulatory, adoption)",
                       "Anti-Pattern", 3)
        if has_conflict and 'conflict' not in lower and 'security' not in lower:
            result.add("The Unmentionable Elephant", "CRITICAL", num,
                       "Conflict-zone pilot but no conflict/security risk",
                       "Add dedicated risk section for conflict-zone operations",
                       "Anti-Pattern", 3)
        break


def check_timeline(pages, result, start):
    wp_timing = {}
    for num, text in pages.items():
        if num < start:
            continue
        for wp, s, e in re.findall(r'Work package (?:number\s+)?(\d+).*?M(\d+)\s*[-–]\s*M?(\d+)', text, re.DOTALL):
            wp_timing[int(wp)] = (int(s), int(e))
    for pilot_wp in [w for w in wp_timing if w >= 7]:
        for comp_wp in [w for w in wp_timing if 3 <= w <= 6]:
            if wp_timing[pilot_wp][0] < wp_timing[comp_wp][1] - 6:
                result.add("Time-Travel Deliverable", "HIGH", 0,
                           f"WP{pilot_wp} starts M{wp_timing[pilot_wp][0]} but WP{comp_wp} ends M{wp_timing[comp_wp][1]}",
                           "Integration WPs must follow component delivery",
                           "Anti-Pattern", 3)


def check_exploitation(pages, result, start):
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'exploitation' not in lower or ('strategy' not in lower and 'plan' not in lower):
            continue
        specific = any(m in lower for m in ['eur ', '€', 'revenue', 'pricing', 'saas', 'license fee'])
        generic = any(m in lower for m in ['partners will', 'results will be', 'will integrate'])
        if generic and not specific:
            result.add("The Exploitation Fog", "HIGH", num,
                       "Generic exploitation — no named partner plans with revenue models",
                       "Each partner: WHAT product + WHICH market + WHEN + revenue model",
                       "Anti-Pattern", 3)
            break


def check_market(pages, result, start):
    for num, text in pages.items():
        if num < start:
            continue
        if re.search(r'(?:USD|EUR|€|\$)\s*[\d,.]+\s*(?:bn|billion)', text, re.IGNORECASE):
            if not any(w in text.lower() for w in ['addressable', 'serviceable', 'sub-segment', 'target segment']):
                result.add("The TAM Distraction", "MEDIUM", num,
                           "Large market figure without sub-segment drill-down",
                           "Total market → addressable → your capture path. Cite sources",
                           "Anti-Pattern", 3)
                break


def check_meeting_milestones(pages, result, start):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'milestone' not in lower:
            continue
        bad_milestones = re.findall(
            r'(?:milestone|MS\d+)[:\s]*(.*?(?:meeting|workshop|review|kick.?off|conference).*?)(?:\n|$)',
            lower
        )
        if bad_milestones:
            result.add("Meeting Milestones", "HIGH", num,
                       f"Milestone is a meeting/event, not a verifiable achievement: '{bad_milestones[0][:80]}'",
                       "Milestones must be concrete verifiable outputs, not calendar events",
                       "Anti-Pattern", 3)
            break


def check_output_outcome_impact(pages, result, start):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'expected outcome' not in lower and 'expected impact' not in lower:
            continue
        has_output = 'output' in lower
        has_outcome = 'outcome' in lower
        has_impact = 'impact' in lower
        if has_outcome and has_impact:
            outcome_section = text[lower.find('outcome'):lower.find('outcome') + 500].lower()
            impact_section = text[max(0, lower.rfind('impact') - 50):lower.rfind('impact') + 500].lower()
            publish_words = ['publish', 'paper', 'conference', 'journal', 'disseminat']
            if any(p in outcome_section for p in publish_words):
                result.add(
                    "Output-Outcome Confusion", "MEDIUM", num,
                    "Publications listed as outcomes — publications are outputs, not outcomes",
                    "Outputs = what you produce. Outcomes = what changes because of it. Impacts = long-term societal change",
                    "Anti-Pattern", 3
                )
                break


def check_page_count(pages, result, start):
    part_b_pages = sum(1 for n, t in pages.items() if n >= start and not is_admin_page(t))
    if part_b_pages > 45:
        result.add("Page Limit Risk", "HIGH", 0,
                   f"Part B appears to be ~{part_b_pages} pages (limit is typically 40 for RIA/IA as of Dec 2025)",
                   "Pages beyond the limit are REMOVED by the system — evaluators never see them",
                   "Anti-Pattern", 3)


def check_budget_ratios(pages, result, start):
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'management' in lower and ('wp1' in lower or 'work package 1' in lower or 'work package number' in lower):
            # Check if WP1 allocation seems disproportionate
            pm_match = re.findall(r'(?:WP\s*1|management).*?(\d{2,3})\s*(?:PM|person)', text, re.IGNORECASE)
            total_match = re.findall(r'total.*?(\d{3,4})\s*(?:PM|person)', text, re.IGNORECASE)
            if pm_match and total_match:
                try:
                    wp1 = int(pm_match[0])
                    total = int(total_match[0])
                    pct = wp1 / total * 100
                    if pct > 12:
                        result.add("Heavy Management WP", "MEDIUM", num,
                                   f"WP1 (management) is {pct:.0f}% of total PMs — typical is 5-10%",
                                   "Keep management WP to 5-10% of total effort",
                                   "Anti-Pattern", 3)
                except (ValueError, ZeroDivisionError):
                    pass
            break


def check_dissemination_exploitation_conflation(pages, result, start):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'dissemination' not in lower and 'exploitation' not in lower:
            continue
        if 'dissemination and exploitation' in lower or 'exploitation and dissemination' in lower:
            combined = lower.count('dissemination and exploitation') + lower.count('exploitation and dissemination')
            separate_d = lower.count('dissemination') - combined
            separate_e = lower.count('exploitation') - combined
            if combined > 3 and separate_d < 2 and separate_e < 2:
                result.add(
                    "D&E Conflation", "MEDIUM", num,
                    "Dissemination and exploitation always mentioned together, never separately",
                    "These are different: dissemination = awareness, exploitation = economic/policy value creation",
                    "Anti-Pattern", 3
                )
                break


def check_zero_pm_wp_lead(pages, result, start):
    """Partner leads WP/task but has 0 PMs allocated."""
    proposal_text = get_part_b_text(pages, start)
    task_leads = re.findall(r'T\d+\.\d+.*?\(([A-Z]{2,10})\s*/\s*M\d+', proposal_text)
    lead_counts = Counter(task_leads)

    pm_table_text = ""
    for num, text in pages.items():
        if num < start:
            continue
        if 'total' in text.lower() and re.search(r'\b\d{2,3}\b.*\b\d{2,3}\b', text):
            pm_table_text += text

    for partner, count in lead_counts.items():
        if len(partner) >= 2 and count >= 2:
            if f"{partner}\n" in pm_table_text or f"{partner} " in pm_table_text:
                context = pm_table_text[pm_table_text.find(partner):pm_table_text.find(partner) + 100]
                if '\n0\n' in context or '\n0 \n' in context:
                    result.add(
                        "Zero-PM Task Lead", "CRITICAL", 0,
                        f"{partner} leads {count} tasks but may have 0 PMs in that WP",
                        "Cannot lead a task with no effort allocated — fix PM table",
                        "Anti-Pattern", 3
                    )


def check_sota(pages, result, start):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if ('state of the art' in lower or 'state-of-the-art' in lower) and ('advancement' in lower or 'beyond' in lower):
            competitors = ['nvidia', 'omniverse', 'unity', 'unreal', 'microsoft',
                           'bentley', 'siemens', 'dassault', 'autodesk', 'cesium', 'google', 'meta']
            if not any(c in lower for c in competitors):
                result.add("The Reinvented Wheel", "HIGH", num,
                           "Beyond-SotA without naming commercial competitors",
                           "Name and cite competitors, explain the specific gap",
                           "Anti-Pattern", 3)
            break


def check_governance(pages, result, start):
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if sum(1 for g in ['general assembly', 'steering committee', 'advisory board'] if g in lower) < 2:
            continue
        if not any(p in lower for p in ['conflict resolution', 'contingency', 'escalation', 'ip dispute']):
            result.add("Governance Template", "MEDIUM", num,
                       "Standard governance without project-specific mechanisms",
                       "Add: conflict resolution, IP governance, escalation paths",
                       "Anti-Pattern", 3)
        break


def check_acronyms(pages, result, start):
    text = get_part_b_text(pages, start)
    used = set(re.findall(r'\b([A-Z]{3,6})\b', text))
    safe = {'EU', 'AI', 'XR', 'VR', 'AR', 'MR', 'BIM', 'GIS', 'API', 'SSH', 'KPI',
            'TRL', 'DMP', 'FAIR', 'GDPR', 'SME', 'IOT', 'CEO', 'CTO', 'RIA',
            'HTTP', 'JSON', 'CSV', 'PDF', 'URL', 'GPU', 'CPU', 'HPC', 'WP', 'PM',
            'THE', 'AND', 'FOR', 'NOT', 'BUT', 'NOR', 'YET'}
    undefined = [a for a in (used - safe) if not re.search(rf'\([^)]*{a}\)', text)]
    if len(undefined) > 8:
        result.add("Orphaned Acronyms", "LOW", 0,
                   f"{len(undefined)} potentially undefined: {', '.join(sorted(undefined)[:10])}",
                   "Master acronym list + define at first use",
                   "Anti-Pattern", 3)


# ============================================================
# SCORING
# ============================================================

SEVERITY_WEIGHTS = {"CRITICAL": 1.0, "HIGH": 0.5, "MEDIUM": 0.15, "LOW": 0.02}

CRITERION_MAP = {
    "Excellence": {
        "layer_1": ["Call Outcome Gap", "Call Terminology Gap", "TRL Mismatch", "Action Type Mismatch"],
        "layer_2": ["Stale References", "No Foundational Citations", "Prior Art Blindness",
                    "Self-Citation Overload", "No Forward Vision", "Standards Blindness",
                    "SMILE Violation: Data First"],
        "layer_3": ["The Philosophy Lecture", "Buzzword Overload", "The Phantom Baseline",
                    "The Reinvented Wheel"],
    },
    "Impact": {
        "layer_1": ["Policy Alignment Gap", "Work Programme Parrot"],
        "layer_2": [],
        "layer_3": ["The Exploitation Fog", "The TAM Distraction", "Copy-Paste SSH",
                    "Output-Outcome Confusion", "D&E Conflation"],
    },
    "Implementation": {
        "layer_1": [],
        "layer_2": [],
        "layer_3": ["The Unfinished Template", "The Ghost Partner", "Time-Travel Deliverable",
                    "The Medium-High Everything", "Governance Template", "The Unmentionable Elephant",
                    "Meeting Milestones", "Technical-Only Risk Table", "Zero-PM Task Lead",
                    "Page Limit Risk", "Heavy Management WP", "Orphaned Acronyms"],
    },
}


def estimate_scores(result):
    scores = {}
    for criterion, pattern_map in CRITERION_MAP.items():
        base = 4.5
        penalty = 0
        all_patterns = pattern_map["layer_1"] + pattern_map["layer_2"] + pattern_map["layer_3"]
        # Also catch SMILE gaps
        all_patterns += [f"SMILE Gap: {p['name']}" for p in SMILE_PHASES.values()]
        all_patterns += [f"SMILE Perspective Gap: {p['name']}" for p in SMILE_PERSPECTIVES.values()]

        for f in result.findings:
            if f.pattern in all_patterns:
                penalty += SEVERITY_WEIGHTS.get(f.severity, 0.1)

        scores[criterion] = round(max(1.0, min(5.0, base - penalty)), 1)
    return scores


# ============================================================
# REPORT
# ============================================================

def format_report(result, pdf_path, page_count, smile_scores=None, has_call=False):
    scores = estimate_scores(result)
    total = sum(scores.values())
    severity_counts = Counter(f.severity for f in result.findings)
    layer_counts = Counter(f.layer for f in result.findings)
    pattern_counts = Counter(f.pattern for f in result.findings)

    lines = []
    w = 72

    lines.append("")
    lines.append("=" * w)
    lines.append("  C.R.U.C.I.B.L.E. v" + __version__)
    lines.append("  Consortia Review Under Controlled Interrogation")
    lines.append("  Before Live Evaluation")
    lines.append("=" * w)
    lines.append(f"  File:      {Path(pdf_path).name}")
    lines.append(f"  Pages:     {page_count}")
    lines.append(f"  Findings:  {len(result.findings)}")
    lines.append(f"  Call text: {'provided' if has_call else 'NOT PROVIDED (Layer 1 limited)'}")
    lines.append("")

    # --- Layered Score ---
    lines.append("  THREE-LAYER ANALYSIS")
    lines.append("  " + "-" * (w - 4))
    layer_names = {1: "Call Alignment", 2: "Field & SMILE", 3: "Anti-Patterns"}
    for layer in [1, 2, 3]:
        count = layer_counts.get(layer, 0)
        crits = len([f for f in result.findings if f.layer == layer and f.severity == "CRITICAL"])
        lines.append(f"  Layer {layer}: {layer_names[layer]:<20} {count:>3} findings ({crits} critical)")
    lines.append("")

    # --- Estimated Score ---
    lines.append("  ESTIMATED SCORE")
    lines.append("  " + "-" * (w - 4))
    for criterion, score in scores.items():
        filled = int(score * 4)
        bar = "#" * filled + "." * (20 - filled)
        status = "OK" if score >= 3.0 else "WEAK"
        lines.append(f"  {criterion:<16} {score}/5.0  [{bar}]  {status}")
    lines.append(f"  {'TOTAL':<16} {total:.1f}/15.0")
    passes = total >= 10 and all(s >= 3.0 for s in scores.values())
    lines.append(f"  Threshold: {'LIKELY ABOVE' if passes else 'AT RISK'}")
    lines.append("")

    # --- SMILE Radar ---
    if smile_scores:
        lines.append("  SMILE METHODOLOGY COVERAGE")
        lines.append("  " + "-" * (w - 4))
        for phase, coverage in smile_scores.items():
            bar_len = int(coverage / 5)
            bar = "#" * bar_len + "." * (20 - bar_len)
            status = "OK" if coverage >= 30 else "GAP"
            lines.append(f"  {phase:<26} {coverage:>3.0f}%  [{bar}]  {status}")
        lines.append("")

    # --- Severity ---
    lines.append("  SEVERITY")
    lines.append("  " + "-" * (w - 4))
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        c = severity_counts.get(sev, 0)
        icon = {"CRITICAL": "!!", "HIGH": "! ", "MEDIUM": "~ ", "LOW": "  "}
        lines.append(f"  {icon[sev]} {sev:<12} {c}")
    lines.append("")

    # --- Top patterns ---
    lines.append("  TOP ISSUES")
    lines.append("  " + "-" * (w - 4))
    for pattern, count in pattern_counts.most_common(15):
        lines.append(f"  [{count:>3}x] {pattern}")
    lines.append("")

    # --- Findings by layer ---
    lines.append("=" * w)
    lines.append("  FINDINGS BY LAYER")
    lines.append("=" * w)

    for layer in [1, 2, 3]:
        layer_findings = [f for f in result.findings if f.layer == layer]
        if not layer_findings:
            continue
        lines.append(f"\n  === LAYER {layer}: {layer_names[layer].upper()} ===\n")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            sev_findings = [f for f in layer_findings if f.severity == sev]
            if not sev_findings:
                continue
            lines.append(f"  --- {sev} ---")
            for f in sev_findings:
                pg = f"p.{f.page}" if f.page > 0 else "global"
                lines.append(f"  [{f.pattern}] ({pg})")
                lines.append(f"    {f.text}")
                lines.append(f"    -> {f.suggestion}")
                lines.append("")

    # --- Checklist ---
    lines.append("=" * w)
    lines.append("  PRE-SUBMISSION CHECKLIST")
    lines.append("=" * w)
    checklist = [
        "SMILE: Proposal leads with impact, not technology",
        "SMILE: All 6 phases addressed (Reality→Wisdom)",
        "SMILE: Three perspectives covered (People/Systems/Planet)",
        "CALL: Every expected outcome mapped to a WP/task",
        "CALL: Call terminology mirrored (not paraphrased)",
        "CALL: TRL targets align with action type",
        "CALL: Referenced EU policies match call text",
        "FIELD: ≥30% citations from last 2 years",
        "FIELD: Seminal/foundational work cited",
        "FIELD: Prior EU-funded projects referenced",
        "FIELD: Relevant standards bodies mentioned",
        "FIELD: Forward vision (roadmap, post-project)",
        "All placeholders removed",
        "Every KPI has a cited baseline",
        "Every partner: profile + prior work + personnel",
        "Every task passes Monday morning test",
        "No time-travel deliverables",
        "Each pilot has unique SSH analysis",
        "Milestones are achievements, not meetings",
        "Risk table: technical + management + market",
        "Outputs ≠ outcomes ≠ impacts",
        "Exploitation names partner + product + market",
        "Part B within page limit (40 pages RIA/IA)",
        "No zero-PM task leads",
        "Spellcheck + final read by non-author",
    ]
    for item in checklist:
        lines.append(f"  [ ] {item}")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def run_analysis(pdf_path, call_path=None, verbose=False):
    pages, page_count = extract_text(pdf_path)
    start = find_part_b_start(pages)
    if verbose:
        print(f"  Pages: {page_count}, Part B: ~p.{start}")

    result = AnalysisResult()
    call_text = None
    if call_path:
        call_text = extract_call_from_pdf(call_path)
        if verbose:
            print(f"  Call text: {len(call_text)} chars loaded")

    # Layer 1: Call Alignment
    if verbose:
        print("  Layer 1: Call Alignment...")
    check_call_alignment(pages, result, start, call_text)

    # Layer 2: Field Awareness + SMILE
    if verbose:
        print("  Layer 2: Field Awareness + SMILE...")
    check_field_awareness(pages, result, start)
    smile_scores = check_smile_alignment(pages, result, start)

    # Layer 3: Anti-Patterns
    detectors = [
        ("Placeholders", lambda: check_unfilled_placeholders(pages, result, start)),
        ("Buzzwords", lambda: check_buzzwords(pages, result, start)),
        ("Opening", lambda: check_opening(pages, result, start)),
        ("Baselines", lambda: check_baselines(pages, result, start)),
        ("Partners", lambda: check_ghost_partners(pages, result, start)),
        ("Copy-paste", lambda: check_copy_paste(pages, result, start)),
        ("Risks", lambda: check_risks(pages, result, start)),
        ("Timeline", lambda: check_timeline(pages, result, start)),
        ("Exploitation", lambda: check_exploitation(pages, result, start)),
        ("Market", lambda: check_market(pages, result, start)),
        ("Milestones", lambda: check_meeting_milestones(pages, result, start)),
        ("Output/Outcome", lambda: check_output_outcome_impact(pages, result, start)),
        ("Page count", lambda: check_page_count(pages, result, start)),
        ("Budget ratios", lambda: check_budget_ratios(pages, result, start)),
        ("D&E conflation", lambda: check_dissemination_exploitation_conflation(pages, result, start)),
        ("Zero-PM leads", lambda: check_zero_pm_wp_lead(pages, result, start)),
        ("State of Art", lambda: check_sota(pages, result, start)),
        ("Governance", lambda: check_governance(pages, result, start)),
        ("Acronyms", lambda: check_acronyms(pages, result, start)),
    ]

    if verbose:
        print("  Layer 3: Anti-Patterns...")
    for name, fn in detectors:
        try:
            fn()
            if verbose:
                print(f"    + {name}")
        except Exception as e:
            if verbose:
                print(f"    x {name}: {e}")

    return result, page_count, smile_scores


def main():
    parser = argparse.ArgumentParser(
        description="C.R.U.C.I.B.L.E. — Consortia Review Under Controlled Interrogation, Before Live Evaluation",
        epilog="Built on SMILE methodology. Impact first, data last.",
    )
    parser.add_argument("pdf", help="Path to proposal PDF")
    parser.add_argument("--call", "-c", metavar="PATH", help="Call/topic text file or PDF (enables Layer 1)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", "-j", metavar="PATH", help="Save JSON output")
    parser.add_argument("--output", "-o", metavar="PATH", help="Save report to file")

    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"File not found: {args.pdf}")
        sys.exit(1)

    print(f"\n  C.R.U.C.I.B.L.E. v{__version__}")
    print(f"  Analyzing: {args.pdf}")
    if args.call:
        print(f"  Call text: {args.call}")

    result, page_count, smile_scores = run_analysis(args.pdf, args.call, args.verbose)
    report = format_report(result, args.pdf, page_count, smile_scores, bool(args.call))
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        print(f"\n  Report: {args.output}")

    if args.json:
        scores = estimate_scores(result)
        data = {
            "tool": "CRUCIBLE",
            "version": __version__,
            "file": str(args.pdf),
            "call_provided": bool(args.call),
            "pages": page_count,
            "scores": scores,
            "total": sum(scores.values()),
            "smile_coverage": smile_scores,
            "findings": [
                {"pattern": f.pattern, "severity": f.severity, "page": f.page,
                 "text": f.text, "suggestion": f.suggestion,
                 "category": f.category, "layer": f.layer}
                for f in result.findings
            ],
        }
        Path(args.json).write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(f"  JSON:   {args.json}")


if __name__ == "__main__":
    main()
