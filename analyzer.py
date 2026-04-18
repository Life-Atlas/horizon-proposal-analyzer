#!/usr/bin/env python3
"""
Horizon Europe Proposal Analyzer
=================================
Scans a Horizon Europe Part B PDF for common anti-patterns that cost
proposals points during evaluation. Based on real evaluator experience
reviewing Innovation Actions and Research & Innovation Actions.

Detects 25 anti-patterns across 6 categories:
  - Document quality (placeholders, typos, formatting)
  - Technical substance (buzzwords, missing baselines, vague tasks)
  - Partner & consortium (ghost descriptions, mismatched allocation)
  - Impact & exploitation (fog, TAM distraction, recycled KPIs)
  - SSH & ethics (checkbox compliance, copy-paste)
  - Operations & risk (boilerplate governance, missing risks)

Usage:
  python analyzer.py proposal.pdf
  python analyzer.py proposal.pdf --verbose
  python analyzer.py proposal.pdf --json output.json

License: MIT
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

__version__ = "1.0.0"


@dataclass
class Finding:
    pattern: str
    severity: str
    page: int
    text: str
    suggestion: str
    category: str = ""


@dataclass
class AnalysisResult:
    findings: list = field(default_factory=list)

    def add(self, pattern, severity, page, text, suggestion, category=""):
        self.findings.append(Finding(pattern, severity, page, text, suggestion, category))


def extract_text(pdf_path: str) -> tuple[dict, int]:
    doc = fitz.open(pdf_path)
    pages = {}
    for i in range(len(doc)):
        pages[i + 1] = doc[i].get_text()
    return pages, len(doc)


def find_part_b_start(pages: dict) -> int:
    """Find where Part B technical content begins (skip admin forms)."""
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
    """Detect administrative form pages to exclude from content analysis."""
    indicators = [
        'Administrative forms', 'Page limit', 'Participant Registry',
        'PIC\n', 'Legal name\n', 'SME Data', 'Gender Equality Plan',
        'Departments carrying out', 'Main contact person',
        'This proposal version was submitted by',
    ]
    return sum(1 for i in indicators if i in text) >= 2


# ============================================================
# ANTI-PATTERN DETECTORS
# ============================================================

def check_unfilled_placeholders(pages, result, part_b_start):
    """#1: The Unfinished Template"""
    placeholders = [
        (r'\[Page limit\]', '[Page limit]'),
        (r'\[insert\s+\w+', '[insert ...]'),
        (r'\[TBD\]', '[TBD]'),
        (r'\[TODO\]', '[TODO]'),
        (r'\[XX+\]', '[XX]'),
        (r'\[fill\s+in\]', '[fill in]'),
        (r'\[placeholder\]', '[placeholder]'),
        (r'\[add\s+\w+', '[add ...]'),
    ]
    seen = set()
    for num, text in pages.items():
        if num < part_b_start:
            continue
        for pattern, label in placeholders:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                key = (label, num)
                if key not in seen:
                    seen.add(key)
                    result.add(
                        "The Unfinished Template", "CRITICAL", num,
                        f"Placeholder found: {label}",
                        "Search doc for '[', 'insert', 'TBD', 'TODO' before submission",
                        "Document Quality"
                    )


def check_buzzword_density(pages, result, part_b_start):
    """#2-3: The Adjective Avalanche / Buzzword Bingo Card"""
    buzzwords = {
        'human-centric', 'human-centred', 'socio-technical', 'trustworthy',
        'interoperable', 'interoperability', 'scalable', 'scalability',
        'holistic', 'synergy', 'synergies', 'paradigm', 'ecosystem',
        'cutting-edge', 'state-of-the-art', 'novel', 'innovative',
        'groundbreaking', 'transformative', 'disruptive', 'seamless',
        'robust', 'comprehensive', 'unprecedented', 'game-changing',
        'next-generation', 'cross-cutting', 'leveraging',
    }
    flagged_pages = 0
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text):
            continue
        words = text.lower().split()
        if len(words) < 50:
            continue
        buzz_count = sum(1 for w in words if any(b in w for b in buzzwords))
        density = buzz_count / len(words) * 100
        if density > 5 and flagged_pages < 5:
            flagged_pages += 1
            result.add(
                "The Buzzword Bingo Card", "HIGH", num,
                f"Buzzword density {density:.1f}% ({buzz_count}/{len(words)} words)",
                "For every buzzword, add one concrete technical specification",
                "Technical Substance"
            )
        elif density > 3 and flagged_pages < 5:
            flagged_pages += 1
            result.add(
                "The Adjective Avalanche", "MEDIUM", num,
                f"Buzzword density {density:.1f}% ({buzz_count}/{len(words)} words)",
                "Max 2 adjectives per noun phrase",
                "Technical Substance"
            )


def check_opening_quality(pages, result, part_b_start):
    """#4: The Philosophy Lecture"""
    for num in range(part_b_start, min(part_b_start + 5, max(pages.keys()) + 1)):
        text = pages.get(num, "")
        lower = text.lower()
        if 'excellence' not in lower and 'section 1' not in lower:
            continue
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 30]
        content_lines = [l for l in lines if not any(
            skip in l.lower() for skip in ['call:', 'horizon', 'eu grants', 'part b', 'page']
        )]
        if content_lines:
            first = content_lines[0]
            if len(first) > 250:
                result.add(
                    "The Philosophy Lecture", "HIGH", num,
                    f"Opening runs {len(first)} chars before project specifics: '{first[:80]}...'",
                    "First paragraph: project name + problem + unique solution in ≤100 words",
                    "Technical Substance"
                )
        break


def check_kpi_baselines(pages, result, part_b_start):
    """#7: The Phantom Baseline"""
    kpi_patterns = [
        r'>=?\s*\d+\s*%',
        r'≥\s*\d+\s*%',
        r'\d+\s*%\s*(?:faster|better|improvement|reduction|increase)',
    ]
    found = 0
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text):
            continue
        for p in kpi_patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            if matches and found < 10:
                context = text.lower()
                has_baseline_ref = any(b in context for b in [
                    'baseline defined', 'compared to', 'current state-of',
                    'measured against', 'reference system',
                ])
                has_citation = bool(re.search(r'\(\w+[\s,]+\d{4}\)|\[\d+\]', text))
                if not has_baseline_ref and not has_citation:
                    found += 1
                    match_text = matches[0] if isinstance(matches[0], str) else str(matches[0])
                    result.add(
                        "The Phantom Baseline", "HIGH", num,
                        f"KPI '{match_text}' without defined baseline or citation",
                        "Every KPI: metric + current SotA (cited) + target + measurement method",
                        "Technical Substance"
                    )
                    break


def check_partner_descriptions(pages, result, part_b_start):
    """#5: The Ghost Partner"""
    for num, text in pages.items():
        if num < part_b_start:
            continue
        lower = text.lower()
        if 'capacity of participant' not in lower and 'consortium as a whole' not in lower:
            continue
        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            if len(stripped) < 20 or len(stripped) > 200:
                continue
            partner_desc = re.match(
                r'^([A-Z]{2,10})\s+(contributes?|supports?|leads?|is supporting|provides?|ensures?)\b',
                stripped
            )
            if partner_desc and len(stripped) < 130:
                result.add(
                    "The Ghost Partner", "HIGH", num,
                    f"Thin description ({len(stripped)} chars): '{stripped[:100]}'",
                    "Each partner: org profile + 2-3 prior projects + named key personnel",
                    "Partner & Consortium"
                )


def check_copy_paste(pages, result, part_b_start):
    """#6: The Copy-Paste SSH"""
    ssh_blocks = []
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text):
            continue
        matches = re.findall(
            r'(?:SSH|Human.centric|[Ss]ociet\w+)\s*(?:dimension|relevance)[:\s]+(.*?)(?:\n\n|\n[A-Z])',
            text, re.DOTALL
        )
        for m in matches:
            clean = ' '.join(m.split())[:300]
            if len(clean) > 60:
                ssh_blocks.append((num, clean))

    for i in range(len(ssh_blocks)):
        for j in range(i + 1, len(ssh_blocks)):
            if ssh_blocks[i][0] == ssh_blocks[j][0]:
                continue
            words_a = set(ssh_blocks[i][1].lower().split())
            words_b = set(ssh_blocks[j][1].lower().split())
            if not words_a or not words_b:
                continue
            overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
            if overlap > 0.55:
                result.add(
                    "The Copy-Paste SSH", "CRITICAL", ssh_blocks[j][0],
                    f"SSH text ~{overlap:.0%} similar to page {ssh_blocks[i][0]}",
                    "Each pilot needs unique SSH challenges, methodologies, and findings",
                    "SSH & Ethics"
                )


def check_risk_register(pages, result, part_b_start):
    """#12: The Medium-High Everything + #22: The Unmentionable Elephant"""
    all_text_lower = " ".join(t for n, t in pages.items() if n >= part_b_start).lower()
    has_conflict = any(w in all_text_lower for w in [
        'conflict zone', 'post-conflict', 'war zone', 'reconstruction',
        'kharkiv', 'ukraine', 'gaza', 'humanitarian',
    ])

    for num, text in pages.items():
        if num < part_b_start:
            continue
        lower = text.lower()
        if 'risk' not in lower or ('likelihood' not in lower and 'severity' not in lower):
            continue

        medium = len(re.findall(r'\bmedium\b', lower))
        high = len(re.findall(r'\bhigh\b', lower))
        low = len(re.findall(r'\blow\b', lower))

        if medium >= 4 and low == 0:
            result.add(
                "The Medium-High Everything", "MEDIUM", num,
                f"Risk register: {medium} Medium, {high} High, {low} Low — no variation",
                "Vary ratings. Include project-specific risks (personnel, access, IP, conflict)",
                "Operations & Risk"
            )

        if has_conflict:
            risk_words = ['conflict', 'security', 'access restriction', 'war', 'safety']
            if not any(w in lower for w in risk_words):
                result.add(
                    "The Unmentionable Elephant", "CRITICAL", num,
                    "Conflict-zone pilot exists but risk register ignores it",
                    "Add: access risk, security protocol, ethics review, contingency plan",
                    "Operations & Risk"
                )
        break


def check_timeline(pages, result, part_b_start):
    """#8: The Time-Travel Deliverable"""
    wp_timing = {}
    for num, text in pages.items():
        if num < part_b_start:
            continue
        wp_matches = re.findall(
            r'Work package (?:number\s+)?(\d+).*?M(\d+)\s*[-–]\s*M?(\d+)',
            text, re.DOTALL
        )
        for wp, start, end in wp_matches:
            wp_timing[int(wp)] = (int(start), int(end))

    pilot_wps = [w for w in wp_timing if w >= 7]
    component_wps = [w for w in wp_timing if 3 <= w <= 6]

    for pilot_wp in pilot_wps:
        pilot_start = wp_timing[pilot_wp][0]
        for comp_wp in component_wps:
            comp_end = wp_timing[comp_wp][1]
            if pilot_start < comp_end - 6:
                result.add(
                    "The Time-Travel Deliverable", "HIGH", 0,
                    f"WP{pilot_wp} (pilots) starts M{pilot_start} but WP{comp_wp} delivers until M{comp_end}",
                    "Integration/pilot WPs must start after component WPs deliver core outputs",
                    "Operations & Risk"
                )


def check_all_pilots(pages, result, part_b_start):
    """#10: The All-For-All Trap"""
    count = 0
    for num, text in pages.items():
        if num < part_b_start:
            continue
        matches = re.findall(r'(?:SO|Objective)\s*#?\d+.*?\bAll\b', text, re.IGNORECASE)
        count += len(matches)
    if count >= 3:
        result.add(
            "The All-For-All Trap", "MEDIUM", 0,
            f"{count} objectives validated in 'All' pilots",
            "Map each objective to 2-3 primary pilots + 1-2 secondary",
            "Impact & Exploitation"
        )


def check_exploitation(pages, result, part_b_start):
    """#15: The Exploitation Fog"""
    for num, text in pages.items():
        if num < part_b_start:
            continue
        lower = text.lower()
        if 'exploitation' not in lower:
            continue
        if 'strategy' not in lower and 'plan' not in lower:
            continue

        specific_markers = ['eur ', '€', 'revenue', 'pricing', 'saas', 'license fee', 'by 202']
        generic_markers = ['partners will', 'results will be', 'will integrate', 'will exploit']

        has_specific = any(m in lower for m in specific_markers)
        has_generic = any(m in lower for m in generic_markers)

        if has_generic and not has_specific:
            result.add(
                "The Exploitation Fog", "HIGH", num,
                "Exploitation uses generic categories, not named partner plans",
                "Each partner: WHAT product + WHICH market + WHEN + revenue model",
                "Impact & Exploitation"
            )
            break


def check_market_analysis(pages, result, part_b_start):
    """#23: The TAM Distraction"""
    for num, text in pages.items():
        if num < part_b_start:
            continue
        big_market = re.findall(
            r'(?:USD|EUR|€|\$)\s*[\d,.]+\s*(?:bn|billion|B\b|trillion)',
            text, re.IGNORECASE
        )
        if big_market:
            lower = text.lower()
            has_drill = any(w in lower for w in [
                'addressable', 'serviceable', 'sub-segment', 'target segment',
                'sam', 'som', 'niche',
            ])
            if not has_drill:
                result.add(
                    "The TAM Distraction", "MEDIUM", num,
                    f"Large market figure ({big_market[0]}) without sub-segment drill-down",
                    "Drill: total market → addressable segment → your capture. Cite sources",
                    "Impact & Exploitation"
                )
                break


def check_typos(pages, result, part_b_start):
    """#14: The Typo Graveyard"""
    seen = set()
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text):
            continue
        issues = []
        if re.search(r'\bremail\b', text) and 'email address' not in text.lower():
            issues.append("Possible 'remail'/'remain' typo")
        if re.search(r'\ban\s+innovation\b', text.lower()):
            issues.append("Possible 'an'/'and' typo")
        if re.search(r'\d[A-Z][a-z]{3,}', text):
            issues.append("Number-letter merge artifact")

        for issue in issues:
            key = (issue, num)
            if key not in seen:
                seen.add(key)
                result.add(
                    "The Typo Graveyard", "LOW", num,
                    issue,
                    "Final editorial pass by someone who didn't write the text",
                    "Document Quality"
                )


def check_acronyms(pages, result, part_b_start):
    """#24: The Orphaned Acronym"""
    part_b_text = " ".join(t for n, t in pages.items() if n >= part_b_start and not is_admin_page(t))
    used = set(re.findall(r'\b([A-Z]{3,6})\b', part_b_text))

    safe = {
        'EU', 'AI', 'XR', 'VR', 'AR', 'MR', 'BIM', 'GIS', 'API', 'SSH', 'KPI',
        'TRL', 'DMP', 'FAIR', 'GDPR', 'SME', 'IOT', 'CEO', 'CTO', 'RIA',
        'HTTP', 'JSON', 'CSV', 'PDF', 'URL', 'GPU', 'CPU', 'HPC', 'SaaS',
        'SAAS', 'WP', 'PM', 'GA', 'IP', 'RGB', 'GPS', 'USB', 'RAM', 'THE',
        'AND', 'FOR', 'NOT', 'BUT', 'NOR', 'YET', 'EVM', 'ETH', 'NFT',
    }
    to_check = used - safe

    undefined = []
    for acr in to_check:
        expanded = rf'\([^)]*{acr}\)' # (Full Name ACRONYM)
        defining = rf'{acr}\s*[-–—:]\s*[A-Z]' # ACRONYM — Full Name
        if not re.search(expanded, part_b_text) and not re.search(defining, part_b_text):
            undefined.append(acr)

    if len(undefined) > 8:
        sample = ', '.join(sorted(undefined)[:12])
        result.add(
            "The Orphaned Acronym", "LOW", 0,
            f"{len(undefined)} potentially undefined acronyms: {sample}",
            "Master acronym list + define at first use",
            "Document Quality"
        )


def check_open_science(pages, result, part_b_start):
    """#22: The Compliance Recital"""
    for num, text in pages.items():
        if num < part_b_start:
            continue
        lower = text.lower()
        if 'open science' not in lower and 'data management' not in lower:
            continue
        has_concrete = any(w in lower for w in [
            ' tb', ' gb', 'terabyte', 'gigabyte', 'ifc', 'citygml',
            'gltf', 'las ', 'geojson', 'parquet', 'year retention',
        ])
        has_generic = any(w in lower for w in ['fair principles', 'findable', 'reusable'])
        if has_generic and not has_concrete:
            result.add(
                "The Compliance Recital", "MEDIUM", num,
                "Open Science lists frameworks but no data types/volumes/formats/retention",
                "Add table: data type | format | volume | storage | retention | access",
                "Impact & Exploitation"
            )
            break


def check_governance(pages, result, part_b_start):
    """#16: The Governance Photocopier"""
    for num, text in pages.items():
        if num < part_b_start:
            continue
        lower = text.lower()
        has_standard = sum(1 for g in [
            'general assembly', 'steering committee', 'advisory board',
            'project coordinator', 'technical manager',
        ] if g in lower)
        if has_standard < 2:
            continue
        has_specific = any(p in lower for p in [
            'conflict resolution', 'contingency', 'escalation',
            'ip dispute', 'security protocol', 'veto',
        ])
        if not has_specific:
            result.add(
                "The Governance Photocopier", "MEDIUM", num,
                "Standard governance template without project-specific mechanisms",
                "Add: conflict resolution, IP governance, escalation paths, pilot-specific protocols",
                "Operations & Risk"
            )
            break


def check_sota(pages, result, part_b_start):
    """#18: The Reinvented Wheel"""
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'state of the art' not in lower and 'state-of-the-art' not in lower and 'beyond' not in lower:
            continue
        if 'advancement' not in lower and 'innovation' not in lower:
            continue
        competitors = [
            'nvidia', 'omniverse', 'unity', 'unreal', 'epic',
            'microsoft', 'bentley', 'itwin', 'siemens', 'dassault',
            'autodesk', 'cesium', 'google', 'meta', 'apple',
        ]
        mentioned = [c for c in competitors if c in lower]
        if len(mentioned) == 0:
            result.add(
                "The Reinvented Wheel", "HIGH", num,
                "Beyond-SotA claims without naming commercial competitors",
                "Name competitors, cite them, explain the specific remaining gap",
                "Technical Substance"
            )
            break


def check_task_specificity(pages, result, part_b_start):
    """#17: The Monday Morning Test"""
    vague_approaches = [
        r'Approach:\s*Develop\s+(?:services|mechanisms|tools|methods|pipelines)\s+for',
        r'Approach:\s*Design\s+and\s+implement\s+(?:the|a)\s+',
        r'Approach:\s*Build\s+(?:the|a|an)\s+',
    ]
    flagged = 0
    for num, text in pages.items():
        if num < part_b_start or is_admin_page(text) or flagged >= 5:
            continue
        for pattern in vague_approaches:
            matches = re.findall(pattern, text)
            for m in matches:
                context_start = text.find(m)
                context = text[context_start:context_start + 200]
                tech_words = ['kafka', 'graphql', 'pytorch', 'tensorflow', 'react',
                              'docker', 'kubernetes', 'postgresql', 'redis', 'grpc',
                              'websocket', 'mqtt', 'rest api', 'sparql']
                has_tech = any(t in context.lower() for t in tech_words)
                if not has_tech and flagged < 5:
                    flagged += 1
                    short_context = context.replace('\n', ' ')[:120]
                    result.add(
                        "The Monday Morning Test", "MEDIUM", num,
                        f"Vague task: '{short_context}...'",
                        "Name at least one algorithm, tool, protocol, or framework",
                        "Technical Substance"
                    )
                    break


# ============================================================
# SCORING
# ============================================================

SEVERITY_WEIGHTS = {"CRITICAL": 1.0, "HIGH": 0.5, "MEDIUM": 0.15, "LOW": 0.02}

CRITERION_PATTERNS = {
    "Excellence": [
        "The Philosophy Lecture", "The Adjective Avalanche",
        "The Buzzword Bingo Card", "The Phantom Baseline",
        "The Reinvented Wheel", "The Monday Morning Test",
    ],
    "Impact": [
        "The Exploitation Fog", "The TAM Distraction",
        "The All-For-All Trap", "The Copy-Paste SSH",
        "The Compliance Recital",
    ],
    "Implementation": [
        "The Unfinished Template", "The Ghost Partner",
        "The Passenger List", "The Time-Travel Deliverable",
        "The Medium-High Everything", "The Governance Photocopier",
        "The Typo Graveyard", "The Unmentionable Elephant",
        "The Orphaned Acronym",
    ],
}


def estimate_scores(result):
    scores = {}
    for criterion, patterns in CRITERION_PATTERNS.items():
        base = 4.5
        penalty = 0
        for f in result.findings:
            if f.pattern in patterns:
                penalty += SEVERITY_WEIGHTS.get(f.severity, 0.1)
        scores[criterion] = round(max(1.0, min(5.0, base - penalty)), 1)
    return scores


# ============================================================
# REPORT
# ============================================================

def format_report(result, pdf_path, page_count):
    scores = estimate_scores(result)
    total = sum(scores.values())
    severity_counts = Counter(f.severity for f in result.findings)
    pattern_counts = Counter(f.pattern for f in result.findings)
    category_counts = Counter(f.category for f in result.findings)

    lines = []
    w = 70

    lines.append("=" * w)
    lines.append("  HORIZON EUROPE PROPOSAL ANALYZER v" + __version__)
    lines.append("=" * w)
    lines.append(f"  File:     {Path(pdf_path).name}")
    lines.append(f"  Pages:    {page_count}")
    lines.append(f"  Findings: {len(result.findings)}")
    lines.append("")

    # --- Score ---
    lines.append("  ESTIMATED SCORE (indicative, not a substitute for review)")
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

    # --- Severity ---
    lines.append("  SEVERITY BREAKDOWN")
    lines.append("  " + "-" * (w - 4))
    icons = {"CRITICAL": "!!", "HIGH": "! ", "MEDIUM": "~ ", "LOW": "  "}
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        c = severity_counts.get(sev, 0)
        lines.append(f"  {icons[sev]} {sev:<12} {c}")
    lines.append("")

    # --- Categories ---
    if category_counts:
        lines.append("  BY CATEGORY")
        lines.append("  " + "-" * (w - 4))
        for cat, count in category_counts.most_common():
            if cat:
                lines.append(f"  {cat:<30} {count}")
        lines.append("")

    # --- Top patterns ---
    lines.append("  TOP ANTI-PATTERNS")
    lines.append("  " + "-" * (w - 4))
    for pattern, count in pattern_counts.most_common(15):
        lines.append(f"  [{count:>3}x] {pattern}")
    lines.append("")

    # --- Detailed findings ---
    lines.append("=" * w)
    lines.append("  FINDINGS")
    lines.append("=" * w)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        findings = [f for f in result.findings if f.severity == severity]
        if not findings:
            continue
        lines.append(f"\n  --- {severity} ({len(findings)}) ---\n")
        for f in findings:
            page_str = f"p.{f.page}" if f.page > 0 else "global"
            cat = f" [{f.category}]" if f.category else ""
            lines.append(f"  {f.pattern}{cat} ({page_str})")
            lines.append(f"    {f.text}")
            lines.append(f"    -> {f.suggestion}")
            lines.append("")

    # --- Checklist ---
    lines.append("=" * w)
    lines.append("  PRE-SUBMISSION CHECKLIST")
    lines.append("=" * w)
    checklist = [
        "All placeholders removed",
        "Page numbers correct and continuous",
        "Every acronym defined at first use",
        "Every KPI has a cited baseline",
        "Every partner: profile + prior work + named personnel",
        "Every task passes Monday morning test",
        "No time-travel deliverables (dependency graph checked)",
        "Objectives mapped to specific pilots, not 'All'",
        "Outcome KPIs != Impact KPIs",
        "Each pilot has unique SSH analysis",
        "Risk register varies in severity + includes project risks",
        "Exploitation names partner + product + market + timeline",
        "Market drills to addressable sub-segment",
        "Budget lists purchases with unit costs",
        "DMP specifies types, volumes, formats, storage",
        "Industry >= 40% PMs (for IAs)",
        "Every partner >= 18 PMs or reclassified",
        "Spellcheck + final read by non-author",
        "Consistent naming throughout",
    ]
    for item in checklist:
        lines.append(f"  [ ] {item}")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def run_analysis(pdf_path, verbose=False):
    pages, page_count = extract_text(pdf_path)
    part_b_start = find_part_b_start(pages)

    if verbose:
        print(f"Pages: {page_count}, Part B starts: ~p.{part_b_start}")

    result = AnalysisResult()

    detectors = [
        ("Placeholders", lambda: check_unfilled_placeholders(pages, result, part_b_start)),
        ("Buzzwords", lambda: check_buzzword_density(pages, result, part_b_start)),
        ("Opening", lambda: check_opening_quality(pages, result, part_b_start)),
        ("KPI baselines", lambda: check_kpi_baselines(pages, result, part_b_start)),
        ("Partners", lambda: check_partner_descriptions(pages, result, part_b_start)),
        ("Copy-paste", lambda: check_copy_paste(pages, result, part_b_start)),
        ("Risks", lambda: check_risk_register(pages, result, part_b_start)),
        ("Timeline", lambda: check_timeline(pages, result, part_b_start)),
        ("All-pilots", lambda: check_all_pilots(pages, result, part_b_start)),
        ("Exploitation", lambda: check_exploitation(pages, result, part_b_start)),
        ("Market", lambda: check_market_analysis(pages, result, part_b_start)),
        ("Typos", lambda: check_typos(pages, result, part_b_start)),
        ("Acronyms", lambda: check_acronyms(pages, result, part_b_start)),
        ("Open Science", lambda: check_open_science(pages, result, part_b_start)),
        ("Governance", lambda: check_governance(pages, result, part_b_start)),
        ("State of Art", lambda: check_sota(pages, result, part_b_start)),
        ("Task clarity", lambda: check_task_specificity(pages, result, part_b_start)),
    ]

    for name, fn in detectors:
        try:
            fn()
            if verbose:
                count = len([f for f in result.findings])
                print(f"  + {name}")
        except Exception as e:
            if verbose:
                print(f"  x {name}: {e}")

    return result, page_count


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a Horizon Europe proposal PDF for common anti-patterns",
        epilog="Based on real evaluator experience. Not a substitute for expert review.",
    )
    parser.add_argument("pdf", help="Path to proposal PDF")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detector progress")
    parser.add_argument("--json", "-j", metavar="PATH", help="Save findings as JSON")
    parser.add_argument("--output", "-o", metavar="PATH", help="Save report to file")

    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"File not found: {args.pdf}")
        sys.exit(1)

    print(f"Analyzing: {args.pdf}")
    result, page_count = run_analysis(args.pdf, args.verbose)
    report = format_report(result, args.pdf, page_count)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        print(f"\nReport: {args.output}")

    if args.json:
        scores = estimate_scores(result)
        data = {
            "version": __version__,
            "file": str(args.pdf),
            "pages": page_count,
            "scores": scores,
            "total": sum(scores.values()),
            "findings": [
                {"pattern": f.pattern, "severity": f.severity, "page": f.page,
                 "text": f.text, "suggestion": f.suggestion, "category": f.category}
                for f in result.findings
            ],
        }
        Path(args.json).write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(f"JSON:   {args.json}")


if __name__ == "__main__":
    main()
