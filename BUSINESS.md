# CRUCIBLE — Business Model Canvas & Value Proposition Canvas

## Value Proposition Canvas

### Customer Segment: EU Grant Applicants (Research & Industry)

**Jobs to be Done:**
- Write a competitive Horizon Europe proposal (€5M-€20M projects)
- Score above threshold (10/15) and rank in top quartile
- Avoid preventable mistakes that cost points
- Align proposal to call requirements perfectly
- Get feedback before submission without hiring a €10K consultant

**Pains:**
- 15% success rate — 85% of effort is wasted
- Evaluators spend 2-3 hours per proposal — first impressions matter
- No feedback until rejection (6+ months later)
- Consultants cost €5K-€15K per proposal review
- Copy-paste errors, placeholder text, inconsistencies slip through in consortium chaos
- 18 partners writing sections independently = patchwork quality
- No way to verify call alignment before submission

**Gains:**
- Instant, objective scoring before submission
- Specific, actionable fixes (not vague "improve this")
- Confidence that basics are covered
- Call-aligned proposal that mirrors evaluator checklist
- Time saved vs manual review (hours → minutes)
- Learning tool — teams improve over repeated use

### Value Map: CRUCIBLE

**Pain Relievers:**
- Catches 45+ anti-patterns evaluators flag (saves ~1-2 points)
- Cross-validates Part A / Part B consistency (catches mismatches)
- Identifies placeholder text, copy-paste errors, typos automatically
- Checks call alignment against actual topic text
- Costs €49/month vs €10K consultant
- Results in 60 seconds, not 2 weeks

**Gain Creators:**
- SMILE methodology radar shows maturity gaps
- Estimated score prediction (Excellence/Impact/Implementation)
- Structured improvement checklist per criterion
- JSON export for programmatic integration into workflows
- Field awareness checks ensure proper citations and competitor acknowledgment
- Pre-submission confidence — "we've been through the CRUCIBLE"

**Products & Services:**
- Free: Basic anti-pattern scan (Layer 4), 3/month
- Pro €49/mo: Full 4-layer analysis, SMILE radar, call alignment, unlimited, PDF+JSON reports
- Enterprise €199/mo: API, team accounts, custom SMILE config, priority support, batch analysis

---

## Business Model Canvas

### 1. Customer Segments
- **Primary**: University research offices & NCPs (National Contact Points) writing 10-50 proposals/year
- **Secondary**: SMEs in Horizon Europe consortia (need to self-check their contribution sections)
- **Tertiary**: Professional grant writers / consultancies (tool amplifies their work)
- **Future**: Extend to NSF, NIH, ERC, UKRI — same anti-patterns, different templates

### 2. Value Propositions
- "The evaluator you run before the real evaluators"
- Instant, objective, actionable proposal scoring
- 45+ anti-pattern detection built from real evaluator experience
- SMILE methodology integration (unique differentiator)
- 100x cheaper than a human consultant, 100x faster

### 3. Channels
- SEO: "Horizon Europe proposal checker", "EU grant proposal analyzer"
- LinkedIn: EU research community, NCP networks, university grant offices
- Content: Blog posts on each anti-pattern (25+ SEO-optimized articles)
- Partnerships: NCPs, research support offices, European university associations
- Open-source core: GitHub → awareness → conversion to paid
- Conferences: EARMA, ARMA, GrantCraft, Horizon Europe info days

### 4. Customer Relationships
- Self-service (Free + Pro tiers)
- Automated onboarding: upload PDF → instant results
- Weekly "Proposal Tips" newsletter
- Enterprise: dedicated support + custom config
- Community: GitHub issues + discussions

### 5. Revenue Streams
- **Pro subscriptions**: €49/month (€39/month annual) — target 200 subscribers = €9.8K MRR
- **Enterprise subscriptions**: €199/month — target 20 = €3.98K MRR
- **Pay-per-analysis**: €9.90/analysis for non-subscribers
- **API metered**: €0.50/analysis for integrators
- **Target Year 1**: €15K MRR = €180K ARR (break-even for 1 engineer)
- **Target Year 2**: €50K MRR = €600K ARR (EARMA has 2,500 members alone)

### 6. Key Resources
- CRUCIBLE analyzer engine (Python, open-source core)
- SMILE methodology IP (WINNIIO proprietary)
- Anti-pattern database (continuously expanded)
- Call text database (scraped from Funding & Tenders Portal)
- Domain expertise in Horizon Europe evaluation

### 7. Key Activities
- Maintain and expand anti-pattern detectors
- Scrape and parse new call texts each work programme cycle
- SEO content production (anti-pattern blog series)
- Community management (GitHub, LinkedIn)
- Customer success for Enterprise tier
- Extend to other funding programmes (NSF, NIH, ERC)

### 8. Key Partnerships
- National Contact Points (NCPs) — embedded tool recommendation
- EARMA (European Association of Research Managers)
- University research support offices (bulk licenses)
- Grant consultancies (white-label or referral)
- Funding & Tenders Portal (API access if available)

### 9. Cost Structure
- Hosting: ~€50/month (Vercel + Python backend)
- Stripe fees: 2.9% + €0.25 per transaction
- Development: 0 (built in-house, open-source contributions)
- Marketing: LinkedIn ads + content = €500/month initially
- Total monthly burn: <€600 until revenue covers it
- Break-even: ~15 Pro subscribers (€735/month covers costs)

---

## Pricing Strategy

| Tier | Price | Gate | Target |
|------|-------|------|--------|
| Free | €0 | Layer 4 only, top 5 findings, no export | Try → Convert |
| Single | €9.90/analysis | All 4 layers, 25 findings, SMILE, score estimate | One-off near deadline |
| Pro | €49/mo (€39 annual) | Full analysis, unlimited, PDF+JSON, call alignment | Individual researchers, SMEs |
| Enterprise | €199/mo | API, teams, batch, composite scoring, priority support | Research offices, NCPs |

## Feature Gating

| Feature | Free | Single | Pro | Enterprise |
|---------|------|--------|-----|-----------|
| Layer 4: Anti-patterns | ✓ (top 5) | ✓ (top 25) | ✓ (all 45+) | ✓ |
| Layer 1: Structural integrity | ✗ | ✓ | ✓ | ✓ |
| Layer 2: Call alignment | ✗ | ✓ | ✓ | ✓ |
| Layer 3: SMILE radar | ✗ | ✓ | ✓ | ✓ + custom config |
| Score estimate | ✗ | ✓ | ✓ | ✓ |
| EIC Pathfinder scoring | ✗ | ✗ | ✗ | ✓ |
| Strategic dimensions | ✗ | ✗ | ✗ | ✓ |
| PESTLE+D analysis | ✗ | ✗ | ✗ | ✓ |
| EU Interop scoring | ✗ | ✗ | ✗ | ✓ |
| Stress test | ✗ | ✗ | ✗ | ✓ |
| Composite score | ✗ | ✗ | ✗ | ✓ |
| PDF report | ✗ | ✗ | ✓ | ✓ + white-label |
| JSON export | ✗ | ✗ | ✓ | ✓ |
| Proposals/month | 3 | Pay-per-use | Unlimited | Unlimited |
| API access | ✗ | ✗ | ✗ | ✓ |
| Team accounts | ✗ | ✗ | ✗ | ✓ (up to 10) |
| Batch analysis | ✗ | ✗ | ✗ | ✓ |

## Open-Core Model

- **CRUCIBLE** (this repo): MIT-licensed CLI tool. Full analysis engine, all detectors, all layers. Free forever.
- **TURTLESHELL** (SaaS product): Commercial web app at crucible.winniio.io. Tier-gated API access via server.py.
- The CLI is the gift. The SaaS is the business. Open source drives awareness → conversion to paid tiers.

## Competitive Landscape

| Competitor | What they do | Price | CRUCIBLE advantage |
|-----------|-------------|-------|-------------------|
| Grant consultants | Manual review | €5K-€15K | 100x cheaper, instant |
| CriteriaI | AI proposal writing | €99-€299/mo | We review, they generate (complementary) |
| EMDESK | Proposal management | €50-€200/mo | They manage, we evaluate quality |
| Cogrant | AI grant search + writing | €49-€199/mo | Different focus — we're the QA layer |
| Nothing | Most people just submit and pray | Free | That's why 85% fail |

## SEO Keywords (Priority Order)
1. "horizon europe proposal checker" — low competition, high intent
2. "eu grant proposal analyzer" — medium competition
3. "horizon europe proposal score" — very low competition
4. "eu funding proposal review" — medium competition
5. "horizon europe writing tips" — content play
6. "horizon europe common mistakes" — content play
7. "grant proposal quality checker" — broader market
8. "eu grant writing tool" — medium competition
9. "horizon europe evaluation criteria" — informational
10. "horizon europe proposal template" — top of funnel
