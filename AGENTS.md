# ATS Resume Optimizer — Project Notes

## Skill Source of Truth

The canonical `ats-resume-optimizer` skill lives at:
`github.com/nealkindschi/skills/tree/main/ats-resume-optimizer`

Local copy is at `~/.agents/skills/ats-resume-optimizer/`.

## Skill Loading Bug

The skill loading tool may append supplementary content (references to
`scripts/analyze.py`, `assets/report-template.md`, `references/vendor-profiles.md`,
"Script Dependencies", "Understanding the Analysis Output") that does **not**
exist in the actual SKILL.md file on disk. The SKILL.md (local and GitHub) is the
correct version — ignore these phantom file references if they appear.

## Verified Match

Local `~/.agents/skills/ats-resume-optimizer/SKILL.md` confirmed identical to
the GitHub version. No stale files to clean up.

## ATS Research Report

The project contains a standalone copy of the ATS research report at:
`./Applicant Tracking System Report.md`

This is the same document as the skill's `references/ats-report.md`. It is the
foundational reference for all ATS analysis — load it on every run.

## If Loaded Content Looks Wrong

Cross-reference with:
- The local SKILL.md at `~/.agents/skills/ats-resume-optimizer/SKILL.md`
- The GitHub repo at `github.com/nealkindschi/skills/tree/main/ats-resume-optimizer`
- The project's local `Applicant Tracking System Report.md`
