"""
CRUCIBLE Module: Vinnova 2026-01401 — Ekosysteminsats: verifiering och
validering för kommersialisering av kunskapsintensiva idéer.

Calibrated against exactly ONE call. Every constant, question and
criterion below is lifted verbatim from the call's own documents:

  - Utlysningstext (Vinnova dnr 2026-01401)
  - Projektbeskrivningsmall (docx template, 7 sections + 4 tables)
  - Anvisning till stödberättigande kostnader 2026 (dnr 2025-04644)

This module deliberately does NOT reuse the generic `vinnova` module,
which is calibrated for Impact Innovation (four criteria on a 1-7 scale,
2/5/10 MSEK category caps, 14-36 months, LOI required). None of that
applies here.

What is different here:
  - THREE assessment criteria, seven sub-criteria, scored 0-10
  - Gender equality sits inside TWO of the three main criteria
  - Hard formal requirements: breach = direct rejection (avslag).
    A formal FAIL forces the composite to 0.
  - Only two attachments are requested: Projektbeskrivningsmall and
    Intyg om stöd av mindre betydelse. No LOI, no avsiktsförklaring,
    no modellförsäkran.

Scoring is derived from measurable signals in the document (presence of
the template's answers, the four tables, numbers, citations, named
people with gender, terminology coverage, quantified before/after
pairs) — not from generic buzzword lists. Term matching is done on word
STEMS over body text only; table rows and template instruction lines are
stripped before counting so a filled-in table cannot inflate prose
scores.

MIT License — WINNIIO AB / Life Atlas
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Optional

from modules import CallModule

if TYPE_CHECKING:
    from crucible import AnalysisResult, ProposalAnchor, ProposalModel


# ============================================================
# CALL CONSTANTS — verbatim from Utlysningstext 2026-01401
# ============================================================

CALL_DNR = "2026-01401"
CALL_TITLE = ("Ekosysteminsats — verifiering och validering för "
              "kommersialisering av kunskapsintensiva idéer")

# "Projektet får ansöka om max 500 000 kronor."
MAX_GRANT_SEK = 500_000

# "Maximalt bidrag som kan sökas är 500 000 kronor, projektlängd tre månader."
MAX_DURATION_MONTHS = 3

# "20 okt. 2026 Projekt får starta"
EARLIEST_START = date(2026, 10, 20)
# "Projektet måste starta senast 26 oktober 2026 och avslutas senast 31 januari 2027."
LATEST_START = date(2026, 10, 26)
LATEST_END = date(2027, 1, 31)

# "Kostnader för konsulttjänster och licenser får uppgå till högst
#  20 procent av en organisations budget."
MAX_CONSULT_LICENSE_SHARE = 0.20

# "Indirekta kostnader får uppgå till högst 30 procent av lönekostnaderna."
MAX_INDIRECT_SHARE_OF_SALARY = 0.30

# Projektbeskrivningsmall: "Ifylld mall får maximalt utgöra 7 sidor."
MAX_PAGES = 7
# "Typsnitt med 11 punkters storlek ska användas."
MIN_FONT_PT = 11
# "# 1. Projektsammanfattning (max 1500 tecken)"
MAX_SUMMARY_CHARS = 1500

# "Utlysningen vänder sig inte till aktörer som beviljats bidrag i utlysning ..."
EXCLUDED_CALL_DNRS = {
    "2025-01651": "Verifiering för tillväxt 2025",
    "2023-03309": ("Stöd till nystartade företag genom excellenta "
                   "inkubatorer, perioden 1 juli 2025 – 30 juni 2029"),
}

# "Till ansökan bifogar ni även dessa bilagor: Projektbeskrivningsmall /
#  Intyg om de minimis-stöd"
REQUESTED_ATTACHMENTS = ["Projektbeskrivningsmall", "Intyg om de minimis-stöd"]

# Attachments this call does NOT ask for — carrying them over from another
# Vinnova call wastes days and signals a copy-paste application.
UNREQUESTED_ATTACHMENT_STEMS = [
    "avsiktsförklaring", "letter of intent", "modellförsäkran",
    "icke-konfidentiell sammanfattning", "cv-mall",
]

# "Aktörer som innovationshubbar, forskningsinstitut, regioner
#  (innovationsplattformar), forsknings- och innovationsinfrastrukturer,
#  test- och demomiljöer, science parks, kluster och andra intermediärer"
ELIGIBLE_ACTOR_STEMS = [
    "forskningsinstitut", "regional innovationsplattform",
    "innovationsplattform", "forsknings- och innovationsinfrastruktur",
    "innovationsinfrastruktur", "test- och demomiljö", "testbädd",
    "demomiljö", "science park", "innovationshubb", "innovationskluster",
    "kluster", "intermediär", "inkubator",
]

# The call's own vocabulary. Terminology coverage is measured against this
# list — NOT against Horizon Europe vocabulary.
CALL_TERMS = [
    "kunskapsintensiva idéer", "verifiering", "validering", "kommersialisering",
    "rätt tidpunkt", "mognadsfas", "idébärare", "idéägare", "stödsystem",
    "stödverksamhet", "intermediär", "innovationshubb", "science park",
    "innovationskluster", "test- och demomiljö",
    "forsknings- och innovationsinfrastruktur", "regional innovationsplattform",
    "målgrupp", "efterfrågan", "kvalitet", "kapacitet", "jämställdhet",
    "kön", "genus", "kvinnliga idébärare", "investeringsredo",
    "nationell innovationsstödsförmåga",
]


# ============================================================
# THE TEMPLATE'S MANDATORY QUESTIONS
# ============================================================
# Each entry's `question` is the Projektbeskrivningsmall's own wording —
# it becomes the finding text when the question is unanswered, so the
# author can paste it straight back into the document.
#
# `groups`: a list of stem-groups. A group is satisfied if ANY of its
# stems appears in body text. The question counts as answered only when
# EVERY group is satisfied. `computed` routes to a structural detector
# (tables, quantification) instead of stems.
# `feeds`: which sub-criterion loses points when this is missing.

MALL_QUESTIONS: list[dict] = [
    {
        "id": "M1.1", "chapter": "1. Projektsammanfattning",
        "question": "Sammanfatta den process/metod/eller verktyg som förstudien ska förbereda underlag till. Ge en kort bakgrund till varför ni lämnar in denna ansökan, max 1500 tecken.",
        "groups": [["projektsammanfattning", "sammanfattning", "summary"]],
        "severity": "HIGH", "feeds": "P2",
    },
    {
        "id": "M2.1", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Beskriv glapp/brister som ni ser idag för att kunskapsintensiva idéer ska kunna verifieras och valideras vid rätt läge/tidpunkt och av rätt aktörer.",
        "groups": [["glapp", "brist"], ["verifier", "valider"]],
        "severity": "CRITICAL", "feeds": "P2",
    },
    {
        "id": "M2.2", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Vem eller vilka är det som är primär målgrupp för er lösning (process/metodik/verktyg)?",
        "groups": [["primär målgrupp", "primära målgrupp", "primärmålgrupp",
                    "huvudmålgrupp"]],
        "severity": "HIGH", "feeds": "P2",
    },
    {
        "id": "M2.3", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Finns sekundära målgrupper, och i så fall vilka?",
        "groups": [["sekundär målgrupp", "sekundära målgrupp",
                    "sekundärmålgrupp"]],
        "severity": "HIGH", "feeds": "P2",
    },
    {
        "id": "M2.4", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Beskriv hur införandet av lösningen kan utveckla ett mer sammanhängande, effektivt och överblickbart stödsystem med ökad kvalitet och kapacitet för verifiering och validering hos målgruppen.",
        "groups": [["sammanhängande"], ["effektiv"], ["överblickbar"],
                   ["kvalitet"], ["kapacitet"]],
        "severity": "CRITICAL", "feeds": "P1",
    },
    {
        "id": "M2.5", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Beskriv hur ni avser att ta reda på hur stor efterfrågan på er lösning är?",
        "groups": [["efterfråga", "efterfrågan"],
                   ["undersök", "ta reda på", "kartlägg", "enkät", "intervju",
                    "marknadsanalys", "betalningsvilja"]],
        "severity": "CRITICAL", "feeds": "P2",
    },
    {
        "id": "M2.6", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Beskriv hur projektet påverkar jämställdheten inom projektparternas verksamhet.",
        "groups": [["jämställ"],
                   ["projektpart", "projektgrupp", "projektteam",
                    "parternas verksamhet", "vår verksamhet", "egna verksamhet"]],
        "severity": "CRITICAL", "feeds": "P3",
    },
    {
        "id": "M2.7", "chapter": "2. Behovsanalys och hypoteser",
        "question": "Beskriv hur projektet påverkar jämställdheten hos de idéägare och företag som senare tar del av utvecklade tjänster. Prioriterat är projekt som leder till att öka andelen kvinnliga idébärare, företagsledare och projektutförare.",
        "groups": [["jämställ", "kvinn"],
                   ["idéägare", "idébärare", "företagsledare", "projektutförare",
                    "som tar del", "användare av tjänsten"]],
        "severity": "CRITICAL", "feeds": "P3",
    },
    {
        "id": "M3.1", "chapter": "3. Angreppssätt",
        "question": "vad levereras konkret till målgruppen",
        "groups": [["levereras", "leverabel", "leverans", "levererar"],
                   ["målgrupp"]],
        "severity": "HIGH", "feeds": "G1",
    },
    {
        "id": "M3.2", "chapter": "3. Angreppssätt",
        "question": "på vilket sätt avser lösningen att förbättra/effektivisera målgruppens/målgruppernas förmåga att driva stödverksamhet? Beskriv förbättringen/effektiviseringen i så konkreta termer som möjligt: Vilka arbetsmoment, vilka mognadsfaser etc.",
        "groups": [["stödverksamhet", "stödsystem"],
                   ["arbetsmoment", "mognadsfas", "processteg", "process-steg",
                    "arbetssteg", "faser i"]],
        "severity": "CRITICAL", "feeds": "P1",
    },
    {
        "id": "M3.3", "chapter": "3. Angreppssätt",
        "question": "Beskriv hypotes för beräknade kostnader, resursbehov",
        "groups": [["hypotes"], ["kostnad"], ["resursbehov", "resurser"]],
        "severity": "HIGH", "feeds": "G1",
    },
    {
        "id": "M3.4", "chapter": "3. Angreppssätt",
        "question": "en plan för implementering av lösningen",
        "groups": [["implementer"], ["plan"]],
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M3.5", "chapter": "3. Angreppssätt",
        "question": "Vilka ytterligare resurser förutom Vinnovas bidrag kommer ni att behöva attrahera för att genomföra utvecklingen, och hur kommer detta att realiseras?",
        "groups": [["ytterligare resurser", "ytterligare finansiering",
                    "medfinansier", "attrahera", "ytterligare medel"],
                   ["realiser", "säkras", "säkerställ", "nästa steg", "hur detta"]],
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M4.1", "chapter": "4. Förväntade resultat",
        "question": "Vad blir nyttan och utfallet för nationell innovationsstödsförmåga ifall ni lyckas?",
        "groups": [["innovationsstödsförmåga", "innovationsstödsystem",
                    "innovationsstödssystem", "nationell", "sverige"],
                   ["nytta", "utfall", "effekt"]],
        "severity": "HIGH", "feeds": "G1",
    },
    {
        "id": "M4.2", "chapter": "4. Förväntade resultat",
        "question": "Kvantifiera utfallet om möjligt.",
        "computed": "quantified_outcome",
        "severity": "HIGH", "feeds": "P2",
    },
    {
        "id": "M5.1", "chapter": "5. Projektplan och arbetspaket",
        "question": "Projektplan (Beskriv innehåll och mål för respektive arbetspaket)",
        "groups": [["arbetspaket", "projektplan", "ap 1", "ap1"]],
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M5.2", "chapter": "5. Projektplan och arbetspaket",
        "question": "Här anger ni kortfattat allmän information kring projekts genomförande, arbetsmetodik, om projektet har andra specifika resursbehov.",
        "groups": [["arbetsmetodik", "metodik", "metod"]],
        "severity": "HIGH", "feeds": "G1",
    },
    {
        "id": "M5.3", "chapter": "5. Projektplan och arbetspaket",
        "question": "samt hur jämställdhetsaspekter integrerats i projektplanen",
        "groups": [["jämställ"],
                   ["projektplan", "arbetspaket", "genomförande", "aktivitet"]],
        "severity": "CRITICAL", "feeds": "G2",
    },
    {
        "id": "M5.4", "chapter": "5. Projektplan och arbetspaket",
        "question": "TABELL 1: Arbetspaket (AP) | Beskrivning av aktivitet och dess konkreta resultat | Kostnad",
        "computed": "table1",
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M5.5", "chapter": "5. Projektplan och arbetspaket",
        "question": "TABELL 2: Arbetspaket | Tidsperiod | Medverkande personer | Personal (SEK) | Tid (timmar) | Konsultkostnader, licenser m.m | Utrustning, mark, byggnader | Övriga direkta Kostnader | Indirekta kostnader | Egen finansiering (SEK) | Sökt bidrag (SEK)",
        "computed": "table2",
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M6.1", "chapter": "6. Risker",
        "question": "Vad upplever ni som svårt och riskfyllt, avseende projektgenomförandet?",
        # A filled, scored TABELL 3 IS the answer to this question — the
        # template's own instrument for "what is difficult and risky".
        # Requiring the literal word "genomförande" in prose made a
        # complete risk table read as an unanswered question.
        "groups": [["risk"], ["genomför", "projektgenomförande",
                              "@table3_scored"]],
        "severity": "HIGH", "feeds": "G1",
    },
    {
        "id": "M6.2", "chapter": "6. Risker",
        "question": "Vilka risker ser ni med att er lösning inte tas fram, för målgruppen, idébärarna av kunskapsintensiva idéer och stödsystemet i stort?",
        "groups": [["inte tas fram", "uteblir", "om lösningen inte",
                    "om vi inte", "utan lösningen", "inte kommer till stånd",
                    "inte genomförs", "uteblivet"]],
        "severity": "CRITICAL", "feeds": "P2",
    },
    {
        "id": "M6.3", "chapter": "6. Risker",
        "question": "TABELL 3: Risk | Sannolikhet (1-5) | Konsekvens (1-5) | Åtgärd",
        "computed": "table3",
        "severity": "CRITICAL", "feeds": "G1",
    },
    {
        "id": "M7.1", "chapter": "7. Team och organisation",
        "question": "Motiv för val av medverkande projektparters och deras roll i projektet",
        "groups": [["motiv", "därför att", "skälet"], ["part"], ["roll"]],
        "severity": "CRITICAL", "feeds": "A2",
    },
    {
        "id": "M7.2", "chapter": "7. Team och organisation",
        "question": "Beskriv behov av kompetenser, erfarenheter och andra faktorer inom teamet som är avgörande för projektet.",
        "groups": [["kompetens"], ["erfarenhet"]],
        "severity": "HIGH", "feeds": "A2",
    },
    {
        "id": "M7.3", "chapter": "7. Team och organisation",
        "question": "Teamet (nyckelpersonernas) sammansättning med avseende på könsfördelning samt fördelning av makt och inflytande mellan kvinnor och män inom genomförandet",
        "groups": [["könsfördelning", "kön"], ["makt", "inflytande", "mandat"]],
        "severity": "CRITICAL", "feeds": "G2",
    },
    {
        "id": "M7.4", "chapter": "7. Team och organisation",
        "question": "TABELL 4 (CV per nyckelperson): Namn, och kön | Titel, Organisation | Omfattning medv. (h) under hela projektet | Roll i projektet | Kompetens, erfarenhet relevant för projektet | Motiv till varför person är viktig för projektet",
        "computed": "table4",
        "severity": "CRITICAL", "feeds": "A1",
    },
]


# ============================================================
# THE THREE CRITERIA / SEVEN SUB-CRITERIA
# ============================================================
# Verbatim from Utlysningstext, "Vad bedömer vi?".
# Gender equality appears in TWO of the three main criteria (P3 and G2),
# which is why Potential and Genomförbarhet carry the heavier weights.

CRITERIA_WEIGHTS = {
    "potential": 0.40,
    "aktörer": 0.25,
    "genomförbarhet": 0.35,
}

SUBCRITERIA_META: list[dict] = [
    {"id": "P1", "criterion": "potential", "weight": 0.40,
     "name": "Nytänkande i relation till existerande processer och modeller i att "
             "öka kvalitet och kapacitet för verifiering och validering hos "
             "aktörer av kunskapsintensiva idéer"},
    {"id": "P2", "criterion": "potential", "weight": 0.35,
     "name": "Trovärdighet i analysen av problembilden och de resultat den "
             "föreslagna lösningen förväntas åstadkomma"},
    {"id": "P3", "criterion": "potential", "weight": 0.25,
     "name": "Bidrag till ökad jämställdhet genom att integrera perspektiv "
             "kring kön och genus"},
    {"id": "A1", "criterion": "aktörer", "weight": 0.45,
     "name": "Projektledarens och andra nyckelpersoners förutsättningar att "
             "leda och genomföra projektet"},
    {"id": "A2", "criterion": "aktörer", "weight": 0.55,
     "name": "Aktörskonstellationens sammansättning, deltagande, kompetens och "
             "förmåga att bidra till projektmål och genomförande"},
    {"id": "G1", "criterion": "genomförbarhet", "weight": 0.65,
     "name": "Förutsättningar för att projektets resultat tas vidare och kommer "
             "till användning efter projektets slut"},
    {"id": "G2", "criterion": "genomförbarhet", "weight": 0.35,
     "name": "Könsfördelning i projektteamet och perspektiv kring kön och genus "
             "integrerat i projektplanen"},
]


# ============================================================
# TEXT HELPERS
# ============================================================

_SWEDISH_MONTHS = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "mars": 3, "mar": 3,
    "april": 4, "apr": 4, "maj": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "augusti": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "december": 12,
    "dec": 12,
}

_NUMBER_WORDS = [
    "noll", "en", "ett", "två", "tre", "fyra", "fem", "sex", "sju", "åtta",
    "nio", "tio", "elva", "tolv",
]

# "tre månader" is a project duration exactly like "3 månader".
_NUMBER_WORD_VALUES = {
    "noll": 0, "en": 1, "ett": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5,
    "sex": 6, "sju": 7, "åtta": 8, "nio": 9, "tio": 10, "elva": 11,
    "tolv": 12,
}

# Labels that make a month figure a DURATION statement rather than an
# incidental number ("de senaste 24 månaderna" is not a project length).
_DURATION_LABELS = [
    "projekttid", "projektlängd", "projektperiod", "löptid", "löper",
    "genomförandetid", "projektet pågår", "pågår i", "pågår under",
    "projektet omfattar", "varaktighet", "under", "projekttiden",
]


def _month_value(token: str) -> Optional[int]:
    """'3' / '3,0' / 'tre' -> 3."""
    t = str(token).strip().lower()
    if t in _NUMBER_WORD_VALUES:
        return _NUMBER_WORD_VALUES[t]
    m = re.match(r"^(\d{1,2})", t)
    return int(m.group(1)) if m else None


def _months_between(a: date, b: date) -> int:
    """Whole calendar months from a to b, rounded up on a part month."""
    n = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day > a.day:
        n += 1
    return max(0, n)

_ROLE_STEMS = [
    "projektledare", "vd", "ceo", "cto", "professor", "docent", "forskare",
    "forskningsledare", "senior", "specialist", "expert", "ansvarig",
    "koordinator", "nyckelperson", "affärsutvecklare", "doktorand",
]


def _strip_table_rows(text: str) -> str:
    """Remove table rows and markdown separators.

    Terminology and stem counting must run on prose only — otherwise a
    filled-in budget table inflates the language scores.
    """
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.count("|") >= 2:
            continue
        if re.fullmatch(r"[\s|:+\-=_]*", stripped) and stripped:
            continue
        out.append(line)
    return "\n".join(out)


def _strip_instructions(text: str) -> str:
    """Remove leftover Projektbeskrivningsmall instruction text.

    The template says: "Ta bort alla instruktioner (kursiv text) ...".
    Markdown italics and the template's own phrasing are dropped so an
    unedited template does not score for questions it merely quotes.
    """
    out = []
    instruction_markers = (
        "beskriv hur ni avser", "kopiera tabellen nedan",
        "infoga ytterligare rader", "ta bort alla instruktioner",
        "ifylld mall får maximalt", "typsnitt med 11 punkters",
        "eventuella illustrationer ska vara",
    )
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if any(m in low for m in instruction_markers):
            continue
        # Whole-line markdown italics = instruction convention
        if len(s) > 4 and s.startswith("*") and s.endswith("*") and \
                not s.startswith("**"):
            continue
        out.append(line)
    return "\n".join(out)


def _body_text(full: str) -> str:
    """Prose only: no table rows, no template instructions."""
    return _strip_instructions(_strip_table_rows(full))


def _stem_count(body_lower: str, stem: str) -> int:
    return len(re.findall(re.escape(stem.lower()), body_lower))


def _has_any(body_lower: str, stems: list[str]) -> bool:
    return any(_stem_count(body_lower, s) > 0 for s in stems)


def _parse_sek(raw: str, unit: str = "") -> float:
    """Parse a Swedish money string into SEK."""
    s = re.sub(r"[\s    ]", "", str(raw))
    # Thousands separators as dots, decimal comma
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") >= 1 and re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        val = float(s)
    except ValueError:
        return 0.0
    u = unit.lower()
    if u in ("msek", "mkr", "miljoner kronor", "mnkr"):
        val *= 1_000_000
    elif u in ("tkr", "ksek", "tsek"):
        val *= 1_000
    return val


_MONEY_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[\s    \.]\d{3})+|\d+(?:[,\.]\d+)?)\s*"
    r"(?P<unit>msek|mkr|mnkr|tkr|ksek|tsek|sek|kronor|kr)\b",
    re.IGNORECASE,
)


def _find_amounts(text: str) -> list[tuple[float, int, str]]:
    """All money mentions as (value_sek, position, matched_text)."""
    out = []
    for m in _MONEY_RE.finditer(text):
        val = _parse_sek(m.group("num"), m.group("unit"))
        if val > 0:
            out.append((val, m.start(), m.group(0)))
    return out


def _amounts_near(text: str, stems: list[str], window: int = 90
                  ) -> list[tuple[float, str]]:
    """Money mentions whose surrounding window contains one of the stems."""
    low = text.lower()
    out = []
    for val, pos, raw in _find_amounts(text):
        ctx = low[max(0, pos - window):pos + len(raw) + window]
        if any(s in ctx for s in stems):
            out.append((val, ctx.strip()))
    return out


_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_SV_DATE_RE = re.compile(
    r"\b(\d{1,2})\s*(" + "|".join(sorted(_SWEDISH_MONTHS, key=len, reverse=True))
    + r")\.?\s*(20\d{2})\b", re.IGNORECASE)


def _find_dates(text: str) -> list[tuple[date, int, str]]:
    """Fully-specified dates only. Year-less dates are never returned —
    inferring a year would be a guess, and a guess must not trigger a FAIL."""
    out = []
    for m in _ISO_DATE_RE.finditer(text):
        try:
            out.append((date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
                        m.start(), m.group(0)))
        except ValueError:
            continue
    for m in _SV_DATE_RE.finditer(text):
        month = _SWEDISH_MONTHS.get(m.group(2).lower())
        if not month:
            continue
        try:
            out.append((date(int(m.group(3)), month, int(m.group(1))),
                        m.start(), m.group(0)))
        except ValueError:
            continue
    return out


_START_LABELS = ["projektstart", "startdatum", "startar", "påbörjas", "start"]
_END_LABELS = ["projektslut", "slutdatum", "avslutas", "avslutat", "avslut",
               "slutar", "slut", "färdigt", "klart"]


_DATE_RANGE_RE = re.compile(
    r"(20\d{2}-\d{1,2}-\d{1,2})\s*(?:–|—|--|-|till|t\.o\.m\.?|tom)\s*"
    r"(20\d{2}-\d{1,2}-\d{1,2})")

_PERIOD_CONTEXT = ("projekt", "löper", "löptid", "period", "genomförande",
                   "startar", "pågår")


def _iso(s: str) -> Optional[date]:
    m = re.fullmatch(r"(20\d{2})-(\d{1,2})-(\d{1,2})", s.strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _range_dates(text: str, window: int = 80
                 ) -> tuple[Optional[tuple[date, str]],
                            Optional[tuple[date, str]]]:
    """'Projektet löper 2026-10-26 – 2027-01-26' — a range IS start+end."""
    low = text.lower()
    for m in _DATE_RANGE_RE.finditer(text):
        ctx = low[max(0, m.start() - window):m.end() + 20]
        if not any(k in ctx for k in _PERIOD_CONTEXT):
            continue
        a, b = _iso(m.group(1)), _iso(m.group(2))
        if a and b and a <= b:
            return (a, m.group(0)), (b, m.group(0))
    return None, None


def _table_period_dates(periods: Optional[list]) -> list[date]:
    """Fully specified dates in TABELL 2's Tidsperiod column.

    Cells such as '2026-10-26 – 11-27' carry an end without a year. A
    year-less date is never classified — inferring one would be a guess.
    """
    out: list[date] = []
    for cell in periods or []:
        for m in re.finditer(r"20\d{2}-\d{1,2}-\d{1,2}", cell):
            d = _iso(m.group(0))
            if d:
                out.append(d)
    return out


def _classify_dates(text: str, window: int = 70, table_periods=None
                    ) -> tuple[Optional[tuple[date, str]],
                               Optional[tuple[date, str]]]:
    """Bind fully-specified dates to a start or end label.

    A date is classified by the NEAREST preceding label, not by any label
    anywhere in the window. "start <= 26 okt, slut <= 31 jan 2027" must
    bind 31 jan 2027 to `slut`, never to `start`.

    When no label binds, a project date RANGE in prose is used, and after
    that the fully specified dates in TABELL 2's Tidsperiod column.
    """
    low = text.lower()
    labels: list[tuple[int, str]] = []
    for stem in _START_LABELS:
        for m in re.finditer(re.escape(stem), low):
            labels.append((m.start(), "start"))
    for stem in _END_LABELS:
        for m in re.finditer(re.escape(stem), low):
            labels.append((m.start(), "end"))
    labels.sort()

    start = end = None
    for d, pos, raw in _find_dates(text):
        nearest = None
        for lpos, kind in labels:
            if lpos >= pos:
                break
            if pos - lpos <= window:
                nearest = (lpos, kind)
        if not nearest:
            continue
        ev = low[nearest[0]:pos + len(raw)].strip()
        if nearest[1] == "start" and start is None:
            start = (d, ev)
        elif nearest[1] == "end" and end is None:
            end = (d, ev)

    if start is None or end is None:
        rs, re_ = _range_dates(text)
        start = start or rs
        end = end or re_

    if start is None or end is None:
        tdates = sorted(_table_period_dates(table_periods))
        if tdates:
            ev = ("TABELL 2, kolumn Tidsperiod (endast datum med årtal; "
                  "datum utan årtal klassas aldrig)")
            if start is None:
                start = (tdates[0], ev)
            if end is None and len(tdates) > 1:
                end = (tdates[-1], ev)
    return start, end


_RULE_LANGUAGE = ("högst", "max", "maximalt", "får inte överstig",
                  "får uppgå till", "taket", "tak på", "begränsa",
                  "regeln", "enligt utlysning", "utlysningen")


def _declared_percentages(low: str, patterns: list[str]) -> list[float]:
    """Percentages the applicant declares as their OWN, not the rule quoted.

    "får uppgå till högst 20 procent" is the call restating its cap — it is
    not evidence that this budget sits at 20 %.

    The rule-language test looks at the text immediately IN FRONT of the
    figure, not at the whole surrounding window. "Indirekta 160 800 =
    30,00 % av lönekostnader 536 000 (max 30 %)" declares 30,00 % and
    quotes the cap in the same sentence — the declaration must survive.
    Decimals are kept: 18,78 % is 18.78, not 78.
    """
    out: list[float] = []
    for pat in patterns:
        for m in re.finditer(pat, low):
            before = low[max(0, m.start(1) - 45):m.start(1)]
            if any(r in before for r in _RULE_LANGUAGE):
                continue
            try:
                out.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                continue
    return out


# Percentage figure with an optional decimal part (18,78 / 30.0 / 45).
_PCT = r"(\d{1,3}(?:[,\.]\d+)?)\s*(?:%|procent)"


def _table_rows(text: str) -> list[list[str]]:
    """Pipe-delimited rows from markdown / docx / pdf table dumps."""
    rows = []
    for line in text.splitlines():
        if line.count("|") < 2:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(r"[\s:+\-=_]*", "".join(cells)):
            continue
        rows.append(cells)
    return rows


# ============================================================
# TABLE READING
# ============================================================
# The template puts the entire budget, the whole timeline, every hour and
# every gender marker inside four tables. Prose-only reading therefore
# makes the module blind to exactly the facts the formal requirements are
# about. Terminology and stem SCORING still runs on prose only (a filled
# table must not inflate language scores) — but the formal checks, the
# quantitative signals and the template questions read the tables.

# Space characters that turn up as thousands separators in docx/pdf dumps:
# NBSP, narrow NBSP, thin space, figure space.
_SPACE_CHARS = "    "


def _clean_cell(cell: str) -> str:
    """Cell text without bold/italic markers or exotic spaces."""
    s = str(cell).replace("**", "").replace("__", "")
    for ch in _SPACE_CHARS:
        s = s.replace(ch, " ")
    return s.strip().strip("*").strip()


def _cell_number(cell: str) -> Optional[float]:
    """A table cell as a number, or None if the cell is not purely numeric.

    Tolerates bold, unit suffixes (kr/SEK/h/timmar), and thousands
    separators written as space, NBSP, narrow NBSP or dot.
    """
    s = _clean_cell(cell)
    if not s:
        return None
    s = re.sub(r"(?i)\b(sek|kronor|kr|timmar|tim|h|st)\b\.?", "", s).strip()
    if not s or not re.fullmatch(r"-?\d[\d .,]*", s):
        return None
    t = s.replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    elif "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


@dataclass
class _Table:
    header: list[str]
    rows: list[list[str]]

    def text(self) -> str:
        out = [" | ".join(self.header)]
        out += [" | ".join(r) for r in self.rows]
        return "\n".join(out)


def _parse_tables(text: str) -> list["_Table"]:
    """Consecutive pipe-delimited lines grouped into tables.

    The first non-separator line of a block is the header row. A blank or
    non-pipe line closes the table.
    """
    tables: list[_Table] = []
    cur: list[list[str]] = []

    def flush():
        if len(cur) >= 2:
            tables.append(_Table(cur[0], cur[1:]))

    for line in text.splitlines():
        if line.count("|") >= 2:
            cells = [_clean_cell(c) for c in line.strip().strip("|").split("|")]
            if re.fullmatch(r"[\s:+\-=_]*", "".join(cells)):
                continue                      # markdown separator row
            cur.append(cells)
        else:
            flush()
            cur = []
    flush()
    return tables


def _col_index(header: list[str], *keys: str) -> Optional[int]:
    """First column whose heading contains one of the keys, keys in order."""
    low = [h.lower() for h in header]
    for key in keys:
        for i, h in enumerate(low):
            if key in h:
                return i
    return None


# A row label that says "this row is the total". Markdown emphasis and a
# trailing colon are stripped before matching, so '**Summa**', '*Summa*',
# 'Summa:', 'TOTALT', 'Totala' and 'S:a' all read as the same label.
_SUMMARY_LABEL_RE = re.compile(
    r"^(?:summa\w*|totalt?\w*|delsumma\w*|slutsumma\w*|s:a|σ)\b")


def _label_text(cell: str) -> str:
    """A cell as a bare label: no markdown emphasis, no trailing colon."""
    s = re.sub(r"[*_`~]", "", _clean_cell(cell))
    return s.strip().strip(":").strip().lower()


def _is_summary_row(row: list[str]) -> bool:
    return bool(_SUMMARY_LABEL_RE.match(_label_text(row[0]))) if row else False


# At least this many numeric columns must agree before an unlabelled
# trailing row is read as the table's own total.
_IMPLIED_SUMMARY_MIN_COLUMNS = 2


def _implied_summary_index(rows: list[list[str]],
                           cols: dict[str, Optional[int]]) -> Optional[int]:
    """Index of a totals row that carries no recognisable 'Summa' label.

    A trailing row whose numeric cells equal the column sums of every row
    above it IS the table's own total, whatever the first cell calls it.
    Reading it structurally is what keeps the totals from being added ON
    TOP of the data rows — the failure that reports a 499 960 kr grant as
    999 920 kr and rejects a correct application.

    Guarded hard, because a wrong hit here would swallow a real work
    package: at least two rows above it, at least two NON-ZERO columns
    that agree, and not one numeric column that disagrees.
    """
    if len(rows) < 3:
        return None
    cand = rows[-1]
    if not cand or re.match(r"ap\s*\d", _label_text(cand[0])):
        return None                       # an AP row is never the total
    above = rows[:-1]
    agree = 0
    for key, idx in cols.items():
        if key == "tidsperiod" or idx is None:
            continue
        vals = [v for v in (_cell_number(_cell(r, idx)) for r in above)
                if v is not None]
        cv = _cell_number(_cell(cand, idx))
        if cv is None or not vals:
            continue
        total = sum(vals)
        if abs(total - cv) > 1:
            return None                   # a column that disagrees ⇒ data row
        if total:
            agree += 1                    # 0 == 0 proves nothing
    return len(rows) - 1 if agree >= _IMPLIED_SUMMARY_MIN_COLUMNS else None


def _cell(row: list[str], idx: Optional[int]) -> str:
    if idx is None or row is None or idx >= len(row):
        return ""
    return _clean_cell(row[idx])


# TABELL 2's columns, verbatim from the Projektbeskrivningsmall.
_T2_COLUMNS: dict[str, tuple] = {
    "tidsperiod": ("tidsperiod", "period"),
    "personal": ("personal", "lönekostnad", "löner"),
    "hours": ("tid (h)", "tid(h)", "tid h", "timmar"),
    "konsult": ("konsult", "licens"),
    "utrustning": ("utrustning",),
    "ovriga": ("övriga direkta", "övriga"),
    "indirekta": ("indirekt", "overhead"),
    "egen": ("egen fin", "egen finansiering", "medfinansiering"),
    "bidrag": ("sökt bidrag", "bidrag"),
}

_COST_KEYS = ("personal", "konsult", "utrustning", "ovriga", "indirekta")


def _find_budget_table(tables: list["_Table"]) -> Optional["_Table"]:
    """TABELL 2, identified by its column signature — not by its caption."""
    for t in tables:
        h = " | ".join(t.header).lower()
        if "sökt bidrag" in h:
            return t
        if "indirekt" in h and ("personal" in h or "egen fin" in h):
            return t
    return None


def _budget_facts(tables: list["_Table"]) -> dict:
    """Everything TABELL 2 declares: totals per cost type, hours, periods.

    `totals` prefers the table's own Summa row; when there is none the
    data rows are summed. `row_sum` always holds the sum of the data rows
    so the two can be cross-checked. A summary row is NEVER also counted
    as a data row — that double count is what turns a correct budget into
    a formal rejection.

    `summary_kind` records how the total was obtained: "labelled" (the row
    says Summa/Totalt), "implied" (unlabelled row that equals the sum of
    the rows above it), or "" (no summary row — the data rows were summed).
    """
    t = _find_budget_table(tables)
    if t is None:
        return {"found": False}

    cols = {k: _col_index(t.header, *keys) for k, keys in _T2_COLUMNS.items()}

    labelled = [i for i, r in enumerate(t.rows) if _is_summary_row(r)]
    if labelled:
        s_idx: Optional[int] = labelled[0]
        summary_kind = "labelled"
    else:
        s_idx = _implied_summary_index(t.rows, cols)
        summary_kind = "implied" if s_idx is not None else ""
    summary = t.rows[s_idx] if s_idx is not None else None
    data = [r for i, r in enumerate(t.rows)
            if i != s_idx and not _is_summary_row(r)]

    totals: dict[str, Optional[float]] = {}
    row_sum: dict[str, Optional[float]] = {}
    for key in _T2_COLUMNS:
        if key == "tidsperiod":
            continue
        vals = []
        for r in data:
            v = _cell_number(_cell(r, cols.get(key)))
            if v is not None:
                vals.append(v)
        row_sum[key] = sum(vals) if vals else None
        sv = _cell_number(_cell(summary, cols.get(key))) if summary else None
        totals[key] = sv if sv is not None else row_sum[key]

    hours = []
    for r in data:
        v = _cell_number(_cell(r, cols.get("hours")))
        if v is not None:
            hours.append(v)

    periods = [_cell(r, cols.get("tidsperiod")) for r in data]
    periods = [p for p in periods if p]

    total_cost = None
    parts = [totals.get(k) for k in _COST_KEYS if totals.get(k) is not None]
    if parts:
        total_cost = sum(parts)
    if total_cost in (None, 0):
        e, b = totals.get("egen"), totals.get("bidrag")
        if e is not None or b is not None:
            total_cost = (e or 0) + (b or 0)

    return {
        "found": True,
        "has_summary_row": summary is not None,
        "summary_kind": summary_kind,
        "totals": totals,
        "row_sum": row_sum,
        "hours": hours,
        "hours_total": totals.get("hours"),
        "periods": periods,
        "total_cost": total_cost,
        "header": t.header,
    }


def _find_cv_table(tables: list["_Table"]) -> Optional["_Table"]:
    """TABELL 4 — identified by a column that names both person and sex."""
    for t in tables:
        low = [h.lower() for h in t.header]
        if any("kön" in h for h in low) and any("namn" in h for h in low):
            return t
    for t in tables:
        low = [h.lower() for h in t.header]
        if any("kön" in h for h in low):
            return t
    return None


_PLACEHOLDER_RE = re.compile(r"[【\[][^】\]]{0,40}[】\]]")
_GENDER_TAIL_RE = re.compile(
    r"(?:^|[,;:/()\s])(kvinnor|kvinna|kvinnlig|kvinnligt|man|män|manlig|manligt|k|m)"
    r"\s*[)\.]?\s*$", re.IGNORECASE)


def _cv_gender_facts(tables: list["_Table"]) -> dict:
    """Count gender markers in TABELL 4's 'Namn och kön' column.

    A bracketed placeholder name still counts as gender-marked when the
    sex word is there — but it is reported separately as 'ej namngiven',
    because a marker on a person who does not exist yet is a plan, not a
    team.
    """
    t = _find_cv_table(tables)
    if t is None:
        return {"found": False, "K": 0, "M": 0, "placeholder": 0,
                "people": 0, "unmarked": 0}
    idx = _col_index(t.header, "kön", "namn")
    k = m = placeholder = unmarked = people = 0
    for row in t.rows:
        if _is_summary_row(row):
            continue
        cell = _cell(row, idx)
        if not cell:
            continue
        people += 1
        gm = _GENDER_TAIL_RE.search(cell)
        word = gm.group(1).lower() if gm else ""
        if word in ("kvinna", "kvinnor", "kvinnlig", "kvinnligt", "k"):
            k += 1
        elif word in ("man", "män", "manlig", "manligt", "m"):
            m += 1
        else:
            unmarked += 1
            continue
        name_part = cell[:gm.start(1)] if gm else cell
        if _PLACEHOLDER_RE.search(name_part) or not re.search(r"[A-Za-zÅÄÖåäö]{2}",
                                                             _PLACEHOLDER_RE.sub("", name_part)):
            placeholder += 1
    return {"found": True, "K": k, "M": m, "placeholder": placeholder,
            "people": people, "unmarked": unmarked}


_BASELINE_HEADERS = ("nuläge", "nuvarande", "baslinje", "i dag", "idag",
                     "utgångsläge", "as-is", "as is", "dagens", "före")
_TARGET_HEADERS = ("målvärde", "målnivå", "efter", "to-be", "to be", "target",
                   "med modellen", "önskat")


def _table_before_after_pairs(tables: list["_Table"]) -> tuple[int, list[str]]:
    """Before/after pairs expressed as a table instead of as prose.

    A table with both a baseline column and a target column IS a set of
    before/after pairs — one per row where both cells are filled.
    """
    total, notes = 0, []
    for t in tables:
        low = [h.lower() for h in t.header]
        b_idx = t_idx = None
        for i, h in enumerate(low):
            if b_idx is None and any(k in h for k in _BASELINE_HEADERS):
                b_idx = i
            elif t_idx is None and h.startswith("mål") and "målgrupp" not in h:
                t_idx = i
            elif t_idx is None and any(k in h for k in _TARGET_HEADERS):
                t_idx = i
        if b_idx is None or t_idx is None or b_idx == t_idx:
            continue
        n = 0
        for row in t.rows:
            if _is_summary_row(row):
                continue
            if _cell(row, b_idx) and _cell(row, t_idx):
                n += 1
        if n:
            total += n
            notes.append(f"{n} rader i tabell '{t.header[b_idx]}' → "
                         f"'{t.header[t_idx]}'")
    return total, notes


# ============================================================
# ANALYSIS CONTEXT
# ============================================================

def _build_context(model: "ProposalModel") -> dict:
    """Everything the checks and the scorer need, computed once."""
    full = model.full_text or ""
    body = _body_text(full)
    body_lower = body.lower()
    full_lower = full.lower()
    rows = _table_rows(full)
    parsed = _parse_tables(full)
    table_text = "\n".join(t.text() for t in parsed)

    ctx: dict = {
        "full": full,
        "full_lower": full_lower,
        "body": body,
        "body_lower": body_lower,
        "rows": rows,
        "parsed_tables": parsed,
        "table_text": table_text,
        # Prose PLUS table content. Used by the template questions and the
        # formal checks — a question answered inside a mandated table is
        # answered. Scoring stem-counts keep using body_lower only.
        "mall_lower": body_lower + "\n" + table_text.lower(),
        "model": model,
    }

    ctx["budget"] = _budget_facts(parsed)
    ctx["cv_gender"] = _cv_gender_facts(parsed)

    # --- Table detection (signature-based, per Projektbeskrivningsmall) ---
    def row_text(r):
        return " | ".join(r).lower()

    t1 = t2 = t3 = 0
    t3_scored = 0
    for r in rows:
        rt = row_text(r)
        # TABELL 1: AP | beskrivning av aktivitet | kostnad
        if re.search(r"\bap\s*\d", rt) and len(r) >= 3:
            t1 += 1
        # TABELL 2: has the cost-type columns
        if ("indirekta" in rt and ("sökt bidrag" in rt or "egen finansiering" in rt)) \
                or ("personal" in rt and "konsultkostnader" in rt):
            t2 += 1
        if re.search(r"\bap\s*\d", rt) and len(r) >= 8:
            t2 += 1
        # TABELL 3: risk row with two integers 1-5
        nums = [c.strip() for c in r if re.fullmatch(r"[1-5]", c.strip())]
        if len(nums) >= 2 and len(r) >= 3:
            t3 += 1
            t3_scored += 1
        if "sannolikhet" in rt and "konsekvens" in rt:
            t3 += 1

    # TABELL 4: CV blocks — the label set from the template
    t4_labels = ["namn", "titel", "omfattning", "roll i projektet", "kompetens",
                 "motiv"]
    t4_hits = sum(1 for lab in t4_labels
                  if any(lab in row_text(r) for r in rows))
    # docx/pdf CV tables often come out as label/value line pairs
    if t4_hits < 4:
        t4_hits = sum(1 for lab in t4_labels
                      if re.search(r"(?m)^\s*" + re.escape(lab), full_lower))

    ctx["tables"] = {
        "table1": t1 >= 2,
        "table2": t2 >= 2,
        "table3": t3 >= 2,
        "table4": t4_hits >= 4,
        "table1_rows": t1,
        "table2_rows": t2,
        "table3_scored_rows": t3_scored,
        "table4_labels": t4_hits,
    }

    # --- Terminology coverage (the call's own vocabulary) ---
    present = [t for t in CALL_TERMS if _stem_count(body_lower, t) > 0]
    ctx["terminology"] = {
        "present": present,
        "missing": [t for t in CALL_TERMS if t not in present],
        "coverage": round(len(present) / len(CALL_TERMS), 3),
    }

    # --- Quantification signals ---
    numbers = re.findall(r"(?<![\w-])\d{1,3}(?:[  ]\d{3})*(?:[,\.]\d+)?\s*"
                         r"(?:%|procent|st\b|timmar|tim\b|dagar|månader|veckor|"
                         r"kr\b|sek\b|kronor|idéer|företag|personer|aktörer)",
                         body_lower)
    ctx["quantified_units"] = len(numbers)

    nw = "|".join(_NUMBER_WORDS)
    beforeafter = re.findall(
        r"från\s+[^.\n]{0,40}?(?:\d|" + nw + r")[^.\n]{0,40}?\btill\s+"
        r"[^.\n]{0,40}?(?:\d|" + nw + r")", body_lower)
    table_pairs, pair_notes = _table_before_after_pairs(parsed)
    ctx["before_after_prose"] = len(beforeafter)
    ctx["before_after_table"] = table_pairs
    ctx["before_after_notes"] = pair_notes
    ctx["before_after_pairs"] = len(beforeafter) + table_pairs

    ctx["quantified_outcome"] = (
        _has_any(ctx["mall_lower"], ["kvantifier"]) or
        (ctx["quantified_units"] >= 5 and ctx["before_after_pairs"] >= 1)
    )

    # --- Hours (TABELL 2 'Tid (h)' + TABELL 4 'Omf. (h)' + prose) ---
    prose_hours = re.findall(r"\d{1,4}\s*(?:h\b|timmar|tim\b)", body_lower)
    t2_hours = list(ctx["budget"].get("hours") or [])
    t4_hours: list[float] = []
    cv_tbl = _find_cv_table(parsed)
    if cv_tbl is not None:
        h_idx = _col_index(cv_tbl.header, "omf", "omfattning", "(h)", "timmar")
        if h_idx is not None:
            for r in cv_tbl.rows:
                if _is_summary_row(r):
                    continue
                v = _cell_number(_cell(r, h_idx))
                if v is not None:
                    t4_hours.append(v)
    ctx["hours"] = {
        "table2": t2_hours,
        "table2_total": ctx["budget"].get("hours_total"),
        "table4": t4_hours,
        "prose": len(prose_hours),
        "count": len(t2_hours) + len(t4_hours) + len(prose_hours),
    }

    # --- People and gender ---
    name_re = r"[A-ZÅÄÖ][a-zåäöé]+(?:\s+[A-ZÅÄÖ][a-zåäöé]+){1,2}"
    named = set()
    for m in re.finditer(name_re, full):
        window = full_lower[max(0, m.start() - 60):m.end() + 60]
        if any(r in window for r in _ROLE_STEMS):
            named.add(m.group(0))
    ctx["named_people"] = sorted(named)

    # Gender markers: TABELL 4's 'Namn och kön' column first, then the
    # older loose K/M cell convention as a fallback.
    cvg = ctx["cv_gender"]
    k_cells, m_cells = cvg["K"], cvg["M"]
    if k_cells + m_cells == 0:
        for r in rows:
            rt = row_text(r)
            if "kön" in rt or "namn" in rt:
                for c in r:
                    cs = c.strip()
                    if re.fullmatch(r"[Kk]|kvinna|Kvinna", cs):
                        k_cells += 1
                    elif re.fullmatch(r"[Mm]|man|Man", cs):
                        m_cells += 1
                    else:
                        # Mallens CV-tabell ar LODRAT: raden ar
                        # "Namn, och kon | Anna Andersson, kvinna". Cellen ar
                        # alltsa hela varden, inte bara konsordet. Utan det har
                        # gav en korrekt konsmarkt ansokan 0 av 4 pa jamstalldhet.
                        if re.search(r",\s*(kvinna|k)\s*$", cs, re.I):
                            k_cells += 1
                        elif re.search(r",\s*(man|m)\s*$", cs, re.I):
                            m_cells += 1
    ctx["gender_cells"] = {
        "K": k_cells, "M": m_cells,
        "placeholder": cvg["placeholder"],
        "people": cvg["people"],
        "unmarked": cvg["unmarked"],
    }

    gender_stat = re.search(
        r"(\d+)\s*(?:kvinnor|kvinna)[^.\n]{0,30}?(\d+)\s*(?:män|man)\b",
        body_lower)
    ctx["gender_statement"] = bool(gender_stat)

    ctx["gender_stems"] = {
        s: _stem_count(body_lower, s)
        for s in ["jämställ", "kvinn", "genus", "könsfördelning", "kön",
                  "makt", "inflytande", "idébärare", "idéägare"]
    }

    ctx["transfer_stems"] = {
        s: _stem_count(body_lower, s)
        for s in ["överför", "generalis", "implementer", "förvalt", "skala",
                  "sprid", "ta vidare", "efter projektslut", "nästa steg",
                  "återanvänd", "mottagare", "licens"]
    }

    # --- Parties / actors ---
    ctx["eligible_actor_types"] = [s for s in ELIGIBLE_ACTOR_STEMS
                                   if _stem_count(body_lower, s) > 0]
    ctx["party_mentions"] = len(set(re.findall(
        r"\b[A-ZÅÄÖ][A-Za-zÅÄÖåäö&\.\- ]{2,40}?(?:AB|AS|ApS|Institute|Institutet|"
        r"Universitet|Högskolan|Science Park|Innovation)\b", full)))

    # Evidence attribution. crucible's citations_found is calibrated for
    # Horizon-style "(Author, 2024)" and misses Swedish narrative sourcing,
    # so year-in-parenthesis refs and explicit attribution verbs count too.
    ctx["citations"] = (len(model.citations_found or []) +
                        len(re.findall(r"\((?:19|20)\d{2}\)", full)))
    ctx["attributions"] = sum(
        _stem_count(body_lower, s) for s in
        ["enligt ", "referens", "källa", "studie", "forskning visar",
         "rapport", "publicerad", "bygger på arbete", "härrör från"])

    # --- Mall question answers ---
    answered, missing = [], []
    for q in MALL_QUESTIONS:
        if _mall_answered(q, ctx):
            answered.append(q["id"])
        else:
            missing.append(q)
    ctx["mall_answered"] = answered
    ctx["mall_missing"] = missing

    # --- Formal checks ---
    ctx["formal"] = _formal_checks(model, ctx)
    return ctx


def _computed_marker(key: str, ctx: dict) -> bool:
    """Structural evidence a stem group may be satisfied by instead of a word."""
    if key == "table3_scored":
        return ctx["tables"].get("table3_scored_rows", 0) > 0
    if key in ctx["tables"]:
        return bool(ctx["tables"][key])
    return bool(ctx.get(key, False))


def _group_satisfied(group: list[str], ctx: dict) -> bool:
    """A group is satisfied by ANY of its stems, or by a '@marker'."""
    hay = ctx.get("mall_lower") or ctx["body_lower"]
    for stem in group:
        if stem.startswith("@"):
            if _computed_marker(stem[1:], ctx):
                return True
        elif _stem_count(hay, stem) > 0:
            return True
    return False


def _mall_answered(q: dict, ctx: dict) -> bool:
    if "computed" in q:
        key = q["computed"]
        if key in ctx["tables"]:
            return bool(ctx["tables"][key])
        return bool(ctx.get(key, False))
    return all(_group_satisfied(group, ctx) for group in q.get("groups", []))


def _missing_groups(q: dict, ctx: dict) -> list[str]:
    if "computed" in q:
        return [q["computed"]]
    return ["/".join(g) for g in q.get("groups", [])
            if not _group_satisfied(g, ctx)]


# ============================================================
# FORMAL REQUIREMENTS — breach = direct rejection
# ============================================================
# Status vocabulary:
#   FAIL    — positive evidence the requirement is breached  → composite 0
#   PASS    — positive evidence the requirement is met
#   WARN    — evidence of risk, not yet a breach
#   UNKNOWN — the document says nothing; cannot be verified from this text
#
# UNKNOWN is never upgraded to FAIL. A guess must not reject an application.

def _fc(fid, label, requirement, status, detail, evidence=""):
    return {"id": fid, "label": label, "requirement": requirement,
            "status": status, "detail": detail, "evidence": evidence[:200]}


def _kr(v: float) -> str:
    return f"{v:,.0f} kr".replace(",", " ")


# --- F1 helpers: only amounts ANCHORED to sökt bidrag may reject ---------
#
# The old rule took the largest money figure anywhere near the word
# "bidrag" or "budget". A paragraph about what a later implementation
# phase would cost then rejected the application. An amount now counts
# only if it is bound to the applied-for grant.

_GRANT_ANCHOR_STEMS = [
    "sökt bidrag", "söker bidrag", "söka bidrag", "sökt belopp",
    "ansöker om", "ansökt om", "vi söker", "söker vi", "söker om",
    "bidrag från vinnova", "bidrag av vinnova", "bidragsbelopp",
    "begärt bidrag", "yrkat bidrag",
]

# Amounts inside a sentence about a LATER phase are not the applied-for
# grant, however large they are.
_FUTURE_PHASE_STEMS = [
    "implementer", "pilot", "efter projektslut", "efter projektets slut",
    "efter förstudien", "efter avslutat projekt", "framtid", "nästa fas",
    "nästa steg", "uppskatt", "bedömer vi behovet", "vidareutveckling",
    "per år", "per miljö", "skalning", "på sikt", "fortsättning",
    "kommande", "senare skede", "steg 2", "fas 2",
]

# Text immediately in front of a number that makes it a rule, not a claim.
_CAP_LANGUAGE = ["≤", "<=", "högst", "max", "tak", "upp till", "överstig",
                 "får inte", "får uppgå", "begränsa"]

_GROUPED_AMOUNT_RE = re.compile(
    r"\d{1,3}(?:[     ]\d{3})+")


def _sentences(text: str) -> list[tuple[str, int]]:
    """(sentence, offset) — split on sentence enders and line breaks."""
    out, start = [], 0
    for m in re.finditer(r"[.!?\n]", text):
        seg = text[start:m.start()]
        if seg.strip():
            out.append((seg, start))
        start = m.end()
    if text[start:].strip():
        out.append((text[start:], start))
    return out


def _sentence_at(text: str, pos: int) -> str:
    """The sentence containing `pos`. Sentence enders and line breaks bound it."""
    start = max(text.rfind(ch, 0, pos) for ch in ".!?\n")
    ends = [i for i in (text.find(ch, pos) for ch in ".!?\n") if i >= 0]
    return text[start + 1:min(ends) if ends else len(text)]


def _anchored_grant_amounts(full: str) -> list[tuple[float, str]]:
    """Money figures bound to 'sökt bidrag' and not to a later phase."""
    out: list[tuple[float, str]] = []
    for sent, _ in _sentences(full):
        low = sent.lower()
        anchor = min((low.find(s) for s in _GRANT_ANCHOR_STEMS
                      if low.find(s) >= 0), default=-1)
        if anchor < 0:
            continue
        if any(s in low for s in _FUTURE_PHASE_STEMS):
            continue
        cands: list[tuple[int, float]] = []
        for m in _MONEY_RE.finditer(sent):
            v = _parse_sek(m.group("num"), m.group("unit"))
            if v > 0:
                cands.append((m.start(), v))
        for m in _GROUPED_AMOUNT_RE.finditer(sent):
            v = _parse_sek(m.group(0))
            if v > 0 and not any(abs(p - m.start()) < 3 for p, _ in cands):
                cands.append((m.start(), v))
        for pos, val in cands:
            if pos < anchor:
                continue
            before = low[max(0, pos - 30):pos]
            if any(c in before for c in _CAP_LANGUAGE):
                continue
            out.append((val, sent.strip()))
    return out


# --- F10 helpers: a rule quoted is not a transaction performed -----------
#
# Words that COULD describe money moving between organisations.
_F10_BUY_RE = re.compile(
    r"(fakturer\w*|köper\w*|köp mellan|köp av (?:varor|tjänster)|"
    r"betalar|ersätter|ersättning till|arvoder\w*)", re.I)

# If any of these sits in the same SENTENCE as the hit, the sentence is
# stating the rule, or stating that the transaction does not happen. Either
# way it is not evidence of a purchase between project parties.
_F10_NOT_A_TRANSACTION = [
    # negations
    "inte", "ingen", "inga", "icke", "aldrig", "ej ",
    "utan ersättning", "utan kostnad", "utan att",
    # rule language
    "inte stödberättigande", "ej stödberättigande", "får inte",
    "anvisning", "regel", "utanför partskretsen", "extern aktör",
    "extern leverantör", "ej projektpart", "inte projektpart",
    "marknadsmässiga villkor", "upphandling",
]


def _formal_checks(model: "ProposalModel", ctx: dict) -> list[dict]:
    full = ctx["full"]
    low = ctx["full_lower"]
    checks: list[dict] = []

    # --- F1: max 500 000 kr i bidrag ---
    # Only an amount ANCHORED to sökt bidrag counts. TABELL 2's Summa row
    # under the column "Sökt bidrag" is the primary source; text anchored
    # to sökt bidrag/ansöker om is the fallback. No anchored amount →
    # UNKNOWN, never FAIL: a guess must not reject an application.
    budget = ctx["budget"]
    prose_grants = _anchored_grant_amounts(full)
    declared: Optional[float] = None
    source = ""
    evidence = ""
    notes: list[str] = []

    table_grant = budget.get("totals", {}).get("bidrag") if budget.get("found") else None
    if table_grant is not None:
        declared = table_grant
        b_col = _col_index(budget["header"], "sökt bidrag", "bidrag")
        colname = (budget["header"][b_col] if b_col is not None
                   else "Sökt bidrag")
        kind = budget.get("summary_kind")
        if kind == "labelled":
            source = f"TABELL 2, summarad, kolumn '{colname}'"
        elif kind == "implied":
            source = (f"TABELL 2, summarad utan etikett — raden är summan av "
                      f"AP-raderna, kolumn '{colname}'")
        else:
            source = (f"TABELL 2, summa av AP-raderna (ingen summarad), "
                      f"kolumn '{colname}'")
        rs = budget.get("row_sum", {}).get("bidrag")
        if kind and rs is not None and abs(rs - declared) > 1:
            notes.append(f"OBS: summaraden ({_kr(declared)}) stämmer inte med "
                         f"summan av AP-raderna ({_kr(rs)}).")
        elif kind and rs is not None:
            notes.append(f"Summaraden stämmer med AP-raderna ({_kr(rs)}).")
        if prose_grants:
            pv = max(v for v, _ in prose_grants)
            if abs(pv - declared) > 1:
                notes.append(f"Löptexten anger {_kr(pv)} som sökt bidrag — "
                             "tabellen och löptexten är inte samstämmiga.")
            else:
                notes.append(f"Löptexten anger {_kr(pv)} — samstämmigt med "
                             "tabellen.")
            evidence = prose_grants[0][1]
        else:
            notes.append("Löptexten anger inget belopp som är ankrat till "
                         "sökt bidrag.")
    elif prose_grants:
        declared = max(v for v, _ in prose_grants)
        source = "löptext, ankrad till sökt bidrag"
        evidence = next(e for v, e in prose_grants if v == declared)

    if declared is not None and declared > MAX_GRANT_SEK:
        checks.append(_fc(
            "F1", "Bidragstak 500 000 kr",
            "Projektet får ansöka om max 500 000 kronor.", "FAIL",
            f"Sökt bidrag {_kr(declared)} överskrider taket "
            f"{_kr(MAX_GRANT_SEK)} (källa: {source}). " + " ".join(notes),
            evidence))
    elif declared is not None:
        checks.append(_fc(
            "F1", "Bidragstak 500 000 kr",
            "Projektet får ansöka om max 500 000 kronor.", "PASS",
            f"Sökt bidrag {_kr(declared)} ≤ taket {_kr(MAX_GRANT_SEK)} "
            f"(källa: {source}). " + " ".join(notes),
            evidence))
    else:
        checks.append(_fc(
            "F1", "Bidragstak 500 000 kr",
            "Projektet får ansöka om max 500 000 kronor.", "UNKNOWN",
            "Inget belopp som är ankrat till sökt bidrag går att läsa ut — "
            "varken ur TABELL 2:s kolumn 'Sökt bidrag' eller ur löptext. "
            "Belopp som rör senare faser, implementering eller pilot räknas "
            "inte som sökt bidrag och kan därför aldrig utlösa avslag här."))

    # --- F3 first: the dates also give F2 its computed duration ---
    start, end = _classify_dates(full, table_periods=ctx["budget"].get("periods"))

    # --- F2: projekttid max 3 månader ---
    # Duration may be written as a digit ("3 månader"), as a Swedish number
    # word ("tre månader") or only as a date range in TABELL 2 / prose.
    nwords = "|".join(sorted(_NUMBER_WORD_VALUES, key=len, reverse=True))
    month_re = (r"(\d{1,2}(?:[,\.]\d+)?|" + nwords +
                r")\s*(?:månader|månads|månad\b|mån\b)")
    months = []
    for m in re.finditer(month_re, low):
        window = low[max(0, m.start() - 90):m.end() + 90]
        near = low[max(0, m.start() - 60):m.start()]
        strong = any(s in near for s in _DURATION_LABELS)
        if not (strong or "projekt" in window or "löptid" in window
                or "genomförandetid" in window):
            continue
        # An amount/period belonging to a later phase is not the project time.
        if not strong and any(s in window for s in _FUTURE_PHASE_STEMS):
            continue
        val = _month_value(m.group(1))
        if val is not None:
            months.append((val, window.strip()))
    declared_months = max((v for v, _ in months), default=0)

    computed_months = None
    if start and end:
        computed_months = _months_between(start[0], end[0])

    if declared_months > MAX_DURATION_MONTHS:
        checks.append(_fc(
            "F2", "Projekttid max 3 månader",
            "Projekttiden får vara högst tre månader.", "FAIL",
            f"Angiven projekttid: {declared_months} månader.",
            months[0][1] if months else ""))
    elif declared_months > 0:
        extra = (f" Beräknat ur datumintervallet {start[0].isoformat()} – "
                 f"{end[0].isoformat()}: {computed_months} månader."
                 if computed_months is not None else "")
        checks.append(_fc(
            "F2", "Projekttid max 3 månader",
            "Projekttiden får vara högst tre månader.", "PASS",
            f"Angiven projekttid: {declared_months} månader." + extra))
    elif computed_months is not None:
        checks.append(_fc(
            "F2", "Projekttid max 3 månader",
            "Projekttiden får vara högst tre månader.",
            "PASS" if computed_months <= MAX_DURATION_MONTHS else "WARN",
            f"Ingen projekttid i månader skriven i klartext. Beräknad ur "
            f"{start[0].isoformat()} – {end[0].isoformat()}: "
            f"{computed_months} månader. Skriv ut månadsantalet explicit."))
    else:
        checks.append(_fc(
            "F2", "Projekttid max 3 månader",
            "Projekttiden får vara högst tre månader.", "UNKNOWN",
            "Ingen projekttid i månader angiven i anslutning till 'projekt', "
            "och inget fullständigt datumintervall att räkna ur."))

    # --- F3: start/slut inom fönstret ---
    date_msgs, date_status = [], "UNKNOWN"
    if start:
        d, ev = start
        if d > LATEST_START:
            date_status = "FAIL"
            date_msgs.append(f"Startdatum {d.isoformat()} är efter "
                             f"{LATEST_START.isoformat()}.")
        elif d < EARLIEST_START:
            date_status = "FAIL"
            date_msgs.append(f"Startdatum {d.isoformat()} är före "
                             f"{EARLIEST_START.isoformat()} (projekt får ej starta).")
        else:
            date_msgs.append(f"Startdatum {d.isoformat()} inom fönstret.")
    if end:
        d, ev = end
        if d > LATEST_END:
            date_status = "FAIL"
            date_msgs.append(f"Slutdatum {d.isoformat()} är efter "
                             f"{LATEST_END.isoformat()}.")
        else:
            date_msgs.append(f"Slutdatum {d.isoformat()} inom fönstret.")
    # Any fully specified date in TABELL 2's Tidsperiod column that falls
    # outside the window is positive evidence of a breach, whichever end
    # of a work package it belongs to.
    for d in _table_period_dates(ctx["budget"].get("periods")):
        if d < EARLIEST_START or d > LATEST_END:
            date_status = "FAIL"
            date_msgs.append(
                f"TABELL 2 innehåller datumet {d.isoformat()} som ligger "
                f"utanför fönstret {EARLIEST_START.isoformat()} – "
                f"{LATEST_END.isoformat()}.")
            break
    if date_status != "FAIL":
        date_status = "PASS" if (start and end) else (
            "WARN" if (start or end) else "UNKNOWN")
    if not start:
        date_msgs.append("Inget fullständigt startdatum (med årtal) angivet.")
    if not end:
        date_msgs.append("Inget fullständigt slutdatum (med årtal) angivet.")
    checks.append(_fc(
        "F3", "Projektfönster 2026-10-20 .. 2027-01-31",
        "Projektet måste starta senast 26 oktober 2026 och avslutas senast "
        "31 januari 2027. Projekt får starta tidigast 20 oktober 2026.",
        date_status, " ".join(date_msgs),
        (start[1] if start else "") + " " + (end[1] if end else "")))

    # --- F4: konsult- och licenskostnader max 20 % av en organisations budget ---
    # Percentages come from three places, in order of authority: what the
    # applicant declares per organisation, what TABELL 2's Summa row gives
    # when the ratio is computed, and finally loose amounts in prose.
    F4_REQ = ("Kostnader för konsulttjänster och licenser får uppgå till högst "
              "20 procent av en organisations budget.")
    F4_LBL = "Konsult/licens max 20 % av en organisations budget"
    pct_claims = _declared_percentages(low, [
        r"(?:konsult|licens)[^.\n]{0,80}?" + _PCT,
        _PCT + r"[^.\n]{0,80}?(?:konsultkostnad|licenskostnad)",
    ])
    consult_amounts = _amounts_near(full, ["konsult", "licens"])
    tol = 0.0005                                    # 0,05 pp rounding slack
    t_consult = budget.get("totals", {}).get("konsult") if budget.get("found") else None
    t_total = budget.get("total_cost") if budget.get("found") else None
    table_share = (t_consult / t_total) if (t_consult and t_total) else None

    if any(p > MAX_CONSULT_LICENSE_SHARE * 100 + 0.05 for p in pct_claims):
        worst = max(p for p in pct_claims
                    if p > MAX_CONSULT_LICENSE_SHARE * 100 + 0.05)
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "FAIL",
            f"Angiven andel konsult-/licenskostnader: {worst:g} %."))
    elif table_share is not None and table_share > MAX_CONSULT_LICENSE_SHARE + tol:
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "FAIL",
            f"TABELL 2: konsult/licens {_kr(t_consult)} av total "
            f"projektkostnad {_kr(t_total)} = {table_share*100:.2f} %. "
            "Överskrider aggregatet 20 % måste minst en organisation ligga "
            "över taket."))
    elif pct_claims:
        extra = (f" TABELL 2 ger {_kr(t_consult)} av {_kr(t_total)} = "
                 f"{table_share*100:.2f} % av projektets totala kostnad."
                 if table_share is not None else "")
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "PASS",
            f"Angiven andel per organisation: {max(pct_claims):g} %." + extra))
    elif table_share is not None:
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "WARN",
            f"TABELL 2: konsult/licens {_kr(t_consult)} av total "
            f"projektkostnad {_kr(t_total)} = {table_share*100:.2f} %, alltså "
            "under taket i aggregat. Ingen andel PER ORGANISATION redovisas — "
            "taket räknas per organisations totala projektkostnad."))
    elif consult_amounts:
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "WARN",
            f"{len(consult_amounts)} konsult-/licensbelopp hittade men ingen "
            "andel per organisation redovisad. Taket räknas per organisations "
            "TOTALA projektkostnad, inte per bidrag.",
            consult_amounts[0][1]))
    else:
        checks.append(_fc(
            "F4", F4_LBL, F4_REQ, "UNKNOWN",
            "Inga konsult- eller licenskostnader identifierade — varken i "
            "TABELL 2 eller i löptext."))

    # --- F5: indirekta kostnader max 30 % av lönekostnader ---
    F5_REQ = ("Indirekta kostnader får uppgå till högst 30 procent av "
              "lönekostnaderna.")
    F5_LBL = "Indirekta kostnader max 30 % av lönekostnader"
    ind_pct = _declared_percentages(low, [
        r"indirekt[^.\n]{0,80}?" + _PCT,
        _PCT + r"[^.\n]{0,60}?(?:indirekt|overhead|påslag)",
    ])
    ind_amounts = _amounts_near(full, ["indirekt", "overhead"])
    sal_amounts = _amounts_near(full, ["lönekostnad", "löner", "personalkostnad",
                                       "personal"])
    t_ind = budget.get("totals", {}).get("indirekta") if budget.get("found") else None
    t_sal = budget.get("totals", {}).get("personal") if budget.get("found") else None
    ind_share = (t_ind / t_sal) if (t_ind and t_sal) else None

    if any(p > MAX_INDIRECT_SHARE_OF_SALARY * 100 + 0.05 for p in ind_pct):
        worst = max(p for p in ind_pct
                    if p > MAX_INDIRECT_SHARE_OF_SALARY * 100 + 0.05)
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "FAIL",
            f"Angivet påslag för indirekta kostnader: {worst:g} %."))
    elif ind_share is not None and ind_share > MAX_INDIRECT_SHARE_OF_SALARY + tol:
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "FAIL",
            f"TABELL 2: indirekta {_kr(t_ind)} mot lönekostnader "
            f"{_kr(t_sal)} = {ind_share*100:.2f} %."))
    elif ind_share is not None:
        extra = f" Angivet påslag i löptext: {max(ind_pct):g} %." if ind_pct else ""
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "PASS",
            f"TABELL 2: indirekta {_kr(t_ind)} mot lönekostnader "
            f"{_kr(t_sal)} = {ind_share*100:.2f} %." + extra))
    elif ind_pct:
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "PASS",
            f"Angivet påslag: {max(ind_pct):g} %."))
    elif ind_amounts and sal_amounts and \
            max(v for v, _ in ind_amounts) > \
            MAX_INDIRECT_SHARE_OF_SALARY * max(v for v, _ in sal_amounts):
        ind = max(v for v, _ in ind_amounts)
        sal = max(v for v, _ in sal_amounts)
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "FAIL",
            f"Indirekta {_kr(ind)} mot lönekostnader {_kr(sal)} = "
            f"{ind/sal*100:.0f} %."))
    else:
        checks.append(_fc(
            "F5", F5_LBL, F5_REQ, "UNKNOWN",
            "Inga indirekta kostnader redovisade — varken i TABELL 2 eller "
            "i löptext."))

    # --- F6: projektledaren anställd hos koordinerande part ---
    pl_m = re.search(r"projektledare[^\n]{0,160}", low)
    coord_m = re.search(r"(?:koordinator|koordinerande part)[^\n]{0,120}", low)
    if not pl_m:
        checks.append(_fc(
            "F6", "Projektledare anställd hos koordinerande part",
            "Att projektledaren är anställd hos den koordinerande parten i "
            "projektet.", "UNKNOWN",
            "Ingen projektledare namngiven i dokumentet."))
    elif coord_m:
        checks.append(_fc(
            "F6", "Projektledare anställd hos koordinerande part",
            "Att projektledaren är anställd hos den koordinerande parten i "
            "projektet.", "WARN",
            "Projektledare och koordinator nämns båda, men anställningen hos "
            "koordinerande part är inte uttryckligen intygad i texten.",
            pl_m.group(0)))
    else:
        checks.append(_fc(
            "F6", "Projektledare anställd hos koordinerande part",
            "Att projektledaren är anställd hos den koordinerande parten i "
            "projektet.", "WARN",
            "Projektledare nämns men ingen koordinerande part är utpekad.",
            pl_m.group(0)))

    # --- F7: koordinerande part svensk juridisk person, minst 1 projektpart ---
    has_coord = bool(re.search(r"koordinator|koordinerande part|samordnare", low))
    swedish = bool(re.search(r"\bab\b|aktiebolag|\bsverige\b|svensk|"
                             r"organisationsnummer|org\.?\s*nr", low))
    if has_coord and swedish:
        status, detail = "PASS", "Koordinerande part utpekad med svensk anknytning."
    elif has_coord:
        status, detail = "WARN", ("Koordinerande part utpekad men svensk "
                                  "juridisk person går inte att verifiera.")
    else:
        status, detail = "WARN", "Ingen koordinerande part utpekad i dokumentet."
    checks.append(_fc(
        "F7", "Koordinerande part = svensk juridisk person",
        "Den koordinerande parten ska vara en svensk juridisk person och "
        "bedriva verksamhet i Sverige. Minst 1 projektpart ska medverka.",
        status, detail))

    # --- F8: alla parter juridiska personer ---
    if re.search(r"enskild firma|enskild näringsidkare|fysisk person", low):
        checks.append(_fc(
            "F8", "Alla parter juridiska personer",
            "Alla deltagande organisationer ska vara juridiska personer. "
            "Fysiska personer eller enskilda firmor kan inte delta.", "FAIL",
            "Dokumentet nämner enskild firma / fysisk person som part."))
    else:
        checks.append(_fc(
            "F8", "Alla parter juridiska personer",
            "Alla deltagande organisationer ska vara juridiska personer. "
            "Fysiska personer eller enskilda firmor kan inte delta.", "PASS",
            "Inga enskilda firmor eller fysiska personer utpekade som part."))

    # --- F9: uteslutna aktörer (två tidigare utlysningar) ---
    excl_hits = []
    for dnr, name in EXCLUDED_CALL_DNRS.items():
        if dnr in full or name.lower()[:28] in low:
            pos = low.find(dnr.lower())
            if pos < 0:
                pos = low.find(name.lower()[:28])
            window = low[max(0, pos - 120):pos + 120]
            granted = bool(re.search(r"bevilja|erhållit|fått bidrag|tilldelats",
                                     window))
            excl_hits.append((dnr, name, granted, window))
    if any(g for _, _, g, _ in excl_hits):
        d = next((h for h in excl_hits if h[2]))
        checks.append(_fc(
            "F9", "Uteslutna aktörer",
            "Utlysningen vänder sig inte till aktörer som beviljats bidrag i "
            "utlysning “Verifiering för tillväxt 2025” (2025-01651) "
            "eller ”Stöd till nystartade företag genom excellenta "
            "inkubatorer, perioden 1 juli 2025 – 30 juni 2029” (2023-03309).",
            "FAIL",
            f"Dokumentet anger att part beviljats bidrag i {d[0]} ({d[1]}).",
            d[3]))
    elif excl_hits:
        checks.append(_fc(
            "F9", "Uteslutna aktörer",
            "Utlysningen vänder sig inte till aktörer som beviljats bidrag i "
            "2025-01651 eller 2023-03309.", "WARN",
            f"Utesluten utlysning nämnd ({', '.join(h[0] for h in excl_hits)}) "
            "utan att det framgår om part beviljats bidrag där. Verifiera."))
    else:
        checks.append(_fc(
            "F9", "Uteslutna aktörer",
            "Utlysningen vänder sig inte till aktörer som beviljats bidrag i "
            "2025-01651 eller 2023-03309.", "UNKNOWN",
            "Ingen av de uteslutande utlysningarna nämns. Måste verifieras "
            "mot parternas faktiska bidragshistorik."))

    # --- F10: köp mellan projektparter aldrig stödberättigande ---
    # Only a described TRANSACTION between parties may fail this check.
    # A sentence that QUOTES the rule ("Vinnovas anvisning anger att köp
    # mellan projektparter aldrig är stödberättigande") or DENIES the
    # transaction ("utan ersättning till annan part", "leverantören är
    # inte projektpart") is compliance language, not a purchase. Judging
    # the rule to be the thing it forbids is how a correct application got
    # a formal rejection — an uncertain reading may never be a FAIL.
    fail_ev, pass_ev, pass_reason = None, None, ""
    for m in _F10_BUY_RE.finditer(low):
        window = low[max(0, m.start() - 130):m.end() + 130]
        # "projektparten" has no word boundary before "part", so \bpart\w*
        # alone missed every compound form of the word.
        if not re.search(r"\bpart\w*|\w*projektpart\w*|varandra", window):
            continue
        sent = _sentence_at(low, m.start())
        excused = [t for t in _F10_NOT_A_TRANSACTION if t in sent]
        if excused:
            if pass_ev is None:
                pass_ev, pass_reason = sent.strip(), excused[0]
            continue
        fail_ev = fail_ev or window
    if fail_ev:
        checks.append(_fc(
            "F10", "Köp mellan projektparter",
            "Kostnader för köp av varor eller tjänster mellan projektparter är "
            "överhuvudtaget inte stödberättigande. (Anvisning stödberättigande "
            "kostnader 2026, avsnitt 4.3)", "FAIL",
            "Texten beskriver en faktisk transaktion mellan projektparter.",
            fail_ev))
    elif pass_ev:
        checks.append(_fc(
            "F10", "Köp mellan projektparter",
            "Kostnader för köp av varor eller tjänster mellan projektparter är "
            "överhuvudtaget inte stödberättigande.", "PASS",
            "Ingen faktisk transaktion mellan projektparter beskriven. "
            "Träffarna på transaktionsord sitter i meningar som återger "
            f"regeln eller förnekar transaktionen (\"{pass_reason}\").",
            pass_ev))
    else:
        checks.append(_fc(
            "F10", "Köp mellan projektparter",
            "Kostnader för köp av varor eller tjänster mellan projektparter är "
            "överhuvudtaget inte stödberättigande.", "UNKNOWN",
            "Inga transaktioner mellan parter beskrivna."))

    # --- F11: bilagor — endast två efterfrågas ---
    unrequested = [s for s in UNREQUESTED_ATTACHMENT_STEMS
                   if _stem_count(low, s) > 0]
    de_minimis = bool(re.search(r"de\s*minimis|mindre betydelse", low))
    if unrequested:
        checks.append(_fc(
            "F11", "Bilagor",
            "Till ansökan bifogas endast: Projektbeskrivningsmall samt Intyg "
            "om stöd av mindre betydelse (de minimis). Inga andra bilagor "
            "efterfrågas.", "WARN",
            "Dokumentet refererar bilagor som denna utlysning INTE efterfrågar: "
            + ", ".join(unrequested) + "."))
    elif de_minimis:
        checks.append(_fc(
            "F11", "Bilagor",
            "Till ansökan bifogas endast: Projektbeskrivningsmall samt Intyg "
            "om stöd av mindre betydelse (de minimis).", "PASS",
            "De minimis nämns — intyg om stöd av mindre betydelse krävs och "
            "inga otillåtna bilagor refereras."))
    else:
        checks.append(_fc(
            "F11", "Bilagor",
            "Till ansökan bifogas endast: Projektbeskrivningsmall samt Intyg "
            "om stöd av mindre betydelse (de minimis).", "UNKNOWN",
            "Inga bilagor refereras i dokumentet."))

    # --- F12: max 7 sidor, 11 punkter ---
    virtual = _looks_like_virtual_pages(model)
    if virtual:
        est = max(1, round(len(full) / 3400))
        checks.append(_fc(
            "F12", "Projektbeskrivning max 7 sidor, 11 punkter",
            "Ifylld mall får maximalt utgöra 7 sidor. Typsnitt med 11 punkters "
            "storlek ska användas. Ta bort all kursiv instruktionstext.",
            "WARN" if est > MAX_PAGES else "UNKNOWN",
            f"Indata är text/markdown — sidräkningen är virtuell och kan inte "
            f"avgöra sidantalet. Uppskattning utifrån {len(full):,} tecken: "
            f"~{est} sidor vid 11 pt. Kontrollera i den färdiga docx/pdf-filen."
            .replace(",", " ")))
    elif model.total_pages > MAX_PAGES:
        checks.append(_fc(
            "F12", "Projektbeskrivning max 7 sidor, 11 punkter",
            "Ifylld mall får maximalt utgöra 7 sidor. Projektbeskrivningar som "
            "överskrider detta antal sidor kommer inte att bedömas.", "FAIL",
            f"Dokumentet har {model.total_pages} sidor (tak {MAX_PAGES})."))
    else:
        checks.append(_fc(
            "F12", "Projektbeskrivning max 7 sidor, 11 punkter",
            "Ifylld mall får maximalt utgöra 7 sidor.", "PASS",
            f"Dokumentet har {model.total_pages} sidor."))

    # --- F13: projektsammanfattning max 1500 tecken ---
    summ = re.search(r"(?:projektsammanfattning|1\.\s*projektsammanfattning)"
                     r"[^\n]*\n(.*?)(?=\n#{1,3}\s|\n\s*2\.\s|\Z)",
                     ctx["body"], re.IGNORECASE | re.DOTALL)
    if summ:
        n = len(summ.group(1).strip())
        if n > MAX_SUMMARY_CHARS:
            checks.append(_fc(
                "F13", "Projektsammanfattning max 1500 tecken",
                "1. Projektsammanfattning (max 1500 tecken)", "FAIL",
                f"Sammanfattningen är {n} tecken (tak {MAX_SUMMARY_CHARS})."))
        else:
            checks.append(_fc(
                "F13", "Projektsammanfattning max 1500 tecken",
                "1. Projektsammanfattning (max 1500 tecken)", "PASS",
                f"Sammanfattningen är {n} tecken."))
    else:
        checks.append(_fc(
            "F13", "Projektsammanfattning max 1500 tecken",
            "1. Projektsammanfattning (max 1500 tecken)", "UNKNOWN",
            "Ingen sektion med rubriken Projektsammanfattning hittad."))

    return checks


def _looks_like_virtual_pages(model: "ProposalModel") -> bool:
    """True when the page count came from the 3000-char virtual splitter
    (md/txt/docx input) rather than from real PDF pages."""
    try:
        import crucible
        cpp = crucible._CHARS_PER_VIRTUAL_PAGE
    except Exception:
        cpp = 3000
    n = len(model.full_text or "")
    if not model.total_pages:
        return True
    return model.total_pages == max(1, n // cpp + 1)


# ============================================================
# SUB-CRITERION SIGNALS
# ============================================================
# Every signal returns (value 0.0-1.0, human-readable detail).
# Sub-score = 10 * weighted mean of its signals. Nothing is derived from
# generic buzzword lists — each signal names what it counted.

def _ratio(n: int, target: int) -> float:
    return min(1.0, n / target) if target else 0.0


def _sig_novelty_contrast(ctx):
    b = ctx["body_lower"]
    contrast = sum(_stem_count(b, s) for s in
                   ["befintlig", "existerande", "dagens", "nuläge", "i dag",
                    "idag", "till skillnad", "skiljer sig", "traditionell"])
    process = sum(_stem_count(b, s) for s in ["process", "modell", "metod"])
    v = min(1.0, (_ratio(contrast, 4) + _ratio(process, 6)) / 2)
    return v, f"{contrast} kontrastmarkörer mot befintliga processer, {process} process/modell-omnämnanden"


def _sig_named_prior_models(ctx):
    b = ctx["body_lower"]
    named = [s for s in ["trl", "mim", "eif", "iso", "cen", "nist", "brl", "irl",
                         "lean", "stage-gate", "customer development"]
             if re.search(r"\b" + re.escape(s), b)]
    return _ratio(len(named), 3), (f"namngivna befintliga modeller/standarder: "
                                   f"{', '.join(named) or 'inga'}")


def _sig_quality_capacity_pair(ctx):
    b = ctx["body_lower"]
    q, k = _stem_count(b, "kvalitet"), _stem_count(b, "kapacitet")
    v = 1.0 if q and k else (0.4 if (q or k) else 0.0)
    return v, f"kvalitet x{q}, kapacitet x{k} (utlysningen kräver BÅDA)"


def _sig_terminology(ctx):
    t = ctx["terminology"]
    return _ratio(len(t["present"]), 16), \
        f"{len(t['present'])}/{len(CALL_TERMS)} av utlysningens termer i brödtext"


def _sig_mall(ids):
    def fn(ctx):
        answered = set(ctx["mall_answered"])
        hit = [i for i in ids if i in answered]
        miss = [i for i in ids if i not in answered]
        return _ratio(len(hit), len(ids)), \
            f"mallfrågor besvarade {len(hit)}/{len(ids)}" + \
            (f"; saknas: {', '.join(miss)}" if miss else "")
    return fn


def _sig_citations(ctx):
    n, a = ctx["citations"], ctx["attributions"]
    v = min(1.0, _ratio(n, 3) * 0.6 + _ratio(a, 3) * 0.4)
    return v, (f"{n} formella källhänvisningar (författare/årtal), "
               f"{a} attributioner i löptext (enligt/källa/studie/rapport)")


def _sig_quantification(ctx):
    n, ba = ctx["quantified_units"], ctx["before_after_pairs"]
    v = min(1.0, (_ratio(n, 10) * 0.6 + _ratio(ba, 2) * 0.4))
    src = (f" ({ctx['before_after_prose']} i löptext, "
           f"{ctx['before_after_table']} i tabellform"
           + ("; " + "; ".join(ctx["before_after_notes"])
              if ctx["before_after_notes"] else "") + ")")
    return v, f"{n} kvantifierade uttryck, {ba} före/efter-par" + src


def _sig_primary_data(ctx):
    b = ctx["body_lower"]
    methods = [s for s in ["intervju", "enkät", "workshop", "fallstudie",
                           "datainsamling", "observation", "fokusgrupp",
                           "kartläggning"] if _stem_count(b, s)]
    return _ratio(len(methods), 3), \
        f"metoder för primärdata: {', '.join(methods) or 'inga'}"


def _sig_hypothesis(ctx):
    n = _stem_count(ctx["body_lower"], "hypotes")
    return _ratio(n, 2), f"{n} omnämnanden av hypotes"


def _sig_gender_depth(ctx):
    g = ctx["gender_stems"]
    depth = g["jämställ"] + g["kvinn"] + g["genus"] + g["könsfördelning"]
    return _ratio(depth, 8), (f"jämställ x{g['jämställ']}, kvinn x{g['kvinn']}, "
                              f"genus x{g['genus']}, könsfördelning "
                              f"x{g['könsfördelning']} (brödtext, ordstammar)")


def _sig_gender_target_group(ctx):
    b = ctx["body_lower"]
    v = 1.0 if (_has_any(b, ["kvinnliga idébärare", "kvinnliga företagsledare",
                             "andelen kvinn"])) else (
        0.5 if _has_any(b, ["idébärare", "idéägare"]) and
        _stem_count(b, "kvinn") else 0.0)
    return v, ("uttrycklig koppling kvinnor <-> idébärare/företagsledare"
               if v == 1.0 else "ingen uttrycklig koppling kvinnor <-> idébärare")


def _sig_named_leader(ctx):
    b = ctx["body_lower"]
    has_pl = bool(re.search(r"projektledare", b))
    named = ctx["named_people"]
    v = (0.5 if has_pl else 0.0) + (0.5 if named else 0.0)
    return min(1.0, v), (f"projektledare utpekad: {'ja' if has_pl else 'NEJ'}; "
                         f"{len(named)} namngivna personer med roll")


def _sig_cv_table(ctx):
    t = ctx["tables"]
    return (1.0 if t["table4"] else 0.0), \
        (f"TABELL 4 (CV per nyckelperson): "
         f"{'finns' if t['table4'] else 'SAKNAS'} "
         f"({t['table4_labels']}/6 kolumnetiketter)")


def _sig_hours_per_person(ctx):
    h = ctx["hours"]
    n = h["count"]
    parts = [f"TABELL 2 'Tid (h)': {len(h['table2'])} rader"
             + (f" (summa {h['table2_total']:.0f} h)"
                if h["table2_total"] else ""),
             f"TABELL 4 'Omf. (h)': {len(h['table4'])} personer",
             f"löptext: {h['prose']}"]
    return _ratio(n, 3), (f"{n} tidsangivelser i timmar — " + ", ".join(parts)
                          + " (mallen kräver omfattning per person)")


def _sig_actor_type(ctx):
    types = ctx["eligible_actor_types"]
    return _ratio(len(types), 2), \
        f"aktörstyper ur utlysningens målgrupp: {', '.join(types) or 'inga'}"


def _sig_parties(ctx):
    n = ctx["party_mentions"]
    return _ratio(n, 2), f"{n} namngivna organisationer med juridisk-person-form"


def _sig_competence(ctx):
    b = ctx["body_lower"]
    return _ratio(_stem_count(b, "kompetens") + _stem_count(b, "erfarenhet"), 5), \
        (f"kompetens x{_stem_count(b, 'kompetens')}, "
         f"erfarenhet x{_stem_count(b, 'erfarenhet')}")


def _sig_transfer(ctx):
    t = ctx["transfer_stems"]
    hits = sum(1 for k, v in t.items() if v > 0)
    return _ratio(hits, 6), \
        ("ordstammar för vidareanvändning: " +
         ", ".join(f"{k}x{v}" for k, v in t.items() if v) or "inga")


def _sig_after_project(ctx):
    b = ctx["body_lower"]
    v = 1.0 if _has_any(b, ["efter projektslut", "efter projektets slut",
                            "efter avslutat projekt"]) else (
        0.4 if _has_any(b, ["nästa steg", "fortsättning", "vidare"]) else 0.0)
    return v, ("uttrycklig beskrivning av vad som händer efter projektslut"
               if v == 1.0 else "ingen uttrycklig 'efter projektslut'-beskrivning")


def _sig_wp_tables(ctx):
    t = ctx["tables"]
    got = sum(1 for k in ("table1", "table2", "table3") if t[k])
    return _ratio(got, 3), \
        (f"TABELL 1 {'OK' if t['table1'] else 'SAKNAS'}, "
         f"TABELL 2 {'OK' if t['table2'] else 'SAKNAS'}, "
         f"TABELL 3 {'OK' if t['table3'] else 'SAKNAS'}")


def _sig_risk_scoring(ctx):
    n = ctx["tables"]["table3_scored_rows"]
    return _ratio(n, 3), \
        f"{n} riskrader med både sannolikhet och konsekvens som siffra 1-5"


def _sig_gender_balance_measured(ctx):
    g = ctx["gender_cells"]
    total = g["K"] + g["M"]
    if total == 0:
        return (0.5 if ctx["gender_statement"] else 0.0), \
            ("könsfördelning angiven i löptext" if ctx["gender_statement"]
             else "ingen könsmärkning per person (mallens kolumn 'Namn, och kön')")
    ratio = min(g["K"], g["M"]) / total
    v = min(1.0, ratio / 0.4)
    people = g.get("people") or total
    detail = (f"{g['K']} kvinnor, {g['M']} män av {people} nyckelpersoner i "
              f"TABELL 4 (balansmått {ratio:.2f})")
    if g.get("placeholder"):
        detail += (f"; {g['placeholder']} av dem är ej namngivna "
                   "(platshållare i hakparentes)")
    if g.get("unmarked"):
        detail += f"; {g['unmarked']} rader saknar könsmärkning"
    return v, detail


def _sig_gender_in_plan(ctx):
    b = ctx["body_lower"]
    hits = 0
    for m in re.finditer(r"jämställ", b):
        w = b[max(0, m.start() - 150):m.start() + 150]
        if re.search(r"arbetspaket|projektplan|aktivitet|genomförande|ap\s*\d", w):
            hits += 1
    return _ratio(hits, 2), \
        f"{hits} jämställdhetsomnämnanden inuti projektplan/arbetspaket-kontext"


SUBCRITERIA_SIGNALS: dict[str, list[tuple[str, float, callable]]] = {
    "P1": [
        ("Kontrast mot befintliga processer och modeller", 0.25, _sig_novelty_contrast),
        ("Namngivna befintliga modeller/standarder att jämföra mot", 0.20, _sig_named_prior_models),
        ("Kvalitet OCH kapacitet adresseras", 0.20, _sig_quality_capacity_pair),
        ("Utlysningens terminologi används", 0.15, _sig_terminology),
        ("Mallfrågor för nytänkande (M2.4, M3.2)", 0.20, _sig_mall(["M2.4", "M3.2"])),
    ],
    "P2": [
        ("Källhänvisningar", 0.15, _sig_citations),
        ("Kvantifiering och före/efter-par", 0.25, _sig_quantification),
        ("Metod för primärdata", 0.20, _sig_primary_data),
        ("Uttalade hypoteser", 0.15, _sig_hypothesis),
        ("Mallfrågor för problembild och resultat (M1.1, M2.1, M2.2, M2.3, M2.5, M4.2, M6.2)",
         0.25, _sig_mall(["M1.1", "M2.1", "M2.2", "M2.3", "M2.5", "M4.2", "M6.2"])),
    ],
    "P3": [
        ("Djup i jämställdhetsresonemanget (ordstammar i brödtext)", 0.40, _sig_gender_depth),
        ("Koppling till kvinnliga idébärare/företagsledare", 0.30, _sig_gender_target_group),
        ("Mallfrågor för jämställdhet (M2.6, M2.7)", 0.30, _sig_mall(["M2.6", "M2.7"])),
    ],
    "A1": [
        ("Namngiven projektledare och nyckelpersoner", 0.35, _sig_named_leader),
        ("TABELL 4 — CV per nyckelperson", 0.40, _sig_cv_table),
        ("Omfattning i timmar per person", 0.25, _sig_hours_per_person),
    ],
    "A2": [
        ("Aktörstyp inom utlysningens målgrupp", 0.25, _sig_actor_type),
        ("Namngivna juridiska personer som parter", 0.25, _sig_parties),
        ("Kompetens och erfarenhet beskriven", 0.20, _sig_competence),
        ("Mallfrågor för team och organisation (M7.1, M7.2)", 0.30, _sig_mall(["M7.1", "M7.2"])),
    ],
    "G1": [
        ("Överföring/generalisering/förvaltning (ordstammar)", 0.20, _sig_transfer),
        ("Uttrycklig beskrivning av tiden efter projektslut", 0.20, _sig_after_project),
        ("TABELL 1-3 finns", 0.20, _sig_wp_tables),
        ("Risker poängsatta 1-5", 0.10, _sig_risk_scoring),
        ("Mallfrågor för genomförande och nyttiggörande "
         "(M3.1, M3.3, M3.4, M3.5, M4.1, M5.1, M5.2, M5.4, M5.5, M6.1, M6.3)",
         0.30, _sig_mall(["M3.1", "M3.3", "M3.4", "M3.5", "M4.1", "M5.1",
                          "M5.2", "M5.4", "M5.5", "M6.1", "M6.3"])),
    ],
    "G2": [
        ("Uppmätt könsfördelning i teamet", 0.40, _sig_gender_balance_measured),
        ("Jämställdhet inuti projektplanen", 0.30, _sig_gender_in_plan),
        ("Mallfrågor för kön/genus i plan och team (M5.3, M7.3, M7.4)",
         0.30, _sig_mall(["M5.3", "M7.3", "M7.4"])),
    ],
}


# ============================================================
# THE MODULE
# ============================================================

@dataclass
class VinnovaEkosystemVVModule(CallModule):
    name: str = "vinnova-ekosystem-vv"
    version: str = "1.0.0"
    description: str = ("Vinnova 2026-01401 — Ekosysteminsats: verifiering och "
                        "validering för kommersialisering av kunskapsintensiva "
                        "idéer (3 kriterier, 7 underkriterier, 0-10)")
    funding_body: str = "Vinnova"
    languages: list = field(default_factory=lambda: ["sv", "en"])
    countries: list = field(default_factory=lambda: ["SE"])

    def matches(self, anchor: "ProposalAnchor") -> float:
        """Confidence that this proposal belongs to call 2026-01401.

        The anchor carries no diarienummer, so a generic Swedish Vinnova
        document is indistinguishable from this call at anchor level.
        Auto-detection therefore stays deliberately BELOW the registry's
        0.3 threshold unless the anchor explicitly names this call — that
        way the generic `vinnova` module keeps its existing behaviour and
        nothing regresses. Select this module with
        `--module vinnova-ekosystem-vv`.
        """
        program = (anchor.funding_program or "").lower()
        body = (anchor.funding_body or "").lower()

        # Explicit: only fires if the core anchor ever learns this call.
        if CALL_DNR in program or "ekosysteminsats" in program:
            return 1.0

        score = 0.0
        if "vinnova" in body:
            score += 0.15
        if anchor.language == "sv":
            score += 0.05
        if (anchor.country or "").upper() == "SE":
            score += 0.05
        if anchor.doc_scale in ("micro", "compact"):
            score += 0.04
        return min(score, 0.29)  # never auto-selects; never steals `vinnova`

    def get_lexicon(self) -> dict[str, list[str]]:
        """The call's own vocabulary, not Horizon Europe's."""
        return {
            "knowledge-intensive ideas": ["kunskapsintensiva idéer",
                                          "kunskapsintensiv idé"],
            "verification": ["verifiering", "verifiera"],
            "validation": ["validering", "validera"],
            "commercialization": ["kommersialisering", "kommersialisera"],
            "right point in time": ["rätt tidpunkt", "rätt läge"],
            "maturity phase": ["mognadsfas", "mognadsgrad"],
            "idea carrier": ["idébärare", "idéägare"],
            "support system": ["stödsystem", "innovationsstödsystem"],
            "support activity": ["stödverksamhet"],
            "intermediary": ["intermediär"],
            "innovation hub": ["innovationshubb"],
            "science park": ["science park"],
            "innovation cluster": ["innovationskluster", "kluster"],
            "test and demo environment": ["test- och demomiljö", "testbädd",
                                          "demomiljö"],
            "research and innovation infrastructure": [
                "forsknings- och innovationsinfrastruktur",
                "innovationsinfrastruktur"],
            "regional innovation platform": ["regional innovationsplattform",
                                             "innovationsplattform"],
            "target group": ["målgrupp"],
            "demand": ["efterfrågan", "efterfråga"],
            "quality": ["kvalitet"],
            "capacity": ["kapacitet"],
            "gender equality": ["jämställdhet", "jämställd"],
            "sex": ["kön"],
            "gender": ["genus"],
            "female idea carriers": ["kvinnliga idébärare",
                                     "kvinnliga företagsledare"],
            "investment ready": ["investeringsredo", "investeringsmogen"],
            "national innovation support capability": [
                "nationell innovationsstödsförmåga", "innovationsstödsförmåga"],
            "gap": ["glapp", "brist"],
            "feasibility study": ["förstudie", "genomförbarhetsstudie"],
            "de minimis": ["stöd av mindre betydelse", "de minimis"],
            "eligible costs": ["stödberättigande kostnader"],
            "indirect costs": ["indirekta kostnader", "overhead"],
            "consultancy and licence costs": ["konsult- och licenskostnader",
                                              "konsultkostnader", "licenskostnader"],
            "coordinating party": ["koordinerande part", "koordinator"],
            "project party": ["projektpart"],
        }

    def get_preflight_questions(self) -> list[dict]:
        return [
            {"id": "VVV-PF1",
             "question": "Är sökt bidrag högst 500 000 kr och projekttiden "
                         "högst 3 månader?", "weight": 3},
            {"id": "VVV-PF2",
             "question": "Startar projektet tidigast 2026-10-20, senast "
                         "2026-10-26, och avslutas senast 2027-01-31?",
             "weight": 3},
            {"id": "VVV-PF3",
             "question": "Är konsult- och licenskostnader högst 20 % av VARJE "
                         "organisations totala projektbudget (inte av bidraget)?",
             "weight": 3},
            {"id": "VVV-PF4",
             "question": "Är indirekta kostnader högst 30 % av lönekostnaderna?",
             "weight": 2},
            {"id": "VVV-PF5",
             "question": "Är projektledaren anställd hos koordinerande part, och "
                         "är koordinatorn en svensk juridisk person med "
                         "verksamhet i Sverige?", "weight": 3},
            {"id": "VVV-PF6",
             "question": "Är alla parter juridiska personer (inga enskilda "
                         "firmor eller fysiska personer)?", "weight": 3},
            {"id": "VVV-PF7",
             "question": "Har ingen part beviljats bidrag i 2025-01651 "
                         "(Verifiering för tillväxt 2025) eller 2023-03309 "
                         "(excellenta inkubatorer)?", "weight": 3},
            {"id": "VVV-PF8",
             "question": "Är budgeten fri från köp mellan projektparter?",
             "weight": 3},
            {"id": "VVV-PF9",
             "question": "Bifogas ENDAST Projektbeskrivningsmall och (vid de "
                         "minimis) Intyg om stöd av mindre betydelse?",
             "weight": 2},
            {"id": "VVV-PF10",
             "question": "Är projektbeskrivningen max 7 sidor i 11 punkter med "
                         "all kursiv instruktionstext borttagen?", "weight": 3},
            {"id": "VVV-PF11",
             "question": "Är projektsammanfattningen max 1500 tecken och "
                         "inklistrad i e-tjänsten?", "weight": 2},
            {"id": "VVV-PF12",
             "question": "Är samtliga fyra tabeller ifyllda (AP/kostnad, "
                         "AP-budget, risk 1-5, CV per nyckelperson)?",
             "weight": 3},
            {"id": "VVV-PF13",
             "question": "Är jämställdhet besvarad på alla fyra ställen "
                         "utlysningen kräver: parternas verksamhet, idéägare/"
                         "företag, projektplanen, och teamets könsfördelning "
                         "inkl. makt och inflytande?", "weight": 3},
        ]

    def get_structural_checks(self) -> list[tuple[str, callable]]:
        return [
            ("VVV: Formella krav (avslagsgrundande)", self._check_formal),
            ("VVV: Mallens obligatoriska frågor", self._check_mall_questions),
            ("VVV: Mallens fyra tabeller", self._check_tables),
            ("VVV: Jämställdhet i två av tre kriterier", self._check_gender_coverage),
            ("VVV: Utlysningens terminologi", self._check_terminology),
        ]

    def get_detectors(self) -> list[tuple[str, callable]]:
        return [
            ("VVV: Bilagor som inte efterfrågas", self._detect_unrequested_attachments),
            ("VVV: Impact Innovation-kalibrering återanvänd", self._detect_wrong_call_reuse),
            ("VVV: Scope för stort för 3 månader / 500 kkr", self._detect_scope_overreach),
            ("VVV: Leverantörsannons istället för ekosystemnytta", self._detect_vendor_pitch),
            ("VVV: Overifierade meriter", self._detect_unverified_claims),
        ]

    # --- Scoring ---

    def score(self, model: "ProposalModel", result: "AnalysisResult") -> Optional[dict]:
        ctx = _build_context(model)

        subscores = []
        by_id = {}
        for meta in SUBCRITERIA_META:
            signals = []
            num = den = 0.0
            for sig_name, w, fn in SUBCRITERIA_SIGNALS[meta["id"]]:
                try:
                    v, detail = fn(ctx)
                except Exception as e:          # never let one signal kill scoring
                    v, detail = 0.0, f"signalfel: {e}"
                v = max(0.0, min(1.0, float(v)))
                signals.append({"name": sig_name, "weight": w,
                                "value": round(v, 3),
                                "points": round(v * w * 10, 2),
                                "max_points": round(w * 10, 2),
                                "detail": detail})
                num += v * w
                den += w
            sub = round(10.0 * num / den, 1) if den else 0.0
            entry = {"id": meta["id"], "criterion": meta["criterion"],
                     "weight_in_criterion": meta["weight"], "name": meta["name"],
                     "score": sub, "signals": signals}
            subscores.append(entry)
            by_id[meta["id"]] = entry

        criteria = {}
        for crit in CRITERIA_WEIGHTS:
            parts = [s for s in subscores if s["criterion"] == crit]
            den = sum(p["weight_in_criterion"] for p in parts)
            criteria[crit] = round(
                sum(p["score"] * p["weight_in_criterion"] for p in parts) / den, 1
            ) if den else 0.0

        raw_composite = round(
            sum(criteria[c] * w for c, w in CRITERIA_WEIGHTS.items()), 1)

        fails = [c for c in ctx["formal"] if c["status"] == "FAIL"]
        warns = [c for c in ctx["formal"] if c["status"] == "WARN"]
        unknowns = [c for c in ctx["formal"] if c["status"] == "UNKNOWN"]
        formal_fail = bool(fails)
        composite = 0.0 if formal_fail else raw_composite

        return {
            "call": f"Vinnova {CALL_DNR}",
            "potential": criteria["potential"],
            "aktörer": criteria["aktörer"],
            "genomförbarhet": criteria["genomförbarhet"],
            "composite": composite,
            "raw_composite": raw_composite,
            "scale": "0-10",
            "criteria_weights": CRITERIA_WEIGHTS,
            "formal_fail": formal_fail,
            "formal_fail_ids": [c["id"] for c in fails],
            "formal_warn_ids": [c["id"] for c in warns],
            "formal_unknown_ids": [c["id"] for c in unknowns],
            "formal_checks": ctx["formal"],
            "subscores": subscores,
            "mall_answered": ctx["mall_answered"],
            "mall_missing": [q["id"] for q in ctx["mall_missing"]],
            "mall_total": len(MALL_QUESTIONS),
            "tables": ctx["tables"],
            "terminology": ctx["terminology"],
            "gender_cells": ctx["gender_cells"],
            "named_people": ctx["named_people"],
        }

    def format_scores(self, scores: dict) -> list[str]:
        if not scores:
            return []
        W = 78
        rule = "  " + "=" * W
        thin = "  " + "-" * W
        lines: list[str] = ["", rule,
                            f"  VINNOVA {CALL_DNR} — EKOSYSTEMINSATS V&V "
                            f"(3 kriterier / 7 underkriterier, skala 0-10)",
                            rule, ""]

        # --- Formal requirements first: they gate everything ---
        lines.append("  FORMELLA KRAV — brott mot dessa ger direkt avslag")
        lines.append(thin)
        icons = {"PASS": "PASS ", "FAIL": "FAIL ", "WARN": "WARN ",
                 "UNKNOWN": "?    "}
        for c in scores.get("formal_checks", []):
            lines.append(f"  [{icons.get(c['status'], '?    ')}] {c['id']}  "
                         f"{c['label']}")
            for chunk in _wrap(c["detail"], W - 12):
                lines.append(f"           {chunk}")
        lines.append("")

        if scores.get("formal_fail"):
            lines += [
                "  " + "!" * W,
                "  !! FORMELLT AVSLAG — ansökan bedöms inte alls.",
                f"  !! Brutna krav: {', '.join(scores.get('formal_fail_ids', []))}",
                "  !! Composite tvingas till 0.0 oavsett innehållets kvalitet.",
                "  " + "!" * W,
                "",
            ]

        # --- The three criteria ---
        lines.append("  BEDÖMNINGSKRITERIER")
        lines.append(thin)
        cw = scores.get("criteria_weights", CRITERIA_WEIGHTS)
        for key, label in (("potential", "Potential"),
                           ("aktörer", "Aktörer"),
                           ("genomförbarhet", "Genomförbarhet")):
            val = scores.get(key, 0.0)
            lines.append(f"  {label:<18} {val:>4.1f} / 10.0   "
                         f"(vikt {cw.get(key, 0)*100:.0f} %)  {_bar(val)}")
        lines.append(thin)
        if scores.get("formal_fail"):
            lines.append(f"  COMPOSITE           0.0 / 10.0   "
                         f"(FORMELLT AVSLAG; oviktat innehållsvärde "
                         f"{scores.get('raw_composite', 0):.1f})")
        else:
            lines.append(f"  COMPOSITE          {scores.get('composite', 0):>4.1f} "
                         f"/ 10.0   (40/25/35)")
        lines.append("")

        # --- Sub-criteria with per-signal points ---
        lines.append("  UNDERKRITERIER — här tappas poängen")
        lines.append(thin)
        for s in scores.get("subscores", []):
            lines.append("")
            lines.append(f"  [{s['id']}] {s['score']:>4.1f} / 10.0  "
                         f"({s['criterion']}, vikt "
                         f"{s['weight_in_criterion']*100:.0f} % inom kriteriet)")
            for chunk in _wrap(s["name"], W - 8):
                lines.append(f"        {chunk}")
            for sig in s["signals"]:
                lines.append(f"        {sig['points']:>5.2f}/{sig['max_points']:<5.2f}"
                             f"  {sig['name']}")
                for chunk in _wrap(sig["detail"], W - 20):
                    lines.append(f"                     {chunk}")
        lines.append("")

        # --- Template questions ---
        missing = scores.get("mall_missing", [])
        total = scores.get("mall_total", 0)
        lines.append(f"  PROJEKTBESKRIVNINGSMALLEN — {total - len(missing)}/{total} "
                     f"obligatoriska frågor besvarade")
        lines.append(thin)
        if missing:
            qmap = {q["id"]: q for q in MALL_QUESTIONS}
            for qid in missing:
                q = qmap[qid]
                lines.append(f"  SAKNAS  {qid}  ({q['chapter']})")
                for chunk in _wrap(q["question"], W - 12):
                    lines.append(f"          {chunk}")
        else:
            lines.append("  Alla obligatoriska frågor är besvarade.")
        lines.append("")

        # --- Tables ---
        t = scores.get("tables", {})
        lines.append("  MALLENS FYRA TABELLER")
        lines.append(thin)
        for key, label in (("table1", "TABELL 1  AP | aktivitet och konkret resultat | kostnad"),
                           ("table2", "TABELL 2  AP | tidsperiod | personer | kostnadsslag | bidrag"),
                           ("table3", "TABELL 3  risk | sannolikhet 1-5 | konsekvens 1-5 | åtgärd"),
                           ("table4", "TABELL 4  CV per nyckelperson (namn och kön, roll, timmar)")):
            lines.append(f"  [{'OK  ' if t.get(key) else 'SAKNAS'}] {label}")
        lines.append("")

        # --- Terminology ---
        term = scores.get("terminology", {})
        lines.append(f"  UTLYSNINGENS TERMINOLOGI — "
                     f"{len(term.get('present', []))}/{len(CALL_TERMS)} termer i brödtext")
        lines.append(thin)
        miss = term.get("missing", [])
        if miss:
            for chunk in _wrap("Saknas: " + ", ".join(miss), W - 4):
                lines.append(f"  {chunk}")
        else:
            lines.append("  Full täckning.")
        lines.append("")
        return lines

    def get_extraction_hints(self) -> dict:
        return {
            "budget_patterns": [
                r"(?:Sökt\s+bidrag|Söker\s+bidrag|Bidrag)[:\s]+([\d\s \.,]+)\s*(?:kr|SEK|kronor)",
                r"(?:Total\s+projektkostnad|Totala\s+kostnader|Summa)[:\s]+([\d\s \.,]+)\s*(?:kr|SEK|kronor)",
                r"(?:Egen\s+finansiering)[:\s]+([\d\s \.,]+)\s*(?:kr|SEK|kronor)",
                r"(?:Konsultkostnader,\s*licenser[^\n]*?)([\d\s \.,]{4,})",
                r"(?:Indirekta\s+kostnader[^\n]*?)([\d\s \.,]{4,})",
            ],
            "duration_patterns": [
                r"(?:Projekttid|Projektlängd|Projektperiod|Löptid)[:\s]+(\d{1,2})\s*(?:månader|mån)",
                r"(\d{4}-\d{2}-\d{2})\s*[-–till]{1,4}\s*(\d{4}-\d{2}-\d{2})",
                r"(\d{1,2})\s+(?:okt|oktober|nov|november|dec|december|jan|januari)\.?\s*(20\d{2})",
            ],
            "partner_patterns": [
                r"(?:Koordinator|Koordinerande\s+part)[:\s]+([^\n]{3,80})",
                r"(?:Projektpart(?:er)?)[:\s]+([^\n]{3,120})",
                r"(?:Org\.?\s*nr|Organisationsnummer)[:\s]+(\d{6}-\d{4})",
            ],
            "risk_patterns": [
                r"([^|\n]{5,80})\|\s*([1-5])\s*\|\s*([1-5])\s*\|([^|\n]{3,120})",
            ],
            "person_patterns": [
                r"Namn[,\s]*(?:och\s*)?kön[:\s|]+([^\n|]{3,60})",
                r"Omfattning\s+medv\.?\s*\(h\)[^\d]{0,20}(\d{1,4})",
            ],
        }

    def get_markers(self) -> dict[str, list[str]]:
        return {
            "potential_nytänkande": ["befintlig", "existerande", "dagens",
                                     "till skillnad", "nytänkande", "process",
                                     "modell", "kvalitet", "kapacitet"],
            "potential_trovärdighet": ["hypotes", "intervju", "enkät", "workshop",
                                       "datainsamling", "kvantifier", "glapp",
                                       "brist", "problembild"],
            "jämställdhet": ["jämställ", "kvinn", "genus", "könsfördelning",
                             "kön", "makt", "inflytande", "idébärare"],
            "aktörer": ["projektledare", "nyckelperson", "kompetens",
                        "erfarenhet", "koordinator", "projektpart", "roll"],
            "genomförbarhet": ["överför", "generalis", "implementer", "förvalt",
                               "skala", "sprid", "efter projektslut",
                               "arbetspaket", "risk", "åtgärd"],
            "målgrupp": ELIGIBLE_ACTOR_STEMS,
        }

    # --- Structural checks ---

    @staticmethod
    def _check_formal(model: "ProposalModel", result: "AnalysisResult"):
        ctx = _build_context(model)
        for c in ctx["formal"]:
            if c["status"] == "FAIL":
                result.add(
                    f"FORMELLT AVSLAG {c['id']}: {c['label']}", "CRITICAL", 0,
                    f"{c['detail']} — KRAV: {c['requirement']}",
                    "Brott mot formella krav ger direkt avslag. Rätta detta "
                    "före allt annat arbete i ansökan.",
                    "formal", 1,
                )
            elif c["status"] == "WARN":
                result.add(
                    f"Formellt krav ej styrkt {c['id']}: {c['label']}", "HIGH", 0,
                    f"{c['detail']} — KRAV: {c['requirement']}",
                    "Skriv ut uppgiften explicit i ansökan så att bedömaren "
                    "kan verifiera den utan att gissa.",
                    "formal", 1,
                )

    @staticmethod
    def _check_mall_questions(model: "ProposalModel", result: "AnalysisResult"):
        ctx = _build_context(model)
        for q in ctx["mall_missing"]:
            missing = _missing_groups(q, ctx)
            result.add(
                f"Mallfråga obesvarad {q['id']} (kap {q['chapter']})",
                q["severity"], 0,
                q["question"],
                "Besvara frågan ordagrant i projektbeskrivningen. "
                f"Saknade begrepp: {', '.join(missing) or '(strukturellt)'}.",
                "mall", 1,
            )

    @staticmethod
    def _check_tables(model: "ProposalModel", result: "AnalysisResult"):
        ctx = _build_context(model)
        t = ctx["tables"]
        labels = {
            "table1": "TABELL 1: Arbetspaket (AP) | Beskrivning av aktivitet "
                      "och dess konkreta resultat | Kostnad",
            "table2": "TABELL 2: Arbetspaket | Tidsperiod | Medverkande personer "
                      "| Personal | Tid (timmar) | Konsultkostnader, licenser "
                      "| Utrustning | Övriga direkta | Indirekta | Egen "
                      "finansiering | Sökt bidrag",
            "table3": "TABELL 3: Risk | Sannolikhet (1-5) | Konsekvens (1-5) "
                      "| Åtgärd",
            "table4": "TABELL 4: CV per nyckelperson (Namn och kön | Titel, "
                      "Organisation | Omfattning medv. (h) | Roll | Kompetens "
                      "| Motiv)",
        }
        for key, label in labels.items():
            if not t.get(key):
                result.add(
                    f"Obligatorisk tabell saknas ({key.upper()})", "CRITICAL", 0,
                    label,
                    "Mallen kräver tabellen ifylld. En tom eller saknad tabell "
                    "läses som ett ofullständigt underlag.",
                    "mall", 1,
                )
        if t.get("table3") and t.get("table3_scored_rows", 0) == 0:
            result.add(
                "Risktabell utan siffersättning", "HIGH", 0,
                "TABELL 3 finns men ingen rad har både sannolikhet och "
                "konsekvens som en siffra 1-5.",
                "Mallen kräver en siffra 1-5 för sannolikhet och en för "
                "konsekvens på varje risk.",
                "mall", 1,
            )

    @staticmethod
    def _check_gender_coverage(model: "ProposalModel", result: "AnalysisResult"):
        ctx = _build_context(model)
        g = ctx["gender_stems"]
        if g["jämställ"] + g["kvinn"] + g["genus"] == 0:
            result.add(
                "Jämställdhet saknas helt", "CRITICAL", 0,
                "Inga träffar på ordstammarna jämställ / kvinn / genus i "
                "brödtexten. Jämställdhet ingår i TVÅ av tre huvudkriterier "
                "(Potential och Genomförbarhet) i denna utlysning.",
                "Besvara jämställdhet på alla fyra ställen: parternas "
                "verksamhet, idéägare/företag som tar del av tjänsterna, "
                "projektplanen, samt teamets könsfördelning och fördelning av "
                "makt och inflytande.",
                "jämställdhet", 1,
            )
            return
        if g["genus"] == 0:
            result.add(
                "Genusperspektiv saknas", "HIGH", 0,
                "Ordstammen 'genus' saknas. Utlysningen bedömer uttryckligen "
                "'perspektiv kring kön och genus' i både Potential och "
                "Genomförbarhet.",
                "Skriv ut hur kön OCH genus är relevanta för lösningens "
                "utformning — eller motivera varför de inte är det.",
                "jämställdhet", 1,
            )
        if g["makt"] == 0 or g["inflytande"] == 0:
            result.add(
                "Makt och inflytande ej beskrivet", "HIGH", 0,
                "Mallen kräver 'fördelning av makt och inflytande mellan "
                "kvinnor och män inom genomförandet'. Ordstammarna makt/"
                f"inflytande förekommer {g['makt']}/{g['inflytande']} gånger.",
                "Beskriv vem som beslutar vad, inte bara vem som deltar.",
                "jämställdhet", 1,
            )
        cells = ctx["gender_cells"]
        if cells["K"] + cells["M"] == 0 and not ctx["gender_statement"]:
            result.add(
                "Könsfördelning inte mätbar", "HIGH", 0,
                "Ingen person är könsmärkt (mallens TABELL 4 har kolumnen "
                "'Namn, och kön') och ingen könsfördelning anges i löptext.",
                "Ange kön per nyckelperson i CV-tabellen så att bedömaren kan "
                "räkna könsfördelningen.",
                "jämställdhet", 1,
            )
        elif cells.get("placeholder"):
            result.add(
                "Könsfördelningen vilar på ej namngivna personer", "MEDIUM", 0,
                f"{cells['K']} kvinnor och {cells['M']} män är könsmärkta i "
                f"TABELL 4, men {cells['placeholder']} av dem är platshållare "
                "utan namn.",
                "En könsmärkning på en person som ännu inte finns är en "
                "bemanningsavsikt, inte en könsfördelning. Namnge personerna "
                "före inlämning.",
                "jämställdhet", 1,
            )

    @staticmethod
    def _check_terminology(model: "ProposalModel", result: "AnalysisResult"):
        ctx = _build_context(model)
        t = ctx["terminology"]
        core = ["kunskapsintensiva idéer", "verifiering", "validering",
                "stödsystem", "målgrupp", "efterfrågan", "kapacitet"]
        missing_core = [c for c in core if c in t["missing"]]
        if missing_core:
            result.add(
                "Utlysningens kärntermer saknas", "HIGH", 0,
                "Följande termer ur utlysningstexten saknas i brödtexten: "
                + ", ".join(missing_core) + ".",
                "Bedömarna läser mot utlysningens egna begrepp. Använd dem "
                "ordagrant där de hör hemma — det är inte nyckelordsstoppning, "
                "det är att svara på frågan som ställdes.",
                "terminologi", 2,
            )

    # --- Anti-pattern detectors ---

    @staticmethod
    def _detect_unrequested_attachments(pages, result, start, model):
        low = (model.full_text or "").lower()
        found = [s for s in UNREQUESTED_ATTACHMENT_STEMS if s in low]
        if found:
            result.add(
                "Bilaga som inte efterfrågas", "MEDIUM", 0,
                "Dokumentet refererar " + ", ".join(found) + ". Denna utlysning "
                "efterfrågar ENDAST Projektbeskrivningsmall och Intyg om stöd "
                "av mindre betydelse.",
                "Vinnova skriver: 'tänk på att endast lämna in de bilagor vi "
                "begär'. Lägg tiden på projektbeskrivningen i stället.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_wrong_call_reuse(pages, result, start, model):
        low = (model.full_text or "").lower()
        wrong = [s for s in ["impact innovation", "kategori 1", "kategori 2",
                             "kategori 3", "konceptstudie", "medfinansiering "
                             "om 50", "utmaningsdriven innovation"] if s in low]
        if wrong:
            result.add(
                "Kalibrering från annan Vinnova-utlysning återanvänd", "HIGH", 0,
                "Dokumentet innehåller begrepp från andra Vinnova-erbjudanden: "
                + ", ".join(wrong) + ". Denna utlysning har inga kategorier, "
                "inget medfinansieringskrav och ett tak på 500 000 kr / 3 "
                "månader.",
                "Ta bort kategoriskrivningar och medfinansieringslöften som "
                "inte gäller här.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_scope_overreach(pages, result, start, model):
        low = (model.full_text or "").lower()
        heavy = [s for s in ["pilot", "demonstrator", "driftsättning",
                             "produktionssättning", "utrullning", "prototyp",
                             "fullskalig", "implementering i drift"]
                 if s in low]
        if len(heavy) >= 3:
            result.add(
                "Scope för stort för en 3-månaders förstudie", "HIGH", 0,
                f"{len(heavy)} genomförandetunga begrepp hittade ({', '.join(heavy[:5])}). "
                "Utlysningen finansierar en FÖRSTUDIE på högst 3 månader och "
                "500 000 kr: analysera glapp, identifiera behov, testa hypotes.",
                "Flytta pilot/driftsättning till avsnittet om vad som händer "
                "efter projektslut. Behåll analys och hypotesprövning i scope.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_vendor_pitch(pages, result, start, model):
        ctx = _build_context(model)
        b = ctx["body_lower"]
        ecosystem = sum(_stem_count(b, s) for s in
                        ["stödsystem", "ekosystem", "målgrupp", "nationell",
                         "andra aktörer", "innovationsstöd"])
        product = sum(_stem_count(b, s) for s in
                      ["vår produkt", "vår lösning", "vårt verktyg",
                       "vår plattform", "vårt ramverk", "vår metod"])
        generalise = sum(_stem_count(b, s) for s in
                         ["generalis", "överför", "andra aktörer kan",
                          "oberoende av", "som klass", "nästa instans"])
        if product >= 3 and generalise == 0 and ecosystem < product:
            result.add(
                "Läses som leverantörsannons, inte ekosystemnytta", "HIGH", 0,
                f"{product} omnämnanden av den egna lösningen mot {ecosystem} "
                "av stödsystem/ekosystem/målgrupp, och noll ordstammar för "
                "generalisering eller överförbarhet.",
                "Utlysningen finansierar ökad kvalitet och kapacitet i "
                "STÖDSYSTEMET. Beskriv lösningen som en klass som fungerar "
                "för nästa aktör utan omskrivning, inte som en enskild produkt.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_unverified_claims(pages, result, start, model):
        text = model.full_text or ""
        flags = re.findall(
            r"[^\n.]{0,120}(?:ska verifieras|obekräftad|ej verifierad|"
            r"verifieras innan|kontrolleras innan|TBD|TODO|\[\s*\?\s*\])[^\n.]{0,80}",
            text, re.IGNORECASE)
        if flags:
            result.add(
                "Overifierade uppgifter kvar i texten", "CRITICAL", 0,
                f"{len(flags)} markering(ar) om uppgifter som ännu inte är "
                f"verifierade, t.ex.: \"{flags[0].strip()[:140]}\".",
                "Verifiera eller ta bort. En felaktig uppgift i en ansökan till "
                "en myndighet är en oriktig uppgift, inte ett utkast.",
                "anti-pattern", 4,
            )


# ============================================================
# FORMATTING HELPERS
# ============================================================

def _wrap(text: str, width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return []
    out, cur = [], words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out


def _bar(value: float, width: int = 20) -> str:
    filled = int(round(max(0.0, min(10.0, value)) / 10.0 * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"
