---
name: ats-resume-optimizer
description: Compares a resume to a job posting and provides ATS optimization recommendations, applying parsing mechanics, knockout logic, vendor-specific strategies, and scoring frameworks from an embedded ATS research report. Use when the user says "ATS check," "optimize my resume for this job," "will my resume get past the ATS," "resume vs job description," "applicant tracking system," or provides a resume file and a job posting URL for comparison.
---

# ATS Resume Optimizer

Optimize a user's resume for a specific job posting using the full Applicant Tracking System research report (`./Applicant Tracking System Report.md`). Every recommendation or change must cite the relevant report section.

## Workflow

```
Progress:
- [ ] Phase 1: Gather inputs (resume, job posting URL, region, output preference)
- [ ] Phase 2: Research ATS vendor
- [ ] Phase 3: Five-dimension analysis
- [ ] Phase 3.5: User interview (if producing rewritten resume)
- [ ] Phase 4: Generate output(s)
```

### Phase 1: Gather Inputs

Ask the user for:

1. **Resume**: Accept PDF, DOCX, TXT, or markdown (`.md`) files. Read the file and extract all text.
2. **Job posting URL**: Fetch the URL with WebFetch to get the full job description text.
3. **Region**: Default to US. Ask: "Is the company based in the United States, or another region (EU, UAE, etc.)? Regional context can affect ATS keyword strategies." Load `../../regional-guide.md` if the user specifies a non-US region.
4. **Output preference**: Ask: "Which output would you like? (A) A recommendations document listing changes to make, (B) A rewritten/optimized resume, or (C) Both."

### Phase 2: Research ATS Vendor

Scan the job posting page for vendor indicators. Check:

- **URL patterns**: `myworkdayjobs.com`, `greenhouse.io`, `taleo.net`, `icims.com`, `successfactors.com`, `eightfold.ai`, `lever.co`, `ashbyhq.com`, `bamboohr.com`, `jobvite.com`
- **Page footer/text**: "Powered by Workday", "Powered by Greenhouse", Taleo branding, iCIMS copyright, SAP/SuccessFactors mentions
- **Application form**: Vendor-specific UI elements, domain redirects on "Apply" button

If a vendor is identified, load `../../vendor-guide.md` and read the relevant vendor profile. Apply vendor-specific strategies in Phase 3.

If no vendor is found, note this and apply general best practices from the report, which are valid across all major ATS platforms.

### Phase 3: Five-Dimension Analysis

Analyze the resume against the job description across these dimensions. For each finding, cite the relevant section of `./Applicant Tracking System Report.md`.

#### Dimension 1: Format Compliance

Check the resume for ATS parsing risks identified in the report (Section: Parsing Failure Modes and Structural Vulnerabilities):

- **Layout**: Is it single-column? Multi-column templates scramble data in Workday, Taleo, and SAP (report lines 25-37).
- **Fonts**: Are standard fonts used (Arial, Calibri, Times New Roman, Helvetica)? Non-standard typography fails extraction (report line 32).
- **Bullets**: Are simple ASCII bullets used (-, *, o)? Complex Unicode symbols break list-parsing arrays (report line 33).
- **Headings**: Are standard section headings used ("Work Experience", "Education", "Skills")? Unconventional headings fail section-recognition engines (report lines 34-35).
- **File format**: Is it a text-selectable PDF or DOCX? Image-based PDFs fail entirely — auto-rejection (report line 34).

Flag any violations with the specific remediation from the report's Parser Failure Mode table.

#### Dimension 2: Keyword Alignment

Apply the deterministic keyword-matching frameworks from the report (Section: Traditional Deterministic and Keyword-Based Models):

- Extract all hard skills, technical terms, certifications, and domain-specific acronyms from the job description.
- Cross-reference against the resume text. Flag every JD keyword absent from the resume.
- Score alignment using the skill-match ratio: matched skills / total JD skills (report lines 78-81).
- Identify high-value terms that appear only once — the report establishes that term frequency matters: "high-value keywords should appear multiple times across the document" (report line 196).
- Note: Verbatim vocabulary alignment is heavily rewarded. Synonyms and variant terminology are penalized (report line 13).

#### Dimension 3: Knockout Readiness

Apply prescreening logic gates from the report (Section: Prescreening Architectures and Knockout Logic):

- Identify likely knockout questions from the JD: work authorization, minimum years of experience, mandatory certifications/licenses, degree requirements, location requirements (report lines 45-49).
- Check the resume for explicit evidence addressing each likely knockout criterion.
- Flag criteria not visibly addressed in the resume — these trigger auto-disqualification with zero human review (report line 47).
- Distinguish Required vs. Asset criteria (report lines 52-59). JD terms like "must have", "required", "minimum" map to Required criteria. Terms like "preferred", "nice to have", "bonus" map to Asset criteria — missing Asset terms won't disqualify but will prevent top-tier ACE categorization (report line 58).

#### Dimension 4: Vendor-Specific Risks and Opportunities

If a vendor was identified in Phase 2, apply the corresponding profile from `../../vendor-guide.md`. Key gotchas by vendor:

- **Oracle Taleo**: Extremely rigid parser, two-column = instant failure, strict pattern-matching on section headings. Optimize for ACE categorization by hitting Asset criteria (report lines 56-58, 116-120).
- **Workday**: Uses skills intelligence and skills cloud. Include adjacent/related skills, not just exact matches. Structured interview scorecards — bullet point quality matters (report lines 122-128).
- **iCIMS**: Heavy keyword density and section-recognition engine. Role Fit ranking is per-job and strict. Favor exact term repetition across experience entries (report lines 132-136).
- **Greenhouse**: AI-first but assistive. Uses weighted calibrations and interview scorecards. Keyword Suggestions feature generates filters from the JD — mirror JD language precisely (report lines 138-147).
- **SAP SuccessFactors**: Often integrates with third-party AI (Sniper AI, Phenom, Paradox AI). Knockout questions may be delivered via chatbot before ATS engagement (report lines 150-153).
- **Eightfold AI**: Uses neural embeddings and deep learning. Synonyms and transferable skills are recognized. Quantified outcomes and methodologies matter more than exact keyword repetition (report lines 155-160).

If no vendor is identified, apply the general deterministic scoring framework.

#### Dimension 5: Regional Context

If the user specified a non-US region, load `../../regional-guide.md` and apply region-specific keyword strategies.

For US-based roles, ensure compliance keywords for regulated industries (finance, healthcare, defense) are present if applicable.

### Phase 3.5: User Interview (required for Option B or C)

**This step is mandatory before creating any rewritten resume.** If the user selected Option B or C, the interview must be completed first. Skipping it produces a resume padded with generic keyword insertions rather than authentic, interview-sourced detail.

Conduct a brief interview **before writing the resume**. This surfaces authentic details to close keyword gaps without fabrication.

For each **critical missing keyword** or **knockout gap** identified in Phase 3, ask targeted questions:

- **Experiences not on the resume**: "Have you done any work with [missing skill/domain] that isn't reflected here? Even adjacent exposure counts."
- **Metrics and outcomes**: "What was the measurable result of that project? Traffic, conversions, revenue, efficiency gains?"
- **Collaboration context**: "Which teams did you work with on that initiative? Product Marketing? Creative? Engineering?"
- **Industry exposure**: "Do you have any exposure to [industry, e.g., healthcare], even tangential — clients, side projects, personal interest?"
- **Tool experience**: "Have you used [missing tool]? Even casually or in a previous role?"

**Rules for the interview:**

- Ask one question at a time. Let the user answer before moving to the next.
- Stop after surfacing 3-5 new details — don't exhaust the user.
- Never lead the user toward a specific answer. Don't suggest experiences they didn't have.
- If the user says "no" to a question, move on. Do not revisit it.
- Document every new detail the user provides — these become the source material for the rewritten resume.

### Phase 4: Generate Output(s)

Based on the user's choice in Phase 1, produce one or both:

#### Option A: Recommendations Document

Generate a structured report with:

1. **Overall ATS compatibility score** (qualitative: High/Medium/Low pass probability)
2. **Format issues** — each with the specific parsing failure mode and remediation, citing report section
3. **Missing keywords** — ranked by importance, organized by category (skills, certifications, domain terms, soft skills)
4. **Knockout gaps** — criteria likely to trigger auto-rejection with suggested resume additions
5. **Vendor-specific recommendations** — tailored to the identified ATS platform
6. **Regional adjustments** — if applicable
7. **Priority action list** — top 5-10 changes in order of impact

Every recommendation must reference the specific report section or line number that supports it.

#### Option B: Rewritten Resume

**Prerequisite:** Complete the Phase 3.5 interview first.

Create a new file (never overwrite the original). The filename should be the original name with `-ats-optimized` appended before the extension (e.g., `resume.pdf` → `resume-ats-optimized.pdf`).

Apply all format fixes, keyword insertions, and knockout gap closures identified in Phase 3. **Use details surfaced in the Phase 3.5 interview** to close gaps with authentic content. Preserve the original content and structure as much as possible while:

- Ensuring single-column layout with standard headings
- Embedding missing keywords naturally into experience bullets, not as a keyword-stuffed list
- Adding explicit evidence for knockout criteria near the top of the resume (summary section, or first experience entry)
- Increasing keyword frequency for high-value terms across multiple sections
- Including quantified achievements for AI-first platforms (Eightfold, Greenhouse)
- **Weaving interview insights** into existing experience bullets — if the user mentioned a healthcare-adjacent project, add it to the relevant role; if they cited a metric not on the resume, add it

After writing, produce a summary of changes made, with each change citing the report justification.

## Critical Rules

- **NEVER modify or overwrite the original resume file.** Always create a new file.
- **Every recommendation or change must cite the specific report section** that justifies it (e.g., "Report Section: Parsing Failure Modes — Two-Column Templates").
- **Contextual embedding**: Never stuff keywords into a standalone list. Integrate them into experience bullets and the summary.
- **Preserve authenticity**: Do not fabricate skills, experiences, or credentials the candidate does not possess.
- **Avoid keyword stuffing**: Do not repeat the same keyword or phrase redundantly to inflate density. One strong, contextual mention in a relevant bullet outweighs three forced mentions. While ATS parsers do reward term frequency, keyword stuffing is detectable and degrades readability for the recruiter who reviews the resume after the ATS pass. Each keyword instance must arise naturally from the content of the bullet it appears in.

## Gotchas

- **PDFs may appear text-selectable but contain embedded images of text**: The Read tool extracts text, but if the result is garbled or empty, the PDF may be image-based — flag this as a critical parsing risk per report line 34.
- **Company uses multiple ATS vendors**: Large enterprises may use Workday for HCM and Greenhouse for recruiting. Prioritize the recruiting-specialized vendor (Greenhouse) over the HCM platform (Workday) for optimization strategy.
- **URL redirects**: Greenhouse-hosted career portals often redirect from the company's main domain. If the initial URL is a company page, follow the "Apply" link to detect the actual ATS.
- **Job postings behind login walls**: If the job posting is on LinkedIn or behind authentication, ask the user to paste the full job description text.
- **Region affects more than keywords**: EU companies operating under the EU AI Act may use different ATS configurations that emphasize transparent, explainable scoring over black-box ranking. ASEAN and Middle Eastern markets have distinct regulatory terminology requirements (see `../../regional-guide.md`).

## References

- **ATS Report (foundational)**: `./Applicant Tracking System Report.md` — the full research report. Load on every run.
- **Vendor Profiles**: `../../vendor-guide.md` — detailed ATS platform profiles. Load when a vendor is identified in Phase 2.
- **Scoring Math**: `../../scoring-math.md` — TF-IDF, cosine similarity, neural embeddings, and the skill-match equation. Load when the user asks about scoring mechanics or when producing a scored analysis.
- **Regional Guide**: `../../regional-guide.md` — region-specific keyword strategies and compliance frameworks. Load when the user specifies a non-US region.
- **Compliance & Bias**: `../../compliance.md` — EEOC, Four-Fifths Rule, NYC Local Law 144, EU AI Act. Load when the role is in a regulated industry or government.
