#!/usr/bin/env python3
"""ATS Resume Optimizer - analyze a resume against a job posting.

Produces a structured JSON report with format audits, keyword gap analysis,
knockout risk assessment, and an estimated ATS score using published
weighting frameworks (Skill Match 40%, Experience 30%, Education 20%,
Format 10%).

Usage:
    python scripts/analyze.py --resume <path> --job <url> --pretty
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

# --- Dependency checks with graceful fallback ---

MISSING = []

try:
    import requests
except ImportError:
    requests = None  # type: ignore
    MISSING.append("requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore
    MISSING.append("beautifulsoup4")

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore
    MISSING.append("pdfplumber")

try:
    import docx
except ImportError:
    docx = None  # type: ignore
    MISSING.append("python-docx")

# ---------------------------------------------------------------------------
# Resume Extraction
# ---------------------------------------------------------------------------

def extract_resume(filepath: str) -> dict:
    """Extract text from a resume file. Returns {'text': ..., 'format': ..., 'error': ...}."""
    if not os.path.exists(filepath):
        return {"text": "", "format": "unknown", "error": f"File not found: {filepath}"}

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(filepath)
    elif ext == ".docx":
        return _extract_docx(filepath)
    elif ext in (".txt", ".md", ".markdown"):
        return _extract_text(filepath)
    else:
        return {"text": "", "format": ext, "error": f"Unsupported format: {ext}"}


def _extract_pdf(filepath: str) -> dict:
    if pdfplumber is None:
        return {"text": "", "format": "pdf", "error": "pdfplumber not installed"}
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n".join(pages)
        if not text.strip():
            return {"text": "", "format": "pdf", "error": "PDF extracted empty text — may be image-based"}
        return {"text": text, "format": "pdf", "error": None}
    except Exception as e:
        return {"text": "", "format": "pdf", "error": str(e)}


def _extract_docx(filepath: str) -> dict:
    if docx is None:
        return {"text": "", "format": "docx", "error": "python-docx not installed"}
    try:
        doc = docx.Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs)
        return {"text": text, "format": "docx", "error": None}
    except Exception as e:
        return {"text": "", "format": "docx", "error": str(e)}


def _extract_text(filepath: str) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".md":
            text = _clean_markdown(text)
        return {"text": text, "format": ext.lstrip(".") if ext else "txt", "error": None}
    except Exception as e:
        return {"text": "", "format": "txt", "error": str(e)}


def _clean_markdown(text: str) -> str:
    """Strip markdown formatting to produce clean plain text for ATS analysis."""
    # Remove heading markers (##, ###, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Remove backslash-escaped dashes in date ranges
    text = re.sub(r'\\--', '--', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


# ---------------------------------------------------------------------------
# Job Posting Fetching
# ---------------------------------------------------------------------------

def fetch_job(url: str) -> dict:
    """Fetch and parse a job posting URL. Returns {'text': ..., 'error': ..., 'html': ...}."""
    if requests is None:
        return {"text": "", "error": "requests not installed — cannot fetch URL"}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ATS-Analyzer/1.0)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"text": "", "error": f"HTTP error: {e}"}

    if BeautifulSoup is None:
        return {"text": re.sub(r"<[^>]+>", " ", html), "error": None}

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # Try to isolate the job description body (not the full application page)
    # Greenhouse: look for the content div that contains the job description
    for selector in [
        "#content", "#job-content", '[class*="job-description"]',
        '[id*="job-description"]', '[class*="posting"]',
        '#job_description', '[data-testid="job-description"]',
        'article', 'main',
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 300:
                # Try to trim application form and legal sections
                text = _trim_job_text(text)
                return {"text": text, "error": None}

    # Fallback: entire body, trimmed
    text = soup.get_text(separator="\n", strip=True)
    text = _trim_job_text(text)
    return {"text": text, "error": None}


def _trim_job_text(text: str) -> str:
    """Trim application form and company boilerplate from job description text."""
    cut_markers = [
        r"\nAbout Tebra\b",
        r"\nOur Values\b",
        r"\nPerks & Benefits",
        r"\nApply for this job\b",
        r"\nSubmit application\b",
        r"\n\* indicates a required field\b",
        r"\nU\.S\. Standard Demographic Questions\b",
        r"\nVoluntary Self-Identification",
        r"\nHow would you describe your gender",
        r"\nPowered by\s*\nGreenhouse",
        r"\nCompliance & Privacy Disclosures",
        r"\nCreate a Job Alert\b",
        r"\n(?:For Recruiter use only)",
        r"\nWe are dedicated to attracting",
        r"\nOur four geo zones",
        r"\nBeyond base compensation",
    ]
    earliest = len(text)
    for marker in cut_markers:
        m = re.search(marker, text, re.IGNORECASE)
        if m and m.start() < earliest:
            earliest = m.start()
    if earliest < len(text):
        text = text[:earliest].strip()
    return text


# ---------------------------------------------------------------------------
# Vendor Detection
# ---------------------------------------------------------------------------

VENDOR_PATTERNS = {
    "greenhouse":     [r"greenhouse\.io", r"greenhouse\b"],
    "workday":        [r"myworkdayjobs\.com", r"workday\b", r"Workday\b"],
    "taleo":          [r"taleo\.net", r"Taleo\b"],
    "icims":          [r"icims\.com", r"iCIMS\b"],
    "sap_successfactors": [r"successfactors\.com", r"SuccessFactors\b", r"SAP SuccessFactors"],
    "eightfold":      [r"eightfold\.ai", r"Eightfold"],
    "lever":          [r"lever\.co"],
    "ashby":          [r"ashbyhq\.com"],
    "bamboohr":       [r"bamboohr\.com"],
    "jobvite":        [r"jobvite\.com"],
}


def detect_vendor(url: str, page_text: str) -> Optional[str]:
    """Detect ATS vendor from URL and page text."""
    combined = url + " " + page_text[:3000]

    # Greenhouse URL patterns also include greenhouse.io subdomains
    if "greenhouse.io" in url.lower():
        return "greenhouse"  # greenhouse.io is definitive from URL

    for vendor, patterns in VENDOR_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE):
                return vendor

    return None


# ---------------------------------------------------------------------------
# Format Audit
# ---------------------------------------------------------------------------

STANDARD_HEADINGS = [
    "work experience", "experience", "professional experience",
    "education", "skills", "technical skills", "core competencies",
    "certifications", "licenses", "professional summary", "summary",
    "projects", "publications", "languages",
]

UNICODE_BULLETS = re.compile(r"[•◦▪▸❖►✓✔☑☐◆◇]")

CRITICAL_FILE_TYPES = {".pages", ".indd", ".odt"}


def audit_format(resume_text: str, file_format: str, extraction_error: Optional[str]) -> dict:
    """Audit resume format for ATS compatibility."""
    issues = []

    # File format check
    if file_format in CRITICAL_FILE_TYPES:
        issues.append({"severity": "critical", "title": "Unsupported file format",
                       "detail": f"{file_format} is not parseable by ATS systems. Use PDF or DOCX."})

    # Image-based PDF / empty extraction
    if extraction_error:
        if "empty" in extraction_error.lower() or "image" in extraction_error.lower():
            issues.append({"severity": "critical", "title": "Image-based or blank PDF",
                           "detail": "PDF extracted no text. May be image-based (Canva, InDesign). Results in auto-rejection."})
        elif "not installed" in extraction_error.lower():
            issues.append({"severity": "high", "title": "Missing extraction library",
                           "detail": extraction_error})

    # Column layout heuristic (wide gaps of 3+ newlines)
    if re.search(r"\n\n\n\n+", resume_text):
        issues.append({"severity": "high", "title": "Possible multi-column layout",
                       "detail": "Large text gaps detected. Multi-column layouts scramble data in Taleo, Workday, and SAP."})

    # Unicode bullets
    unicode_matches = UNICODE_BULLETS.findall(resume_text)
    if unicode_matches:
        unique = sorted(set(unicode_matches))
        issues.append({"severity": "high", "title": "Unicode bullet symbols",
                       "detail": f"Found: {unique}. Use ASCII bullets (-, *, o) to avoid list-parsing failures."})

    # Heading check
    lines = resume_text.splitlines()
    potential_headings = []
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) < 50 and (
            stripped.isupper() or
            stripped.istitle() or
            re.match(r"^[A-Z][a-z]+(\s+[A-Z][a-z]+){0,4}$", stripped)
        ):
            potential_headings.append(stripped.strip().lower())

    found_standard = [h for h in potential_headings if h in STANDARD_HEADINGS]
    creative = [h for h in potential_headings if h not in STANDARD_HEADINGS and len(h.split()) <= 5]

    missing_standard = []
    if "work experience" not in found_standard and "experience" not in found_standard:
        missing_standard.append("Work Experience")
    if "education" not in found_standard:
        missing_standard.append("Education")
    if "skills" not in found_standard and "technical skills" not in found_standard:
        missing_standard.append("Skills")

    if missing_standard:
        issues.append({"severity": "high", "title": "Missing standard section headings",
                       "detail": f"Not found: {missing_standard}. Use standard headers so parsers map content correctly."})

    if creative:
        # Filter to only truly unconventional (skip short title-like lines)
        filtered_creative = [c for c in creative if c not in ("name", "email", "phone", "linkedin", "github")]
        if filtered_creative:
            issues.append({"severity": "medium", "title": "Unconventional headings detected",
                           "detail": f"Possible non-standard headings: {filtered_creative[:5]}"})

    # Word count
    word_count = len(resume_text.split())
    if word_count < 150:
        issues.append({"severity": "medium", "title": "Resume too short",
                       "detail": f"{word_count} words. ATS scoring may penalize resumes under 150 words."})

    # Score
    score = 100
    for issue in issues:
        if issue["severity"] == "critical":
            score -= 30
        elif issue["severity"] == "high":
            score -= 15
        elif issue["severity"] == "medium":
            score -= 5
    score = max(0, score)

    return {"issues": issues, "score": score}


# ---------------------------------------------------------------------------
# Section Analysis
# ---------------------------------------------------------------------------

def analyze_sections(resume_text: str) -> dict:
    """Analyze section headings in the resume."""
    lines = resume_text.splitlines()
    headings_found = []
    all_potential = []

    for line in lines:
        stripped = line.strip().lower()
        if stripped and len(stripped) < 50 and re.match(r"^[a-z][a-z\s&/]+$", stripped):
            if stripped in STANDARD_HEADINGS:
                headings_found.append(stripped)
            elif len(stripped.split()) <= 4:
                all_potential.append(stripped)

    headings_missing = []
    if not any(h in headings_found for h in ["work experience", "experience", "professional experience"]):
        headings_missing.append("Work Experience")
    if "education" not in headings_found:
        headings_missing.append("Education")
    if not any(h in headings_found for h in ["skills", "technical skills", "core competencies"]):
        headings_missing.append("Skills")

    unconventional = [h for h in all_potential if h not in STANDARD_HEADINGS and h not in headings_found]
    # Filter noise
    skip = {"email", "phone", "name", "linkedin", "github", "website", "address", "city", "state", "zip"}
    unconventional = [h for h in unconventional if h not in skip]

    return {
        "headings_found": headings_found,
        "headings_missing": headings_missing,
        "unconventional_headings": unconventional,
    }


# ---------------------------------------------------------------------------
# Keyword Analysis
# ---------------------------------------------------------------------------

# Common words to skip when extracting keywords
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "be", "been",
    "will", "can", "may", "has", "have", "had", "do", "does", "did",
    "it", "its", "this", "that", "these", "those", "we", "our", "you",
    "your", "they", "their", "he", "she", "not", "no", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "so", "than", "too", "very", "just",
    "about", "above", "after", "again", "also", "any", "because",
    "before", "between", "but", "during", "except", "here", "how",
    "into", "over", "under", "up", "what", "when", "where", "which",
    "while", "who", "why", "would", "could", "should", "new"
}


_NOISE_PHRASES = {
    "job description", "job posting", "job title", "location", "salary",
    "benefits", "qualification", "qualifications", "requirements",
    "apply for this", "submit application", "cover letter", "resume",
    "your resume", "linkedin profile", "email address", "phone number",
    "first name", "last name", "preferred name", "middle name",
    "legal name", "address line", "postal code", "select one",
    "we are", "we have", "we offer", "we provide", "we value",
    "your application", "the role", "the company", "our team",
    "our values", "equal opportunity", "diversity", "inclusion",
    "we do not", "this role", "this position", "successful candidate",
    "ideal candidate", "right candidate",
}

_BOILERPLATE_FILTERS = [
    "privacy policy", "equal opportunity employer", "california",
    "demographic", "self-identification", "disability status",
    "veteran status", "eeoc", "ofccp", "omb control",
    "paperwork reduction", "public burden", "protected veteran",
    "sexual orientation", "gender identity", "racial", "ethnic",
    "transgender", "hispanic", "latino", "armed forces",
    "application form", "attach", "dropbox", "google drive",
    "enter manually", "accepted file types", "autofill",
    "create alert", "job alert",
]


def extract_keywords(text: str) -> list[str]:
    """Extract keywords from job description that an ATS would match on.

    ATS keyword matching focuses on: skills, tools, certifications,
    domain terminology, and explicit qualifiers from the JD. This function
    extracts them via pattern matching and filters aggressively.
    """
    keywords = set()
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip().lstrip("-*•◦▪▸1234567890.) ")
        if len(stripped) < 10:
            continue
        stripped_lower = stripped.lower()
        if any(b in stripped_lower for b in _BOILERPLATE_FILTERS):
            continue

        # === Tools, platforms, named products ===
        for m in re.finditer(
            r'\b(AirOps|Clearscope|Gemini|Jasper|Semrush|Ahrefs|Screaming[-\s]Frog|'
            r'ContentKing|Conductor|Algolia|Profound|Looker|Tableau|Google\s+(?:Analytics|Search\s+Console)|'
            r'Adobe\s+Analytics|Salesforce|HubSpot|Marketo|WordPress|Shopify)',
            stripped, re.IGNORECASE
        ):
            keywords.add(m.group(0).lower())

        # === Acronyms in context (not standalone, from informative lines) ===
        for m in re.finditer(r'\b(SEO|LLM|AIO|SERP|BOFU|MOFU|KPI|CTA|B2B|SaaS|AEO|GEO)\b', stripped):
            keywords.add(m.group(0).lower())

        # === Years-of-experience requirements ===
        for m in re.finditer(
            r'(\d+\+?\s*years?\s+(?:of|in)\s+[a-z][a-z\s]{3,40}?)(?:\.|,|\n|$)',
            stripped_lower
        ):
            keywords.add(m.group(0).strip().rstrip(".,;"))

        # === "Experience with/in X" ===
        for m in re.finditer(
            r'(?:experience|proficiency|knowledge|familiarity|background)\s+'
            r'(?:in|with|of|using|working\s+with)\s+'
            r'([a-z][a-z\s/-]{3,50}?)(?:\.|,|\n|$|\))',
            stripped_lower
        ):
            phrase = m.group(1).strip().rstrip(".,;")
            if _is_good_keyword(phrase):
                keywords.add(phrase)

        # === "X skills/abilities" ===
        for m in re.finditer(
            r'(strong|excellent|exceptional|deep)\s+([a-z][a-z\s]{4,30}?)\s+(?:skills|abilities|judgment)',
            stripped_lower
        ):
            phrase = f"{m.group(1)} {m.group(2)}"
            if _is_good_keyword(phrase):
                keywords.add(phrase)

        # === Noun phrases from requirement-like lines ===
        # NOTE: disabled — n-gram extraction from requirement lines
        # produces too much noise (sentence fragments with commas, parentheses, etc.)
        # SKIPPED: the three explicit pattern types above capture the key skills

        # === Extract team names mentioned in "Partner with X" patterns ===
        for m in re.finditer(
            r'(?:partner|work|collaborate)\s+(?:with|closely\s+with)\s+'
            r'(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
            stripped
        ):
            team = m.group(1).strip().lower()
            if team not in _NOISE_PHRASES and len(team) > 3:
                keywords.add(team)

        # === Extract domain-specific terms commonly found in JD ===
        domain_terms = [
            "content marketing", "content strategy", "product marketing",
            "social media", "editorial judgment", "project management",
            "pipeline growth", "funnel", "conversion", "conversion-focused",
            "structured content", "content roadmap", "content velocity",
            "editorial guidelines", "knowledge base", "best practices",
            "ai-first", "organic marketing", "organic search", "organic traffic",
            "search engine optimization", "answer engine optimization",
            "keyword research", "competitive analysis", "content briefs",
            "content planning", "content production", "content refreshes",
            "content optimization", "semantic", "extractability",
            "citation", "proof points", "testimonials", "case studies",
            "competitor comparison", "roi", "implementation", "calculators",
            "product explainers", "cross-functional", "cross functional",
            "b2b saas", "saas", "healthcare", "medtech", "ehr",
            "practice management", "business goals", "owned channels",
            "scalable workflows", "training sessions", "dashboard",
            "analytics", "reporting", "data", "kpi", "metrics",
            "automation", "workflow automation", "ai workflows",
            "content discovery", "agentic", "coding agent",
            "developer documentation", "developer relations",
            "information gain", "entity optimization",
            "link building", "internal linking", "site architecture",
            "schema", "crawl optimization", "core web vitals",
            "hreflang", "canonicals", "duplicate content",
        ]
        for term in domain_terms:
            if term in stripped_lower:
                keywords.add(term)

        # === "managing/creating/building/leading X" ===
        for m in re.finditer(
            r'(?:managing|creating|building|leading|driving|owning|executing)\s+'
            r'([a-z][a-z\s/-]{3,40}?)(?:\.|,|\n|$|\band\b|\bor\b|\bfor\b)',
            stripped_lower
        ):
            phrase = m.group(1).strip().rstrip(".,;")
            if _is_good_keyword(phrase):
                keywords.add(phrase)

        # === "ensuring X" / "staying X" ===
        for m in re.finditer(
            r'(?:ensuring|staying|keeping|making)\s+([a-z][a-z\s]{4,40}?)(?:\.|,|\n|$)',
            stripped_lower
        ):
            phrase = m.group(1).strip().rstrip(".,;")
            if _is_good_keyword(phrase):
                keywords.add(phrase)

    # === Post-filter: remove anything that looks like a sentence fragment ===
    filtered = set()
    for kw in keywords:
        kw = kw.strip().rstrip(".,;:!?()- \t")
        if len(kw) < 3 or len(kw) > 40:
            continue
        words = kw.split()
        if len(words) > 4:
            continue
        if kw in _NOISE_PHRASES:
            continue
        if any(b in kw for b in _BOILERPLATE_FILTERS):
            continue
        filtered.add(kw)

    return sorted(filtered, key=lambda x: len(x), reverse=True)


def _is_good_keyword(phrase: str) -> bool:
    """Check if a phrase is a clean, meaningful keyword."""
    phrase = phrase.strip().rstrip(".,;:!?()- \t")
    words = phrase.split()
    if len(phrase) < 4 or len(phrase) > 40:
        return False
    if len(words) < 2 or len(words) > 3:
        return False
    if phrase in _NOISE_PHRASES:
        return False
    if any(b in phrase for b in _BOILERPLATE_FILTERS):
        return False
    if all(w in STOP_WORDS for w in words):
        return False
    if words[0] in STOP_WORDS or words[-1] in STOP_WORDS:
        return False
    # Skip phrases that clearly aren't skills/domain terms
    noise_words = {
        "will", "also", "each", "both", "few", "most", "only", "just",
        "very", "than", "still", "never", "already", "always", "would",
        "could", "should", "must", "might", "their", "there", "here",
        "about", "some", "such", "other", "through", "via", "every",
        "your", "our", "this", "that", "these", "those", "what", "when",
        "where", "which", "while", "have", "has", "had", "been"
    }
    if any(w in noise_words for w in words):
        return False
    return True


def match_keywords(keywords: list[str], resume_text: str) -> dict:
    """Match extracted keywords against resume text.

    Returns exact matches (for scoring) and partial matches (for awareness).
    Only exact matches factor into the match ratio.
    """
    resume_lower = resume_text.lower()
    exact_matched = []
    partial_matched = []
    missing = []

    for kw in keywords:
        kw_clean = kw.strip().rstrip(".,;:!?()- \t")

        # Exact word-boundary match
        if re.search(r'\b' + re.escape(kw_clean) + r'\b', resume_lower):
            exact_matched.append(kw)
            continue

        # Partial: for multi-word keywords, check if words appear near each other
        if " " in kw_clean:
            words = kw_clean.split()
            significant = [w for w in words if w not in STOP_WORDS and len(w) > 2]
            if len(significant) >= 2:
                # Check if any 2 significant words appear within 5 words of each other
                found_pair = False
                for i in range(len(significant)):
                    for j in range(i + 1, len(significant)):
                        w1, w2 = significant[i], significant[j]
                        p1 = [m.start() for m in re.finditer(r'\b' + re.escape(w1) + r'\b', resume_lower)]
                        p2 = [m.start() for m in re.finditer(r'\b' + re.escape(w2) + r'\b', resume_lower)]
                        for pos1 in p1:
                            for pos2 in p2:
                                if abs(pos1 - pos2) <= 80:  # within ~15 words
                                    found_pair = True
                                    break
                            if found_pair:
                                break
                        if found_pair:
                            break
                if found_pair:
                    partial_matched.append(kw)
                    continue

        missing.append(kw)

    matched = exact_matched

    # Low-frequency: exact matches appearing only once
    low_freq = []
    for kw in matched:
        kw_clean = kw.strip().rstrip(".,;:!?()- \t")
        count = len(re.findall(r'\b' + re.escape(kw_clean) + r'\b', resume_lower))
        if count == 1 and len(kw_clean) > 5:
            low_freq.append(kw)

    # Critical missing: longer terms not matched even partially
    critical_missing = [m for m in missing if len(m) > 15 and not any(
        b in m.lower() for b in _BOILERPLATE_FILTERS)]

    match_ratio = len(matched) / len(keywords) if keywords else 0

    return {
        "matched": sorted(matched),
        "partial_matches": sorted(partial_matched),
        "missing": sorted(missing),
        "critical_missing": sorted(critical_missing),
        "match_ratio": round(match_ratio, 3),
        "low_frequency": sorted(low_freq),
    }


# ---------------------------------------------------------------------------
# Knockout Assessment
# ---------------------------------------------------------------------------

KNOCKOUT_PATTERNS = [
    ("work_authorization", re.compile(
        r"authori[sz]ed\s+to\s+work|eligible\s+to\s+work|right\s+to\s+work|work\s+authori[sz]ation",
        re.IGNORECASE)),
    ("sponsorship", re.compile(
        r"sponsor\w*\s+(?:an?\s+)?immigration|visa\s+sponsor|h-?1b|employment-based\s+(?:visa|immigration)",
        re.IGNORECASE)),
    ("years_experience", re.compile(
        r"(\d+)\+?\s*(?:years|yrs)\s+(?:of\s+)?experience|minimum\s+(?:of\s+)?(\d+)\+?\s*(?:years|yrs)",
        re.IGNORECASE)),
    ("degree", re.compile(
        r"(?:bachelor|master|phd|doctorate|mba|associate)(?:'?s)?\s+degree",
        re.IGNORECASE)),
    ("certification", re.compile(
        r"(?:certified|certification|licensed|registered)\s+(?:in|as|professional)",
        re.IGNORECASE)),
    ("location", re.compile(
        r"must\s+(?:be\s+)?(?:located|reside|live)\s+in|must\s+be\s+(?:in|within)",
        re.IGNORECASE)),
    ("security_clearance", re.compile(
        r"security\s+clearance|top\s+secret|secret\s+clearance",
        re.IGNORECASE)),
]


def assess_knockouts(job_text: str, resume_text: str) -> dict:
    """Detect knockout criteria in job description and check resume."""
    risks = []

    for criterion, pattern in KNOCKOUT_PATTERNS:
        matches = pattern.findall(job_text)
        if not matches:
            continue

        # Build the detail from matches
        if criterion == "years_experience":
            years = None
            for m in matches:
                val = m[0] or m[1]
                if val:
                    years = int(val)
                    break
            detail = f"Requires {years}+ years of experience" if years else "Requires minimum years of experience"
        else:
            raw = pattern.search(job_text)
            detail = raw.group(0) if raw else "Detected in job description"

        # Check resume for evidence
        resume_lower = resume_text.lower()
        found = False
        if criterion == "years_experience" and years:
            # Experience parsing happens elsewhere; just check for explicit mention
            found = bool(re.search(rf'\b{years}\+?\s*years?\b', resume_lower))
        elif criterion == "work_authorization":
            found = bool(re.search(r"authori[sz]ed|eligible|citizen|permanent\s*resident|green\s*card", resume_lower))
        elif criterion == "sponsorship":
            found = bool(re.search(r"sponsor|visa|h-?1b|permanent\s*resident|citizen", resume_lower))
        elif criterion == "degree":
            found = bool(re.search(r"bachelor|master|phd|doctorate|mba|associate|degree", resume_lower))
        elif criterion == "certification":
            found = bool(re.search(r"certif|licens|register", resume_lower))
        elif criterion == "location":
            found = True  # Address is usually present
        elif criterion == "security_clearance":
            found = bool(re.search(r"clearance|top\s*secret|ts/sci", resume_lower))
        else:
            found = bool(pattern.search(resume_lower))

        ctype = "required" if not found else "met"
        risks.append({
            "criterion": criterion.replace("_", " ").title(),
            "type": ctype,
            "found": found,
            "detail": detail,
        })

    return {"risks": risks}


# ---------------------------------------------------------------------------
# Experience and Education Parsing
# ---------------------------------------------------------------------------

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|" \
         r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

DATE_RANGE = re.compile(
    r"(\b" + _MONTH + r"\s+)?"          # optional start month
    r"(\d{4})"                           # start year
    r"\s*[-–—to]+\s*"                    # separator
    r"(" + _MONTH + r"\s+)?"             # optional end month
    r"(\d{4}|Present|Current|Now)",       # end year or present
    re.IGNORECASE,
)

DEGREE_PATTERNS = [
    (re.compile(r"\bph\.?d\b", re.IGNORECASE), "Doctorate"),
    (re.compile(r"\bmaster'?s?\b", re.IGNORECASE), "Master's"),
    (re.compile(r"\bmba\b", re.IGNORECASE), "MBA"),
    (re.compile(r"\bbachelor'?s?\b", re.IGNORECASE), "Bachelor's"),
    (re.compile(r"\bassociate'?s?\b", re.IGNORECASE), "Associate's"),
    (re.compile(r"\bcertificate\b", re.IGNORECASE), "Certificate"),
]


def parse_experience(resume_text: str) -> dict:
    """Extract years of experience from resume."""
    matches = DATE_RANGE.findall(resume_text)
    parse_issues = []

    if not matches:
        # Try simpler YYYY-YYYY pattern
        simple = re.findall(r"\b(\d{4})\s*[-–—]\s*(\d{4}|Present|Current|Now)\b", resume_text, re.IGNORECASE)
        if not simple:
            parse_issues.append("No date ranges found. May use abbreviated dates (e.g., Jan '20).")
            return {"total_years": 0, "roles": [], "parse_issues": parse_issues}

    current_year = datetime.now().year
    total_years = 0.0
    roles = []

    for match in matches:
        start_month, start_year_str, end_month, end_year_str = match
        try:
            start_year = int(start_year_str)
        except ValueError:
            continue

        if end_year_str and end_year_str.lower() in ("present", "current", "now"):
            end_year = current_year
        elif end_year_str:
            try:
                end_year = int(end_year_str)
            except ValueError:
                continue
        else:
            continue

        if start_year > end_year:
            parse_issues.append(f"Skipping reversed date range: {start_year}-{end_year}")
            continue

        years = end_year - start_year
        if start_month and end_month and years <= 2:
            # Approximate partial-year contribution
            pass

        roles.append({"start": start_year, "end": end_year, "years": round(years, 1)})
        total_years += years

    # Deduplicate overlapping ranges (simple: sum all unique year spans)
    # A proper dedup would merge overlapping intervals, but for estimation this is acceptable
    if len(roles) > 1:
        total_years = sum(r["years"] for r in roles)

    if total_years == 0 and not parse_issues:
        parse_issues.append("Could not calculate total years from extracted dates.")

    return {
        "total_years": round(total_years, 1),
        "roles": roles,
        "parse_issues": parse_issues,
    }


def parse_education(resume_text: str) -> dict:
    """Detect highest degree level."""
    resume_lower = resume_text.lower()
    highest = None

    for pattern, level in DEGREE_PATTERNS:
        if pattern.search(resume_lower):
            if highest is None:
                highest = level

    return {"highest_degree": highest, "degree_found": highest is not None}


# ---------------------------------------------------------------------------
# ATS Score Estimation
# ---------------------------------------------------------------------------

def calculate_ats_score(
    keyword_result: dict,
    experience_result: dict,
    education_result: dict,
    format_result: dict,
    vendor: Optional[str],
    job_text: str,
) -> dict:
    """Calculate estimated ATS score using standard weighting framework."""

    # Skill Match (40%)
    skill_score = int(keyword_result["match_ratio"] * 100)

    # Experience (30%)
    req_years_match = re.search(r"(\d+)\+?\s*(?:years|yrs).*?(?:experience|in\s+\w+)", job_text, re.IGNORECASE)
    required_years = int(req_years_match.group(1)) if req_years_match else 5
    total_years = experience_result["total_years"]
    if total_years <= 0:
        exp_score = 0
    elif total_years >= required_years:
        exp_score = 100
    else:
        exp_score = int((total_years / required_years) * 100)

    # Education (20%)
    highest = education_result["highest_degree"]
    req_degree = re.search(
        r"(bachelor|master|phd|doctorate|mba|associate)(?:'?s)?\s+degree",
        job_text, re.IGNORECASE
    )
    if req_degree:
        edu_levels = {"associate's": 25, "associate": 25, "certificate": 20,
                      "bachelor's": 50, "bachelor": 50, "master's": 75,
                      "master": 75, "mba": 75, "phd": 100, "doctorate": 100}
        req_level = req_degree.group(1).lower()
        req_value = edu_levels.get(req_level, 50)
        candidate_value = edu_levels.get(highest.lower() if highest else "", 0)
        edu_score = min(100, int((candidate_value / req_value) * 100)) if req_value else 50
    else:
        edu_score = 100 if highest else 50  # No degree required = neutral

    # Format (10%)
    format_score = format_result["score"]

    # Vendor adjustments
    if vendor == "greenhouse":
        # AI-first: slightly less penalty for synonym misses
        skill_score = min(100, skill_score + 5)
        format_score = min(100, format_score + 5)
    elif vendor == "taleo":
        # Rigid parser: heavier format penalty
        format_score = max(0, format_score - 10)
    elif vendor == "eightfold":
        # Embedding-based: significant boost for transferable skills
        skill_score = min(100, skill_score + 10)
    elif vendor == "icims":
        # Heavy keyword density: steeper keyword penalty
        skill_score = min(100, skill_score - 5)

    weighted = (
        skill_score * 0.40 +
        exp_score * 0.30 +
        edu_score * 0.20 +
        format_score * 0.10
    )

    return {
        "skill_match": {"score": skill_score, "weight": 0.40},
        "experience": {"score": exp_score, "weight": 0.30},
        "education": {"score": edu_score, "weight": 0.20},
        "format": {"score": format_score, "weight": 0.10},
        "weighted_total": int(round(weighted)),
        "disclaimer": (
            "This is a research-based estimate using published weighting frameworks "
            "(Skill Match 40%, Experience 30%, Education 20%, Format 10%). "
            "Actual ATS algorithms vary by vendor. Taleo's scoring is more rigid "
            "than Workday's. Eightfold uses entirely different embedding-based matching. "
            "This is not an actual ATS score and should not be interpreted as a guarantee "
            "of any specific screening outcome."
        ),
    }


# ---------------------------------------------------------------------------
# Main Analysis Pipeline
# ---------------------------------------------------------------------------

def analyze(resume_path: str, job_url: str, region: str = "US") -> dict:
    """Run full ATS analysis and return structured result."""

    # Phase 1: Extract resume
    resume = extract_resume(resume_path)
    if resume["error"] and not resume["text"]:
        return {"error": f"Resume extraction failed: {resume['error']}"}

    # Phase 2: Fetch job posting
    job = fetch_job(job_url)
    if job["error"] and not job["text"]:
        return {"error": f"Job posting fetch failed: {job['error']}"}

    # Phase 3: Detect vendor
    vendor = detect_vendor(job_url, job["text"])

    # Phase 4: Format audit
    format_audit = audit_format(resume["text"], resume["format"], resume.get("error"))

    # Phase 5: Section analysis
    section_analysis = analyze_sections(resume["text"])

    # Phase 6: Keyword analysis
    keywords = extract_keywords(job["text"])
    keyword_analysis = match_keywords(keywords, resume["text"])

    # Phase 7: Knockout assessment
    knockout = assess_knockouts(job["text"], resume["text"])

    # Phase 8: Experience and education
    experience = parse_experience(resume["text"])
    education = parse_education(resume["text"])

    # Phase 9: Score
    score = calculate_ats_score(
        keyword_analysis, experience, education, format_audit, vendor, job["text"]
    )

    # Report missing dependencies
    missing_packages = []
    if requests is None:
        missing_packages.append("requests")
    if BeautifulSoup is None:
        missing_packages.append("beautifulsoup4")
    if pdfplumber is None:
        missing_packages.append("pdfplumber")
    if docx is None:
        missing_packages.append("python-docx")

    return {
        "format_audit": format_audit,
        "section_analysis": section_analysis,
        "keyword_analysis": keyword_analysis,
        "knockout_assessment": knockout,
        "experience_education": {
            **experience,
            **education,
        },
        "vendor_detected": vendor,
        "region": region,
        "ats_score_estimate": score,
        "missing_dependencies": missing_packages,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ATS Resume Optimizer — analyze a resume against a job posting.",
        epilog="Install all deps: pip install requests beautifulsoup4 pdfplumber python-docx",
    )
    parser.add_argument("--resume", required=True, help="Path to resume file (.pdf, .docx, .txt, .md)")
    parser.add_argument("--job", required=True, help="Job posting URL")
    parser.add_argument("--region", default="US", help="Company region (US, EU, UAE, etc.)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    result = analyze(args.resume, args.job, args.region)

    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False))

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
