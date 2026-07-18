#!/usr/bin/env python3
"""
WhatsApp Forensic Evidence Timeline Analyzer
=============================================
Methodology draws from:
  - Evan Stark (2007) 'Coercive Control' — isolation, monitoring, micromanagement
  - M. Johnson (2008) 'A Typology of Domestic Violence' — pattern vs incident framing
  - LIWC (Linguistic Inquiry & Word Count) psycholinguistic categories
  - Duluth Power & Control Wheel — 8 abuse tactic dimensions
  - Home Office DASH Risk Indicator Checklist (SafeLives, 2009)
  - Crown Prosecution Service: 'Controlling or Coercive Behaviour' legal guidance (2015)
  - UK domestic abuse statutory framework (see LEGAL_FRAMEWORK below)

IMPORTANT DISCLAIMER:
  This tool flags patterns for human review. It does NOT make legal conclusions.
  All findings use 'could be evidence of…' framing. A solicitor or IDVA (Independent
  Domestic Violence Advocate) should review flagged content before any legal use.

Usage:
  python3 forensic_timeline.py --data <path_to_gdrive_json> [--output-dir ./output]

For scheduled re-runs (e.g. via GitHub Actions or cron):
  0 * * * * cd /path/to/repo && python3 forensic/forensic_timeline.py --data data/raw_export.json
"""

import json
import re
import csv
import os
import sys
import argparse
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
PHASES = [
    # (phase_id, label, start_date, end_date, description)
    ("PRE",  "Pre-cohabitation: Long-distance contact/courtship",
     datetime(2024,  7,  6),  datetime(2025,  7, 24)),
    ("P0",   "Phase 0: Cohabitation begins / Wedding (July–Sep 2025)",
     datetime(2025,  7, 25),  datetime(2025,  9, 30)),
    ("P1",   "Phase 1: Dependency begins (Oct–Nov 2025)",
     datetime(2025, 10,  1),  datetime(2025, 11, 30)),
    ("P2",   "Phase 2: Financial & emotional instability (Dec 2025)",
     datetime(2025, 12,  1),  datetime(2025, 12, 31)),
    ("P3",   "Phase 3: Crisis & third-party recognition (Jan 2026)",
     datetime(2026,  1,  1),  datetime(2026,  1, 31)),
    ("P4",   "Phase 4: Cycling / normalisation / separation signals (Feb–May 2026)",
     datetime(2026,  2,  1),  datetime(2026,  5, 31)),
    ("UNKNOWN", "Outside defined phases",
     datetime(1970,  1,  1),  datetime(2099, 12, 31)),
]

PHASE_NARRATIVE = {
    "PRE":  "During this period Henry re-initiated contact after a prior relationship. "
            "Messages from this phase establish the baseline dynamic, early red flags, "
            "and any patterns of love-bombing, future-faking, or boundary-testing.",
    "P0":   "Cady moved to the UK and into Henry's home (approx. 25 July 2025). "
            "The wedding took place 20 September 2025. This phase captures the transition "
            "from remote romance to cohabitation, any escalation in control, and the "
            "marriage context — relevant to spouse visa eligibility and any duress claims.",
    "P1":   "Post-wedding. Financial and immigration dependency likely increases. "
            "Watch for isolation from support networks, financial control, housing dependency.",
    "P2":   "Financial stress messages peak. Economic abuse patterns may crystallise here.",
    "P3":   "Messages in this phase may show third-party witnesses (friends, family) "
            "recognising warning signs, requests for help or safety planning.",
    "P4":   "Classic 'cycle of abuse' patterns: tension → incident → reconciliation → calm. "
            "Separation signals (threats of divorce, visa references, housing threats) "
            "are legally significant.",
}

# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD TAG CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
TAG_KEYWORDS = {
    "HENRY_DIRECT": [
        "henry",
    ],
    "MARRIAGE_WEDDING": [
        "wedding", "married", "marriage", "husband", "wife",
        "fiancé", "fiance", "fiancee", "register office",
        "ceremony", "vows", "ring", "honeymoon",
    ],
    "IMMIGRATION_VISA": [
        "visa", "passport", "immigration", "home office", "ilr",
        "right to work", "uk passport", "spouse visa", "leave to remain",
        "settled status", "biometric", "brp", "ukvi", "border",
    ],
    "HOUSING_HOME": [
        "house", "home", "room", "kicked out", "locked out",
        "move out", "moving out", "rent", "mortgage", "homeless",
        "evict", "lease", "tenancy", "landlord", "sofa", "nowhere to go",
        "my flat", "his flat", "the flat",
    ],
    "FINANCIAL": [
        "money", "cash", "bills", "debt", "tax", "taxes",
        "mortgage", "work", "job", "paid", "rent", "£", "$",
        "bank", "account", "transfer", "afford", "broke", "owe",
        "salary", "income", "expense",
    ],
    "ANGER_THREAT": [
        "anger", "angry", "furious", "explode", "exploding", "yell",
        "shouting", "scream", "screaming", "yelling", "fight",
        "threat", "threaten", "divorce", "leave", "kick me out",
        "kick you out", "end this", "over", "done with", "aggressive",
        "rage", "violence", "violent", "hit", "grabbed", "pushed",
    ],
    "SAFETY_DISTRESS": [
        "safe", "unsafe", "scared", "afraid", "frightened", "fear",
        "anxiety", "anxious", "panic", "panic attack", "cry", "cried",
        "crying", "vomiting", "vomit", "distress", "can't eat", "cant eat",
        "can't sleep", "cant sleep", "not eating", "not sleeping",
        "numb", "shaking", "trembling", "overwhelmed", "broken",
        "suicid", "self harm", "hurt myself",
    ],
    "SEXUAL_BOUNDARY": [
        "condom", "protection", "sti", "std", "chlamydia", "sex",
        "without protection", "consent", "aftercare", "reproductive",
        "contraception", "pill", "iud", "coerc",
        "henry's",  # possessive framing of the user's body
    ],
    "NATHAN_CONCERN": [
        "worried", "concerned", "are you okay", "are you safe",
        "i'm here", "im here", "i am here", "here for you",
        "checking on", "check on you", "reached out", "red flag",
        "that worries me", "that concerns me", "scared for you",
        "be careful", "watch out",
    ],
    "SUPPORT_WITNESS": [
        "here if you need", "anything you need", "don't hesitate",
        "support you", "toxic", "abuse", "pattern", "controlling",
        "coercive", "gaslighting", "manipulat", "narciss",
        "refuge", "shelter", "helpline", "police", "solicitor",
        "lawyer", "legal", "court", "wow", "that's not okay",
        "that is not okay", "not normal", "not right",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# FORENSIC-LINGUISTIC PATTERNS (beyond keyword matching)
# Based on Stark (2007), Johnson (2008), LIWC, Duluth model
# ─────────────────────────────────────────────────────────────────────────────
FORENSIC_PATTERNS = {
    "FL_MINIMISATION": re.compile(
        r"\b(just|only|a bit|merely|nothing|not a big deal|overreact|"
        r"too sensitive|so sensitive|dramatic|being dramatic)\b",
        re.IGNORECASE),
    "FL_BLAME_SHIFT": re.compile(
        r"\b(your fault|you made me|if you hadn.t|because of you|"
        r"you caused|you started|look what you|made me do)\b",
        re.IGNORECASE),
    "FL_ISOLATION": re.compile(
        r"\b(no one else|nobody else|alone|just us|only me|only you|"
        r"cut off|don.t need|no friends|without me)\b",
        re.IGNORECASE),
    "FL_FUTURE_FAKING": re.compile(
        r"\b(one day|when we|someday|eventually|in the future|"
        r"we.ll|we will|our home|our life|our future|our kids|"
        r"our children|our family)\b",
        re.IGNORECASE),
    "FL_LOVE_BOMBING": re.compile(
        r"\b(amazing|incredible|perfect|soulmate|never met anyone like|"
        r"unique|so special|never felt this|lucky to have you|"
        r"you.re everything|my whole world|you.re my)\b",
        re.IGNORECASE),
    "FL_GASLIGHTING": re.compile(
        r"\b(that never happened|you.re imagining|not what i said|"
        r"you remember wrong|you.re crazy|you.re insane|"
        r"that.s not what|i never said)\b",
        re.IGNORECASE),
    "FL_DARVO": re.compile(
        r"\b(i.m the victim|you.re hurting me|look what you.ve done|"
        r"i can.t believe you|after everything i.ve done|"
        r"i do everything for you|i give you everything)\b",
        re.IGNORECASE),
    "FL_MONITORING": re.compile(
        r"\b(where are you|where were you|who are you with|"
        r"who were you with|why didn.t you answer|why didn.t you reply|"
        r"you didn.t pick up|i called you|been trying to reach|"
        r"why are you|what are you doing)\b",
        re.IGNORECASE),
}

# ─────────────────────────────────────────────────────────────────────────────
# UK LEGAL FRAMEWORK COLUMN
# ─────────────────────────────────────────────────────────────────────────────
LEGAL_FRAMEWORK = {
    "HENRY_DIRECT": (
        "Speaker identification only — no standalone legal significance. "
        "Messages from Henry may constitute direct evidence of his conduct."
    ),
    "MARRIAGE_WEDDING": (
        "Marriage Act 1949 (validity of marriage); Matrimonial Causes Act 1973 s.12(c) "
        "(voidable if consent was obtained by duress or mistake); "
        "Immigration Rules Appendix FM — 'sham marriage' or 'marriage of convenience' "
        "investigations by Home Office; R v R [1991] (marital rape abolition — consent "
        "required at all times in marriage)."
    ),
    "IMMIGRATION_VISA": (
        "Immigration Act 1971 / Immigration Rules: Cady's right to remain is linked "
        "to the marriage while on a spouse visa. If Henry threatens to report to UKVI "
        "or withholds immigration support, this could constitute: "
        "(1) Coercive control — Serious Crime Act 2015 s.76; "
        "(2) Economic/immigration abuse — Domestic Abuse Act 2021 s.1(4); "
        "Destitute Domestic Violence Concession (DDVC) / Migrant Victims of Domestic "
        "Abuse Concession (MVDAC) may allow Cady to access public funds while seeking "
        "leave outside the rules."
    ),
    "HOUSING_HOME": (
        "Domestic Abuse Act 2021 s.1(4) — economic abuse includes 'withholding, "
        "controlling or misusing resources needed to maintain a home'; "
        "Family Law Act 1996 Part IV — occupation order application; "
        "Serious Crime Act 2015 s.76 — controlling access to accommodation is a "
        "recognised tactic of coercive control; "
        "Housing Act 1996 s.177 — fleeing domestic abuse counts as not having "
        "'reasonable to occupy' previous accommodation (homelessness duty)."
    ),
    "FINANCIAL": (
        "Domestic Abuse Act 2021 s.1(4) — economic abuse: 'behaviour that has a "
        "substantial adverse effect on the victim's ability to acquire, use or maintain "
        "money or other property'; "
        "Serious Crime Act 2015 s.76 — financial control as coercive behaviour; "
        "Welfare Reform Act 2012 — Universal Credit domestic violence easements; "
        "Council Tax / benefit implications of forced separation."
    ),
    "ANGER_THREAT": (
        "Serious Crime Act 2015 s.76 — coercive/controlling behaviour (max 5 years); "
        "Protection from Harassment Act 1997 — course of conduct causing fear of "
        "violence (s.4, max 5 years); "
        "Public Order Act 1986 s.4 / s.4A — threatening, abusive or insulting behaviour; "
        "Criminal Justice Act 1988 s.39 — common assault; "
        "Crown Prosecution Service guidance: a pattern of threatening behaviour even "
        "without physical contact can satisfy s.76."
    ),
    "SAFETY_DISTRESS": (
        "Evidence of psychological harm is central to Domestic Abuse Act 2021 s.1(3) "
        "(domestic abuse includes psychological, emotional, economic abuse); "
        "DASH Risk Indicator Checklist — distress symptoms are high-risk indicators; "
        "Medical records of anxiety/physical symptoms corroborate victim's account; "
        "R v Dhaliwal [2006] — psychological injury is bodily harm for assault purposes."
    ),
    "SEXUAL_BOUNDARY": (
        "Sexual Offences Act 2003 s.74 — consent must be 'freely given'; s.76 — "
        "intentional deception as to the nature of an act removes consent; "
        "Condom removal ('stealthing') — R v Lawrence [2020] established this can "
        "vitiate consent; "
        "Reproductive coercion — recognised as coercive control under SCA 2015 s.76; "
        "R v R [1991] — no marital exemption from rape or sexual assault."
    ),
    "NATHAN_CONCERN": (
        "Third-party witness corroboration is admissible and can strengthen the "
        "victim's account (Criminal Justice Act 2003 s.114 — hearsay exceptions); "
        "A contemporaneous record of a third party expressing concern is a "
        "significant credibility indicator; "
        "Supports pattern evidence under CJA 2003 s.101(1)(d) (bad character)."
    ),
    "SUPPORT_WITNESS": (
        "Contemporaneous records from friends/family constitute 'res gestae' or "
        "hearsay admissible under CJA 2003 s.114; "
        "MARAC (Multi-Agency Risk Assessment Conference) referral indicators; "
        "IDVA (Independent Domestic Violence Adviser) notes are admissible; "
        "Clare's Law (Domestic Violence Disclosure Scheme) — right to ask police "
        "about a partner's history."
    ),
    "FL_MINIMISATION": (
        "Minimisation language by perpetrator is a recognised tactic documented in "
        "Evan Stark 'Coercive Control' (2007) and in CPS prosecutorial guidance; "
        "A pattern of minimising abuse incidents supports the coercive control "
        "element of SCA 2015 s.76."
    ),
    "FL_BLAME_SHIFT": (
        "Blame-shifting is documented as a Duluth Power & Control tactic and DARVO "
        "(Deny, Attack, Reverse Victim and Offender) strategy; "
        "Relevant to credibility assessment and establishing perpetrator's intent."
    ),
    "FL_ISOLATION": (
        "Isolation from support networks is a core element of SCA 2015 s.76 coercive "
        "control and is listed in Home Office statutory guidance on the Act."
    ),
    "FL_FUTURE_FAKING": (
        "Future-faking (false promises to maintain control) is consistent with "
        "psychological manipulation as documented in academic IPV literature; "
        "May support a pattern of deception relevant to any duress/undue influence "
        "claim in matrimonial proceedings."
    ),
    "FL_LOVE_BOMBING": (
        "Intense early affection followed by control is the classic 'grooming' "
        "pattern documented in IPV research (M. Johnson 2008); "
        "Relevant to establishing the relationship's psychological context for court."
    ),
    "FL_GASLIGHTING": (
        "Gaslighting (causing a victim to doubt their own perception) is recognised "
        "as psychological abuse under DA Act 2021 s.1(3) and coercive control "
        "under SCA 2015 s.76."
    ),
    "FL_DARVO": (
        "DARVO is a documented perpetrator strategy; court guidance acknowledges "
        "that perpetrators frequently present as victims (CPS DA policy 2023)."
    ),
    "FL_MONITORING": (
        "Constant monitoring/location-checking is a named coercive control indicator "
        "in the Home Office SCA 2015 statutory guidance and DASH checklist."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# NEEDS_EXTRA_REVIEW FLAGS
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_PATTERNS = re.compile(
    r"\b(divorce|visa|passport|kicked out|kick.*out|locked out|unsafe|scared|"
    r"threat(?:en)?|violence|violent|yelling|screaming|coercive|abus(?:e|ing)|"
    r"control(?:ling)?|home office|suicid|self.harm|hurt myself|"
    r"anger|aggressive|aggression|rape|assault|hit me|punch|"
    r"nowhere to go|leave me|leave you|homeless|destitute)\b",
    re.IGNORECASE,
)

CONTEXT_WINDOW = 5  # messages before and after

# ─────────────────────────────────────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_messages(content: str) -> list[dict]:
    """
    Parse WhatsApp messages from Google Sheets markdown-table export.
    Format per row: | \[MM/DD/YY, H:MM:SS<NNBSP>am/pm\] Speaker: message |
    Returns list of dicts sorted chronologically.
    """
    rows = content.split("\n")
    msg_rows = [r.strip() for r in rows if r.strip().startswith("| \\[")]

    # Regex: \[date, time<NNBSP or space>am/pm\] Speaker: message |
    pat = re.compile(
        r"\| \\\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d+:\d+:\d+)[\s ]+([ap]m)\\\]\s+"
        r"([^:|]+):\s*(.*?)\s*\|$",
        re.IGNORECASE,
    )

    messages = []
    for idx, row in enumerate(msg_rows):
        m = pat.match(row)
        if not m:
            continue
        date_str, time_str, ampm, speaker, text = m.groups()
        speaker = speaker.strip()
        text = text.strip()

        # Skip system messages
        if "‎" in text and ("encrypted" in text.lower() or "changed" in text.lower()
                                  or "added" in text.lower()):
            continue
        # Clean invisible chars
        text = text.replace("‎", "").replace(" ", " ").strip()

        # Parse datetime — WhatsApp iOS exports in MM/DD/YY format
        try:
            dt = datetime.strptime(f"{date_str} {time_str} {ampm.upper()}", "%m/%d/%y %I:%M:%S %p")
        except ValueError:
            try:
                dt = datetime.strptime(f"{date_str} {time_str} {ampm.upper()}", "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                continue

        messages.append({
            "message_id":    f"MSG_{len(messages):05d}",
            "datetime":      dt,
            "date":          dt.strftime("%Y-%m-%d"),
            "time":          dt.strftime("%H:%M:%S"),
            "speaker":       speaker,
            "message_text":  text,
        })

    # Sort chronologically (file has multiple sheets in non-date order)
    messages.sort(key=lambda x: x["datetime"])

    # Re-assign stable sequential IDs after sort
    for i, msg in enumerate(messages):
        msg["message_id"] = f"MSG_{i:05d}"

    return messages


# ─────────────────────────────────────────────────────────────────────────────
# PHASE ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

def assign_phase(dt: datetime) -> tuple[str, str]:
    for phase_id, label, start, end in PHASES:
        if start <= dt <= end:
            return phase_id, label
    return "UNKNOWN", "Outside defined phases"


# ─────────────────────────────────────────────────────────────────────────────
# TAGGING
# ─────────────────────────────────────────────────────────────────────────────

def tag_message(text: str) -> tuple[list[str], list[str]]:
    """
    Returns (keyword_tags, forensic_pattern_tags).
    """
    tl = text.lower()
    ktags = []
    for cat, keywords in TAG_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in tl:
                ktags.append(cat)
                break

    ftags = []
    for pat_name, pattern in FORENSIC_PATTERNS.items():
        if pattern.search(text):
            ftags.append(pat_name)

    return ktags, ftags


def needs_review(text: str) -> bool:
    return bool(REVIEW_PATTERNS.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# BUILD LEGAL ANNOTATION
# ─────────────────────────────────────────────────────────────────────────────

def build_legal_note(tags: list[str], ftags: list[str]) -> str:
    all_tags = tags + ftags
    notes = []
    seen = set()
    for tag in all_tags:
        if tag in LEGAL_FRAMEWORK and tag not in seen:
            notes.append(f"[{tag}] {LEGAL_FRAMEWORK[tag]}")
            seen.add(tag)
    return " || ".join(notes) if notes else "No specific flag — general context"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyse(messages: list[dict]) -> list[dict]:
    """Annotate every message with phase, tags, review flag, and legal note."""
    annotated = []
    for msg in messages:
        phase_id, phase_label = assign_phase(msg["datetime"])
        ktags, ftags = tag_message(msg["message_text"])
        all_tags = ktags + ftags
        review = needs_review(msg["message_text"])
        legal = build_legal_note(ktags, ftags)

        annotated.append({
            **msg,
            "phase_id":          phase_id,
            "phase_label":       phase_label,
            "tags":              "|".join(all_tags),
            "keyword_tags":      "|".join(ktags),
            "forensic_ling_tags": "|".join(ftags),
            "tag_count":         len(all_tags),
            "needs_extra_review": "YES" if review else "",
            "legal_framework":   legal,
        })
    return annotated


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT WINDOWS
# ─────────────────────────────────────────────────────────────────────────────

def build_context_rows(annotated: list[dict]) -> list[dict]:
    """
    For every tagged message, return it with CONTEXT_WINDOW messages before/after,
    each row labelled as BEFORE / TARGET / AFTER.
    """
    tagged_indices = [i for i, m in enumerate(annotated) if m["tag_count"] > 0]
    seen_ids = set()
    ctx_rows = []

    for ti in tagged_indices:
        lo = max(0, ti - CONTEXT_WINDOW)
        hi = min(len(annotated) - 1, ti + CONTEXT_WINDOW)
        for j in range(lo, hi + 1):
            msg = annotated[j]
            uid = (ti, msg["message_id"])
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            role = "TARGET" if j == ti else ("BEFORE" if j < ti else "AFTER")
            ctx_rows.append({
                **msg,
                "context_role":   role,
                "target_msg_id":  annotated[ti]["message_id"],
            })

    return ctx_rows


# ─────────────────────────────────────────────────────────────────────────────
# MONTHLY TAG COUNTS
# ─────────────────────────────────────────────────────────────────────────────

def monthly_counts(annotated: list[dict]) -> list[dict]:
    counts: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))
    all_tag_names = list(TAG_KEYWORDS.keys()) + list(FORENSIC_PATTERNS.keys())

    for msg in annotated:
        ym = msg["date"][:7]  # YYYY-MM
        for tag in msg["tags"].split("|"):
            if tag:
                counts[ym][tag] += 1
        counts[ym]["_TOTAL_MESSAGES"] += 1
        if msg["needs_extra_review"]:
            counts[ym]["_NEEDS_REVIEW"] += 1

    rows = []
    for ym in sorted(counts.keys()):
        row = {"year_month": ym}
        for tag in all_tag_names + ["_TOTAL_MESSAGES", "_NEEDS_REVIEW"]:
            row[tag] = counts[ym].get(tag, 0)
        rows.append(row)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# POSSIBLE TIMELINE EVENTS MARKDOWN
# ─────────────────────────────────────────────────────────────────────────────

LEGAL_CAVEAT = """
> **LEGAL CAVEAT**: This document is a working analytical tool, not a legal submission.
> All language uses 'could be evidence of…' framing. Nothing here constitutes legal advice.
> Consult a specialist domestic abuse solicitor or IDVA before using this in any proceedings.
> Relevant support: **National Domestic Abuse Helpline 0808 2000 247** (free, 24/7).
> **Southall Black Sisters** (immigration & DA): 020 8571 0800.
> **Refuge** immigration project: 0808 2000 247.
"""

def build_markdown(annotated: list[dict]) -> str:
    lines = ["# Forensic Evidence Timeline", ""]
    lines.append(LEGAL_CAVEAT)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary stats
    total = len(annotated)
    tagged = sum(1 for m in annotated if m["tag_count"] > 0)
    review = sum(1 for m in annotated if m["needs_extra_review"])
    henry_msgs = sum(1 for m in annotated if m["speaker"] == "Henry Woods")
    cady_msgs = sum(1 for m in annotated if m["speaker"] == "Cady")

    lines.append("## Overview")
    lines.append("")
    lines.append(f"| Stat | Value |")
    lines.append(f"|------|-------|")
    lines.append(f"| Total messages | {total:,} |")
    lines.append(f"| Messages from Henry Woods | {henry_msgs:,} |")
    lines.append(f"| Messages from Cady | {cady_msgs:,} |")
    lines.append(f"| Tagged messages (any tag) | {tagged:,} ({100*tagged//total}%) |")
    lines.append(f"| NEEDS_EXTRA_REVIEW | {review:,} |")
    lines.append(f"| Date range | {annotated[0]['date']} → {annotated[-1]['date']} |")
    lines.append("")

    # Per-phase sections
    for phase_id, phase_label, phase_start, phase_end in PHASES:
        if phase_id == "UNKNOWN":
            continue

        phase_msgs = [m for m in annotated
                      if m["phase_id"] == phase_id and m["tag_count"] > 0]
        if not phase_msgs:
            continue

        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## {phase_label}")
        lines.append(f"")
        lines.append(f"*{PHASE_NARRATIVE.get(phase_id, '')}*")
        lines.append(f"")

        # Tag summary for this phase
        phase_all = [m for m in annotated if m["phase_id"] == phase_id]
        tag_freq: dict[str, int] = defaultdict(int)
        for m in phase_all:
            for t in m["tags"].split("|"):
                if t:
                    tag_freq[t] += 1

        if tag_freq:
            lines.append(f"**Tag frequency in this phase:**")
            lines.append(f"")
            lines.append(f"| Tag | Count |")
            lines.append(f"|-----|-------|")
            for tag, cnt in sorted(tag_freq.items(), key=lambda x: -x[1]):
                lines.append(f"| {tag} | {cnt} |")
            lines.append(f"")

        # Highlight high-priority messages
        high_pri = [m for m in phase_msgs
                    if m["needs_extra_review"] or m["tag_count"] >= 2]
        if high_pri:
            lines.append(f"### Key Flagged Messages (NEEDS REVIEW or multi-tagged)")
            lines.append(f"")
            for msg in high_pri[:40]:  # cap at 40 per phase to keep readable
                speaker_fmt = f"**{msg['speaker']}**"
                lines.append(f"#### {msg['date']} {msg['time']} — {speaker_fmt}")
                lines.append(f"")
                # Escape pipe chars in message text for markdown tables
                safe_text = msg["message_text"].replace("|", "\\|")
                lines.append(f"> {safe_text}")
                lines.append(f"")
                lines.append(f"- **Tags**: `{msg['tags']}`")
                lines.append(f"- **Message ID**: `{msg['message_id']}`")
                if msg["needs_extra_review"]:
                    lines.append(f"- **⚠ NEEDS EXTRA REVIEW**")
                lines.append(f"- **Legal framework**: {msg['legal_framework']}")
                lines.append(f"")

    # Methodology section
    lines.append("---")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Tags are applied by keyword matching and forensic-linguistic pattern "
        "recognition. The approach draws from:\n\n"
        "- **Evan Stark (2007)** *Coercive Control* — patterns of isolation, "
        "monitoring, micro-management\n"
        "- **M. Johnson (2008)** *A Typology of Domestic Violence* — distinguishing "
        "incident-based from pattern-based violence\n"
        "- **Duluth Power & Control Wheel** — eight coercive tactic categories\n"
        "- **LIWC (Linguistic Inquiry & Word Count)** — psycholinguistic word categories\n"
        "- **Home Office DASH Risk Indicator Checklist** (SafeLives, 2009)\n"
        "- **CPS guidance on Controlling or Coercive Behaviour** (2015, updated 2023)\n"
        "- **DARVO** (Deny, Attack, Reverse Victim and Offender — Freyd 1997)\n"
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CSV EXPORT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

ALL_MSG_FIELDS = [
    "message_id", "datetime", "date", "time", "speaker", "message_text",
    "phase_id", "phase_label", "tags", "keyword_tags", "forensic_ling_tags",
    "tag_count", "needs_extra_review", "legal_framework",
]

CTX_FIELDS = ALL_MSG_FIELDS + ["context_role", "target_msg_id"]


def write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Wrote {len(rows):,} rows → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="WhatsApp Forensic Timeline Analyzer")
    ap.add_argument("--data", required=True,
                    help="Path to Google Drive JSON export (fileContent field)")
    ap.add_argument("--output-dir", default="forensic/output",
                    help="Directory for output files (default: forensic/output)")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[1/6] Loading data from {args.data}...")
    with open(args.data, encoding="utf-8") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
        content = data.get("fileContent", raw)
    except json.JSONDecodeError:
        content = raw

    print("[2/6] Parsing messages...")
    messages = parse_messages(content)
    print(f"      → {len(messages):,} messages parsed, "
          f"{messages[0]['date']} to {messages[-1]['date']}")

    print("[3/6] Tagging and annotating...")
    annotated = analyse(messages)
    tagged_count = sum(1 for m in annotated if m["tag_count"] > 0)
    review_count = sum(1 for m in annotated if m["needs_extra_review"])
    print(f"      → {tagged_count:,} tagged, {review_count:,} NEEDS_EXTRA_REVIEW")

    print("[4/6] Building context windows...")
    ctx_rows = build_context_rows(annotated)

    print("[5/6] Computing monthly tag counts...")
    monthly = monthly_counts(annotated)

    print("[6/6] Writing outputs...")

    out = args.output_dir
    write_csv(f"{out}/all_messages_tagged.csv", annotated, ALL_MSG_FIELDS)

    tagged_only = [m for m in ctx_rows if m["context_role"] == "TARGET"]
    print(f"      Context rows: {len(ctx_rows):,} (from {len(tagged_only):,} target messages)")
    write_csv(f"{out}/tagged_hits_with_context.csv", ctx_rows, CTX_FIELDS)

    monthly_fields = (["year_month"]
                      + list(TAG_KEYWORDS.keys())
                      + list(FORENSIC_PATTERNS.keys())
                      + ["_TOTAL_MESSAGES", "_NEEDS_REVIEW"])
    write_csv(f"{out}/monthly_tag_counts.csv", monthly, monthly_fields)

    md_path = f"{out}/possible_timeline_events.md"
    md = build_markdown(annotated)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  Wrote timeline → {md_path}")

    print("\nDone. Review output files in:", out)


if __name__ == "__main__":
    main()
