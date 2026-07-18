#!/usr/bin/env python3
"""
WhatsApp Forensic Corpus Analyzer — Version 2
==============================================
Expert methodology: Evan Stark 'Coercive Control' (2007), Duluth Power & Control
Wheel, LIWC, DARVO (Freyd 1997), M. Johnson (2008), SafeLives DASH, CPS CC guidance.

Produces 9 evidence sheets + updated timeline narrative:
  01_actor_index.csv       — every named actor: role, first/last mention, frequency
  02_codebook.csv          — tag definitions and legal mappings
  03_search_terms.csv      — term frequency across full corpus
  04_extracts.csv          — primary evidence table (one row per coded message)
  05_context_windows.csv   — 20-message context for each high-value hit
  06_incidents.csv         — clustered incident sequences
  07_pattern_log.csv       — recurring patterns: first seen, last seen, count
  08_open_questions.csv    — auto-generated questions for human review
  possible_timeline_events_v2.md

Usage:
  python3 forensic/forensic_v2.py --data forensic/data/raw_export.json \
                                   --output-dir forensic/output_v2
"""

import json, re, csv, os, sys, argparse
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# CODEBOOK V2  (40+ tags)
# Each entry: (short_label, description, legal_reference, tactic_category)
# ─────────────────────────────────────────────────────────────────────────────
CODEBOOK = {
    # ── CONTROL ──────────────────────────────────────────────────────────────
    "CONTROL_OWNERSHIP": (
        "Language treating victim as property: 'my slut', 'keep you', 'trophy', 'mine'",
        "SCA 2015 s.76; Duluth 'Using Male Privilege' tactic",
        "CONTROL",
    ),
    "CONTROL_DECISION": (
        "Perpetrator making unilateral decisions about victim's body, money, movements",
        "SCA 2015 s.76 (substantially adverse effect on day-to-day activities)",
        "CONTROL",
    ),
    "CONTROL_MOVEMENT": (
        "Monitoring or restricting victim's physical location or travel",
        "SCA 2015 s.76; Duluth 'Using Isolation' tactic",
        "CONTROL",
    ),
    "CONTROL_TOTAL": (
        "Explicit statements of total/complete control ('total control', 'won't ever…')",
        "SCA 2015 s.76 — continuous or repeated course of conduct",
        "CONTROL",
    ),
    # ── DEPENDENCY ───────────────────────────────────────────────────────────
    "DEPENDENCY_IMMIGRATION": (
        "References to visa, sponsorship, passport, Home Office, deportation that "
        "establish or exploit immigration dependency",
        "DA Act 2021 s.1(4); DDVC / MVDAC concessions; Immigration Rules App FM",
        "DEPENDENCY",
    ),
    "DEPENDENCY_HOUSING": (
        "Housing used as leverage: eviction threats, 'where will you go', lock-outs",
        "DA Act 2021 s.1(4); Family Law Act 1996 Part IV (occupation orders)",
        "DEPENDENCY",
    ),
    "DEPENDENCY_FINANCIAL": (
        "Financial dependency established or exploited: paying rent, covering costs, "
        "'you need me financially'",
        "DA Act 2021 s.1(4) economic abuse; Duluth 'Economic Abuse' tactic",
        "DEPENDENCY",
    ),
    "DEPENDENCY_EMPLOYMENT": (
        "Employment used as leverage: threatening to affect job, controlling work schedule",
        "DA Act 2021 s.1(4); SCA 2015 s.76",
        "DEPENDENCY",
    ),
    # ── SEXUAL ───────────────────────────────────────────────────────────────
    "SEXUAL_OBJECTIFICATION": (
        "Reducing victim to body parts or sexual function: 'holes', 'trophy slut', "
        "'body', dehumanising descriptors",
        "SOA 2003 s.74 (consent context); SCA 2015 s.76 (degradation tactic)",
        "SEXUAL",
    ),
    "SEXUAL_COMMERCIALISATION": (
        "Framing victim's sexual availability as commodity: 'rent you out', 'pimp', "
        "'paying for access', financial + sexual language combined",
        "SOA 2003 s.52-53 (controlling prostitution); SCA 2015 s.76",
        "SEXUAL",
    ),
    "SEXUAL_PRESSURE": (
        "Pressure to engage in sexual acts, removal of the ability to say no, "
        "statements that she 'can't refuse'",
        "SOA 2003 s.74 (freely given consent); R v Lawrence [2020] (stealthing)",
        "SEXUAL",
    ),
    "SEXUAL_HUMILIATION": (
        "Sexual degradation used as control tactic outside explicit consent context",
        "SOA 2003; SCA 2015 s.76 (degradation)",
        "SEXUAL",
    ),
    "SEXUAL_BOUNDARY_TEST": (
        "Escalating requests or framing to test and expand sexual limits",
        "SOA 2003 s.74; R v R [1991] (no marital exemption)",
        "SEXUAL",
    ),
    "SEXUAL_AFTERCARE_FAIL": (
        "Failure to provide emotional/physical aftercare in a disclosed power-exchange "
        "relationship",
        "SOA 2003 s.74 consent conditions; SCA 2015 s.76",
        "SEXUAL",
    ),
    # ── HUMOUR MASK ──────────────────────────────────────────────────────────
    "HUMOUR_MASK": (
        "Harmful, controlling, or threatening content packaged as joke/banter/lol. "
        "Mechanism: makes the statement deniable ('just joking') while still landing.",
        "CPS CC guidance: 'perpetrators often use humour to normalise behaviour'; "
        "Relevant to establishing course of conduct under SCA 2015 s.76",
        "DELIVERY_MECHANISM",
    ),
    # ── MINIMISATION / REALITY DISTORTION ─────────────────────────────────
    "MINIMISATION": (
        "Downplaying the severity of behaviour: 'just', 'only a bit', 'overreacting'",
        "SCA 2015 s.76 pattern element; Duluth 'Minimising, Denying, Blaming'",
        "REALITY_DISTORTION",
    ),
    "DENIAL": (
        "Direct denial of events that occurred",
        "SCA 2015 s.76; relevant to credibility",
        "REALITY_DISTORTION",
    ),
    "BLAME_SHIFT": (
        "Attributing perpetrator's conduct to victim's behaviour",
        "Duluth 'Minimising, Denying, Blaming'; CPS CC guidance (DARVO recognition)",
        "REALITY_DISTORTION",
    ),
    "REALITY_UNDERMINE": (
        "Causing victim to doubt their own memory, perception, or sanity",
        "DA Act 2021 s.1(3) psychological abuse; SCA 2015 s.76",
        "REALITY_DISTORTION",
    ),
    "CRAZY_SEXUAL": (
        "'Crazy' used in sexual intensity context — may be consensual framing",
        "Context-dependent; flag for human review",
        "REALITY_DISTORTION_SUBTYPE",
    ),
    "CRAZY_REALITY": (
        "'Crazy' used to dismiss victim's legitimate concern or memory",
        "DA Act 2021 s.1(3); SCA 2015 s.76",
        "REALITY_DISTORTION_SUBTYPE",
    ),
    "CRAZY_AFFECTION": (
        "'Crazy' used affectionately ('crazy about you')",
        "No legal significance on its own — context marker only",
        "REALITY_DISTORTION_SUBTYPE",
    ),
    "CRAZY_SELF": (
        "Victim uses 'crazy' about themselves (self-doubt, internalised framing)",
        "Relevant to psychological impact evidence",
        "REALITY_DISTORTION_SUBTYPE",
    ),
    # ── REPAIR CYCLE ─────────────────────────────────────────────────────────
    "REPAIR_CYCLE": (
        "Post-incident apology, reconciliation, or affection (sorry, miss you, forgive). "
        "Key: what happened immediately before?",
        "CPS CC guidance: 'full picture' and 'layered spectrum'; DASH indicator",
        "CYCLE",
    ),
    "LOVE_BOMB": (
        "Intense affirmation of love/worth, often following an incident or exit attempt",
        "Documented in Stark (2007) as a cycle-maintenance tactic",
        "CYCLE",
    ),
    # ── ISOLATION ─────────────────────────────────────────────────────────────
    "ISOLATION_FRIENDS": (
        "Interference with, criticism of, or restrictions on friendships",
        "SCA 2015 s.76; Duluth 'Using Isolation'",
        "ISOLATION",
    ),
    "ISOLATION_FAMILY": (
        "Interference with family contact",
        "SCA 2015 s.76; Duluth 'Using Isolation'",
        "ISOLATION",
    ),
    # ── TRIANGULATION ─────────────────────────────────────────────────────────
    "TRIANGULATION_EX": (
        "Use of ex-partner (Holly) to create jealousy, comparison, or destabilisation",
        "Duluth 'Using Emotional Abuse'; SCA 2015 s.76 pattern element",
        "TRIANGULATION",
    ),
    "TRIANGULATION_THIRD": (
        "Use of another person (Dan, Nathan, Kit, Nick) to manipulate, compare, or "
        "destabilise",
        "Duluth 'Using Emotional Abuse'",
        "TRIANGULATION",
    ),
    # ── THREATS ───────────────────────────────────────────────────────────────
    "THREAT_LEGAL": (
        "Threats involving legal action, police, or official processes",
        "PHA 1997; SCA 2015 s.76",
        "THREAT",
    ),
    "THREAT_IMMIGRATION": (
        "Threats involving immigration status, deportation, Home Office",
        "SCA 2015 s.76; DA Act 2021 s.1(4); DDVC",
        "THREAT",
    ),
    "THREAT_HOUSING": (
        "Threats to remove housing: 'kick you out', 'you'll have nowhere to go'",
        "SCA 2015 s.76; DA Act 2021 s.1(4); Housing Act 1996 s.177",
        "THREAT",
    ),
    "THREAT_SELF_HARM": (
        "Perpetrator threatening self-harm as coercive tool, or victim disclosing "
        "self-harm/suicidal ideation",
        "SCA 2015 s.76; Mental Health Act; DASH high-risk indicator",
        "THREAT",
    ),
    "THREAT_VIOLENCE": (
        "Direct or indirect threat of physical violence",
        "CJA 1988 s.39; PHA 1997; SCA 2015 s.76",
        "THREAT",
    ),
    # ── ABUSE NAMED ───────────────────────────────────────────────────────────
    "ABUSE_BY_HENRY": (
        "Henry uses the word 'abuse' to describe Cady's conduct (DARVO)",
        "CPS CC guidance on DARVO; credibility assessment",
        "ABUSE_NAMED",
    ),
    "ABUSE_BY_CADY": (
        "Cady explicitly names abuse, abusive behaviour, or sends support resources",
        "Contemporaneous victim naming — strongest credibility evidence",
        "ABUSE_NAMED",
    ),
    # ── FEAR / DISTRESS ───────────────────────────────────────────────────────
    "FEAR_BY_CADY": (
        "Cady explicitly states fear, being scared, or feeling unsafe",
        "DA Act 2021 s.1(3); DASH indicator; R v Dhaliwal [2006] (psych injury)",
        "DISTRESS",
    ),
    "DISTRESS_PHYSICAL": (
        "Physical symptoms of distress: vomiting, not eating, not sleeping, shaking",
        "DA Act 2021 s.1(3); medical corroboration evidence",
        "DISTRESS",
    ),
    # ── VIOLENCE ─────────────────────────────────────────────────────────────
    "VIOLENCE_DIRECT": (
        "Direct statement of physical violence having occurred",
        "CJA 1988 s.39 (assault); Offences Against Person Act 1861; DASH indicator",
        "VIOLENCE",
    ),
    "DOCUMENT_CONTROL": (
        "Passport, documents, ID withheld or moved by perpetrator",
        "SCA 2015 s.76; DASH indicator; CPS CC guidance",
        "CONTROL",
    ),
    # ── EXIT ─────────────────────────────────────────────────────────────────
    "EXIT_ATTEMPT": (
        "Victim attempts or signals desire to leave the relationship",
        "Key indicator of victim's resistance — important for disproving consent "
        "to coercive regime",
        "EXIT",
    ),
    "EXIT_BLOCKED": (
        "Perpetrator's response to exit attempt that discourages or prevents leaving",
        "SCA 2015 s.76; Duluth 'Using Children/Threats'",
        "EXIT",
    ),
    # ── MONITORING ────────────────────────────────────────────────────────────
    "MONITORING": (
        "Checking on location, movements, communications, or social contacts",
        "SCA 2015 s.76; Duluth 'Using Isolation'; tech abuse framework",
        "CONTROL",
    ),
    # ── FUTURE FAKING ────────────────────────────────────────────────────────
    "FUTURE_FAKE": (
        "False promises about future life, home, children, to maintain relationship",
        "Relevant to any duress/undue influence claim; establishes psychological hook",
        "DELIVERY_MECHANISM",
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# ACTOR INDEX — named actors to track
# (name, role, aliases)
# ─────────────────────────────────────────────────────────────────────────────
TRACKED_ACTORS = {
    "Henry": ("Henry Woods", "perpetrator", ["henry", "henry woods", "henry's"]),
    "Cady": ("Cady", "victim", ["cady", "cady's"]),
    "Holly": ("Holly", "ex-partner of Henry / triangulation", ["holly", "holly's"]),
    "Dan": ("Dan", "third party (roommate/friend?)", [" dan ", " dan,", " dan.", " dan'", "dan's", "dan\\"]),
    "Nathan": ("Nathan", "Cady's friend / support person", ["nathan", "nathan's"]),
    "Margo": ("Margo", "Cady's friend", ["margo", "margo's"]),
    "Jody": ("Jody", "Cady's friend", ["jody", "jody's"]),
    "Wade": ("Wade", "third party", ["wade", "wade's"]),
    "Kit": ("Kit", "third party", [" kit ", " kit,", " kit."]),
    "Nick": ("Nick", "third party", [" nick ", " nick,", " nick."]),
    "Sintija": ("Sintija", "possible ex / third party", ["sintija", "sintija's"]),
    "Jamie": ("Jamie", "third party", [" jamie ", " jamie,", "jamie's"]),
    "Kurt": ("Kurt", "Cady's coworker/friend", [" kurt ", " kurt,", "kurt's"]),
    "Emily": ("Emily", "third party", [" emily ", " emily,", "emily's"]),
    "Tom": ("Tom", "third party", [" tom ", " tom,", "tom's"]),
    "James": ("James", "third party", [" james ", " james,", "james's"]),
    "Liz": ("Liz", "third party", [" liz ", " liz,", "liz's"]),
    "Max": ("Max", "third party", [" max ", " max,", "max's"]),
}

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH TERM BATCH (expert-specified)
# ─────────────────────────────────────────────────────────────────────────────
SEARCH_TERMS = [
    ("rent", ["rent you out", "rent her out", "renting you", "renting her"]),
    ("cost/keeping", ["keeping you", "keeping her", "keep you", "keep her", "cost of you"]),
    ("control", ["control", "controlling", "total control", "under my control"]),
    ("joke/mask", ["joke", "joking", "kidding", "jk ", "only joking", "not serious"]),
    ("crazy", ["crazy", "mad", "insane", "you're crazy", "you're mad"]),
    ("sorry/repair", ["sorry", "apologise", "apologize", "forgive", "won't happen", "didn't mean"]),
    ("abuse_named", ["abuse", "abusive", "abused"]),
    ("leave/exit", ["i will leave", "i'm leaving", "i am leaving", "leaving you",
                    "want to leave", "need to leave", "annulment", "divorce"]),
    ("visa/deport", ["visa", "deport", "home office", "immigration", "sponsor", "leave the uk"]),
    ("Holly", ["holly"]),
    ("Dan", [" dan ", " dan,", " dan.", "dan's"]),
    ("passport/docs", ["passport", "documents", "id card", "papers"]),
    ("trophy/slut/holes", ["trophy", "slut", "holes", "hole", "property", "belong to me"]),
    ("violence_direct", ["physically violent", "hit me", "hurt me", "grabbed me",
                          "pushed me", "you hit", "you hurt", "you grabbed"]),
    ("scared/unsafe", ["scared", "unsafe", "afraid", "frightened", "fear for"]),
]

# ─────────────────────────────────────────────────────────────────────────────
# TAG RULES  — applied to each message
# Returns list of tags
# ─────────────────────────────────────────────────────────────────────────────

HUMOUR_MARKERS = re.compile(
    r'\b(lol|lmao|haha|hehe|😂|😜|🤣|joke|joking|kidding|jk|banter|'
    r'teehee|not serious|only playing|🙈|😏)\b', re.IGNORECASE)

def tag_v2(text: str, speaker: str) -> list[str]:
    t = text.lower()
    tags = []
    is_henry = speaker == "Henry Woods"
    is_cady = speaker == "Cady"
    has_humour = bool(HUMOUR_MARKERS.search(text))

    # ── CONTROL ──
    if re.search(r'\b(trophy|my slut|my property|belong to me|you\'re mine|keep you|'
                 r'keeping you|mine to|she\'s mine)\b', t):
        tags.append("CONTROL_OWNERSHIP")
    if re.search(r'\btotal control\b|under my control\b|you won\'t ever\b|'
                 r'you will never\b.*control', t):
        tags.append("CONTROL_TOTAL")
    if re.search(r'\b(where are you|where were you|who are you with|'
                 r'why didn.t you answer|why didn.t you reply|been trying to reach|'
                 r'location|tracking|track you)\b', t):
        tags.append("MONITORING")

    # ── DEPENDENCY ──
    if re.search(r'\b(visa|deport|home office|sponsor|sponsorship|leave the uk|'
                 r'ilr|right to remain|biometric|ukvi|immigration status)\b', t):
        tags.append("DEPENDENCY_IMMIGRATION")
    if re.search(r'\b(kicked out|kick you out|lock you out|locked out|'
                 r'where will you go|nowhere to go|evict|leave the house)\b', t):
        tags.append("DEPENDENCY_HOUSING")
    if re.search(r'\b(pay your rent|cover your|owe me|i pay|financially dependent|'
                 r'you need my money|without my money|i support you)\b', t):
        tags.append("DEPENDENCY_FINANCIAL")

    # ── SEXUAL ──
    if re.search(r'\b(holes|hole|trophy slut|bashing rocks|slut|whore|your body|'
                 r'keeping your|just a body)\b', t):
        tags.append("SEXUAL_OBJECTIFICATION")
    if re.search(r'\b(rent you out|rent her out|pimp|fuck you for free|pay for|'
                 r'paying for access|commerc)\b', t):
        tags.append("SEXUAL_COMMERCIALISATION")
    if re.search(r'\b(not allowed to say no|can\'t say no|no means nothing|'
                 r'do as i say|do what i say|won\'t take no|you have no choice|'
                 r'whether you like)\b', t):
        tags.append("SEXUAL_PRESSURE")
    if re.search(r'\b(condom|protection|without protection|sti|std|chlamydia|'
                 r'aftercare|stealthing)\b', t):
        tags.append("SEXUAL_BOUNDARY_TEST")

    # ── HUMOUR MASK — applied if concerning tag + humour present ──
    concerning = {"CONTROL_OWNERSHIP", "CONTROL_TOTAL", "SEXUAL_OBJECTIFICATION",
                  "SEXUAL_COMMERCIALISATION", "SEXUAL_PRESSURE", "DEPENDENCY_IMMIGRATION",
                  "DEPENDENCY_HOUSING", "THREAT_VIOLENCE", "THREAT_IMMIGRATION"}
    if has_humour and any(t2 in concerning for t2 in tags):
        tags.append("HUMOUR_MASK")

    # ── MINIMISATION / REALITY ──
    if re.search(r'\b(only a bit|overreact(?:ing)?|too sensitive|so sensitive|'
                 r'being dramatic|stop being|you\'re imagining|that never happened|'
                 r'not what i said|you remember wrong|i never said|'
                 r'you.re exaggerating|making it up|it was nothing|'
                 r'not a big deal|such a big deal|calm down|relax)\b', t) and is_henry:
        tags.append("MINIMISATION")
    if re.search(r'\b(that never happened|you\'re imagining|not what i said|'
                 r'you remember wrong|i never said|you misheard|gaslighting|'
                 r'you\'re making|making it up)\b', t) and is_henry:
        tags.append("REALITY_UNDERMINE")

    # ── CRAZY sub-tags ──
    if 'crazy' in t or 'mad' in t or 'insane' in t:
        # Check context
        if re.search(r'\b(crazy sex|crazy in bed|mad in bed|wild|insane sex|'
                     r'crazy hot|absolutely mad|crazy chemistry|madly in love)\b', t):
            tags.append("CRAZY_SEXUAL")
        elif re.search(r'\b(you\'re crazy|you\'re mad|you\'re insane|'
                       r'you\'re being crazy|acting crazy|sounds crazy)\b', t) and is_henry:
            tags.append("CRAZY_REALITY")
        elif re.search(r'\b(crazy about|madly|crazy for you|crazy for)\b', t):
            tags.append("CRAZY_AFFECTION")
        elif is_cady and re.search(r'\b(i\'m going crazy|i feel crazy|am i crazy|'
                                   r'i sound crazy|feel like i\'m|i must be)\b', t):
            tags.append("CRAZY_SELF")

    # ── BLAME SHIFT ──
    if re.search(r'\b(your fault|you made me|if you hadn.t|because of you|'
                 r'you caused|you started|you provoked|look what you.ve done|'
                 r'made me do)\b', t) and is_henry:
        tags.append("BLAME_SHIFT")

    # ── DARVO ──
    if re.search(r'\b(i.m the victim|abuse i can take|amount of abuse|'
                 r'after everything i.ve done|i give you everything|'
                 r'i do everything for you|look what you.ve done to me)\b', t) and is_henry:
        tags.append("ABUSE_BY_HENRY")

    # ── REPAIR CYCLE ──
    if re.search(r'\b(sorry|apologise|apologize|forgive me|won.t happen again|'
                 r'didn.t mean|i love you so much|miss you so much|please come back|'
                 r'i need you|you.re everything)\b', t):
        tags.append("REPAIR_CYCLE")

    # ── LOVE BOMBING ──
    if re.search(r'\b(you.re amazing|you.re incredible|never met anyone|'
                 r'you.re perfect|my whole world|you.re everything|'
                 r'luckiest person|so lucky to have)\b', t) and is_henry:
        tags.append("LOVE_BOMB")

    # ── ISOLATION ──
    if re.search(r'\b(your friends are|your family|they don.t get it|they don.t understand|'
                 r'no one gets us|just us|only us|cut off|they.re against us)\b', t) and is_henry:
        tags.append("ISOLATION_FRIENDS")

    # ── TRIANGULATION ──
    if re.search(r'\b(holly)\b', t):
        tags.append("TRIANGULATION_EX")
    if re.search(r'\b(watch the fallout|make her jealous|make you jealous)\b', t):
        tags.append("TRIANGULATION_EX")

    # ── THREATS ──
    if re.search(r'\b(report you|report to home office|deport you|call immigration|'
                 r'tell home office)\b', t) and is_henry:
        tags.append("THREAT_IMMIGRATION")
    if re.search(r'\b(kick you out|you.ll be homeless|nowhere to go|leave my house|'
                 r'out of my house|out of the flat)\b', t) and is_henry:
        tags.append("THREAT_HOUSING")
    if re.search(r'\b(physically violent|i will hurt|i.ll hit|come here or else|'
                 r'you.ll regret|make you pay)\b', t):
        tags.append("THREAT_VIOLENCE")

    # ── VIOLENCE DIRECT ──
    if re.search(r'\b(physically violent|you hit me|you were violent|'
                 r'you have hit me today|you hurt me|you grabbed me|you pushed me|'
                 r'you assaulted me|physically violent.*multiple|'
                 r'you were.*violent)\b', t) and is_cady:
        tags.append("VIOLENCE_DIRECT")

    # ── DOCUMENT CONTROL ──
    # Document control: require specific ownership + action context
    if re.search(r'\b(passport)\b', t) and \
       re.search(r'\b(swapped|moved|took|taken|have your|do you have|'
                 r'can.t find|missing|where is|held|withheld|kept)\b', t):
        tags.append("DOCUMENT_CONTROL")

    # ── ABUSE NAMED BY CADY ──
    if is_cady and re.search(r'\b(abuse|abusive|abuser|he.s abusive|'
                              r'coercive|controlling|narciss|perpetrator|'
                              r'respectphoneline|refuge|national domestic)\b', t):
        tags.append("ABUSE_BY_CADY")

    # ── FEAR ──
    if is_cady and re.search(r'\b(scared|afraid|frightened|fear|unsafe|'
                              r'scared for my|scared of him|scared of you|'
                              r'worried about my safety)\b', t):
        tags.append("FEAR_BY_CADY")

    # ── EXIT ──
    if is_cady and re.search(
            r'\b(annulment|divorce)\b|'
            r'\b(i will leave you|i.m leaving you|leaving you|leave you|'
            r'i.m done|i.m out of here|i.m out of this|'
            r'report to home office|file for annulment|file for divorce|'
            r'leave the country.*home office|don.t talk to me i.m leaving)\b', t):
        tags.append("EXIT_ATTEMPT")

    # ── DEPENDENCY IMMIGRATION framing by Henry ──
    if is_henry and re.search(r'\b(we.ll get you your visa|your visa|'
                               r'visa sponsor|nearest registry|i.ll sponsor)\b', t):
        tags.append("DEPENDENCY_IMMIGRATION")

    # ── FUTURE FAKING ──
    if is_henry and re.search(r'\b(one day we|when we have|our home|our life|'
                               r'our kids|our children|our family|our future|'
                               r'someday|i promise|we.ll build)\b', t):
        tags.append("FUTURE_FAKE")

    return list(dict.fromkeys(tags))  # deduplicate, preserve order


# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
PHASES = [
    ("PRE",  "Pre-cohabitation (Jul 2024 – Jul 2025)",
     datetime(2024, 7,  6), datetime(2025, 7, 24)),
    ("P0",   "Phase 0: Cohabitation + Wedding (Jul–Sep 2025)",
     datetime(2025, 7, 25), datetime(2025, 9, 30)),
    ("P1",   "Phase 1: Post-wedding dependency (Oct–Nov 2025)",
     datetime(2025, 10, 1), datetime(2025, 11, 30)),
    ("P2",   "Phase 2: Financial & emotional instability (Dec 2025)",
     datetime(2025, 12, 1), datetime(2025, 12, 31)),
    ("P3",   "Phase 3: Crisis & third-party recognition (Jan 2026)",
     datetime(2026, 1,  1), datetime(2026, 1, 31)),
    ("P4",   "Phase 4: Cycling / separation signals (Feb–May 2026)",
     datetime(2026, 2,  1), datetime(2026, 5, 31)),
]

def assign_phase(dt):
    for pid, label, start, end in PHASES:
        if start <= dt <= end:
            return pid, label
    return "UNKNOWN", "Outside phases"


# ─────────────────────────────────────────────────────────────────────────────
# PARSER  (same as v1)
# ─────────────────────────────────────────────────────────────────────────────

def parse_messages(content):
    rows = content.split("\n")
    msg_rows = [r.strip() for r in rows if r.strip().startswith("| \\[")]
    pat = re.compile(
        r"\| \\\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d+:\d+:\d+)[\s ]+([ap]m)\\\]\s+"
        r"([^:|]+):\s*(.*?)\s*\|$",
        re.IGNORECASE,
    )
    messages = []
    for row in msg_rows:
        m = pat.match(row)
        if not m:
            continue
        date_str, time_str, ampm, speaker, text = m.groups()
        speaker = speaker.strip()
        text = text.replace("‎", "").replace(" ", " ").strip()
        if any(x in text.lower() for x in ["encrypted", "messages and calls"]):
            continue
        try:
            dt = datetime.strptime(f"{date_str} {time_str} {ampm.upper()}", "%m/%d/%y %I:%M:%S %p")
        except ValueError:
            continue
        messages.append({"datetime": dt, "date": dt.strftime("%Y-%m-%d"),
                         "time": dt.strftime("%H:%M:%S"), "speaker": speaker,
                         "message_text": text})
    messages.sort(key=lambda x: x["datetime"])
    for i, msg in enumerate(messages):
        msg["message_id"] = f"MSG_{i:05d}"
    return messages


# ─────────────────────────────────────────────────────────────────────────────
# ACTOR INDEX
# ─────────────────────────────────────────────────────────────────────────────

def build_actor_index(messages):
    index = {}
    for actor_key, (full_name, role, aliases) in TRACKED_ACTORS.items():
        hits = []
        for msg in messages:
            if any(a.lower() in msg["message_text"].lower() for a in aliases):
                hits.append(msg)
        index[actor_key] = {
            "actor_key": actor_key,
            "full_name": full_name,
            "role": role,
            "total_mentions": len(hits),
            "first_mention_date": hits[0]["date"] if hits else "",
            "last_mention_date": hits[-1]["date"] if hits else "",
            "first_mention_speaker": hits[0]["speaker"] if hits else "",
            "first_mention_text": hits[0]["message_text"][:200] if hits else "",
        }
    return list(index.values())


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH TERM FREQUENCY
# ─────────────────────────────────────────────────────────────────────────────

def build_search_term_counts(messages):
    rows = []
    for term_label, patterns in SEARCH_TERMS:
        hits = [m for m in messages
                if any(p.lower() in m["message_text"].lower() for p in patterns)]
        henry_hits = [h for h in hits if h["speaker"] == "Henry Woods"]
        cady_hits  = [h for h in hits if h["speaker"] == "Cady"]
        rows.append({
            "term": term_label,
            "patterns": " | ".join(patterns),
            "total_hits": len(hits),
            "henry_hits": len(henry_hits),
            "cady_hits": len(cady_hits),
            "first_date": hits[0]["date"] if hits else "",
            "last_date": hits[-1]["date"] if hits else "",
            "example_henry": henry_hits[0]["message_text"][:200] if henry_hits else "",
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# FULL ANNOTATION
# ─────────────────────────────────────────────────────────────────────────────

def annotate(messages):
    annotated = []
    for i, msg in enumerate(messages):
        phase_id, phase_label = assign_phase(msg["datetime"])
        tags = tag_v2(msg["message_text"], msg["speaker"])
        legal_notes = []
        seen = set()
        for tag in tags:
            if tag in CODEBOOK and tag not in seen:
                legal_notes.append(f"[{tag}] {CODEBOOK[tag][1]}")
                seen.add(tag)

        # NEEDS_REVIEW flag
        review_pattern = re.compile(
            r"\b(divorce|visa|passport|kicked out|kick.*out|locked out|unsafe|scared|"
            r"threat(?:en)?|violen|yelling|screaming|coercive|abus|control(?:ling)?|"
            r"home office|suicid|self.harm|hurt myself|aggressive|"
            r"physically violent|hit me|rape|assault|nowhere to go)\b",
            re.IGNORECASE)
        needs_review = bool(review_pattern.search(msg["message_text"]))

        annotated.append({
            **msg,
            "seq_index": i,
            "phase_id": phase_id,
            "phase_label": phase_label,
            "tags": "|".join(tags),
            "tag_count": len(tags),
            "needs_extra_review": "YES" if needs_review else "",
            "legal_framework": " || ".join(legal_notes) if legal_notes else "",
        })
    return annotated


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTS (04)
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_ID_COUNTER = [0]

def build_extracts(annotated):
    extracts = []
    for msg in annotated:
        if not msg["tags"]:
            continue
        EXTRACT_ID_COUNTER[0] += 1
        eid = f"E{EXTRACT_ID_COUNTER[0]:04d}"
        extracts.append({
            "extract_id": eid,
            "message_id": msg["message_id"],
            "date": msg["date"],
            "time": msg["time"],
            "speaker": msg["speaker"],
            "exact_quote": msg["message_text"],
            "primary_code": msg["tags"].split("|")[0] if msg["tags"] else "",
            "all_codes": msg["tags"],
            "phase_id": msg["phase_id"],
            "actors_mentioned": ", ".join(
                a for a, (_, _, aliases) in TRACKED_ACTORS.items()
                if a not in ("Henry", "Cady") and
                any(al.lower() in msg["message_text"].lower() for al in aliases)
            ),
            "needs_extra_review": msg["needs_extra_review"],
            "legal_framework": msg["legal_framework"],
            "interpretation_note": "",  # For human annotation
            "impact_on_cady": "",       # For human annotation
            "later_significance": "",   # For human annotation
            "confidence": "auto-tagged — human review required",
        })
    return extracts


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT WINDOWS (05)  — 20 messages before and after
# ─────────────────────────────────────────────────────────────────────────────

CONTEXT = 20

def build_context_windows(annotated):
    tagged_idx = [i for i, m in enumerate(annotated) if m["tag_count"] > 0]
    seen = set()
    rows = []
    for ti in tagged_idx:
        lo = max(0, ti - CONTEXT)
        hi = min(len(annotated) - 1, ti + CONTEXT)
        for j in range(lo, hi + 1):
            uid = (ti, annotated[j]["message_id"])
            if uid in seen:
                continue
            seen.add(uid)
            role = "TARGET" if j == ti else ("BEFORE" if j < ti else "AFTER")
            rows.append({
                **annotated[j],
                "context_role": role,
                "target_msg_id": annotated[ti]["message_id"],
                "target_extract_date": annotated[ti]["date"],
            })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# INCIDENTS (06) — cluster tagged messages within 2 hours of each other
# ─────────────────────────────────────────────────────────────────────────────

def build_incidents(annotated):
    tagged = [m for m in annotated if m["tag_count"] > 0]
    if not tagged:
        return []

    incidents = []
    cluster = [tagged[0]]
    INC_GAP = timedelta(hours=2)

    for msg in tagged[1:]:
        if msg["datetime"] - cluster[-1]["datetime"] <= INC_GAP:
            cluster.append(msg)
        else:
            incidents.append(cluster)
            cluster = [msg]
    incidents.append(cluster)

    rows = []
    for i, inc in enumerate(incidents):
        all_tags = []
        for m in inc:
            all_tags.extend(m["tags"].split("|") if m["tags"] else [])
        tag_freq = defaultdict(int)
        for t in all_tags:
            if t:
                tag_freq[t] += 1
        primary = max(tag_freq, key=tag_freq.get) if tag_freq else ""

        rows.append({
            "incident_id": f"INC_{i+1:03d}",
            "start_date": inc[0]["date"],
            "start_time": inc[0]["time"],
            "end_date": inc[-1]["date"],
            "end_time": inc[-1]["time"],
            "phase_id": inc[0]["phase_id"],
            "message_count": len(inc),
            "primary_tag": primary,
            "all_tags": "|".join(sorted(set(t for t in all_tags if t))),
            "henry_messages": sum(1 for m in inc if m["speaker"] == "Henry Woods"),
            "cady_messages": sum(1 for m in inc if m["speaker"] == "Cady"),
            "needs_extra_review": "YES" if any(m["needs_extra_review"] for m in inc) else "",
            "key_quotes": " ||| ".join(
                f"[{m['speaker']}] {m['message_text'][:150]}"
                for m in inc[:5]
            ),
            "open_questions": "",  # For human annotation
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN LOG (07)
# ─────────────────────────────────────────────────────────────────────────────

def build_pattern_log(annotated):
    tag_data = defaultdict(list)
    for msg in annotated:
        for tag in (msg["tags"].split("|") if msg["tags"] else []):
            if tag:
                tag_data[tag].append(msg)

    rows = []
    for tag, msgs in sorted(tag_data.items()):
        henry_msgs = [m for m in msgs if m["speaker"] == "Henry Woods"]
        cady_msgs  = [m for m in msgs if m["speaker"] == "Cady"]
        description, legal, category = CODEBOOK.get(tag, ("", "", ""))
        rows.append({
            "pattern_id": f"P{len(rows)+1:03d}",
            "tag": tag,
            "category": category,
            "description": description,
            "total_occurrences": len(msgs),
            "henry_occurrences": len(henry_msgs),
            "cady_occurrences": len(cady_msgs),
            "first_seen": msgs[0]["date"],
            "last_seen": msgs[-1]["date"],
            "span_days": (msgs[-1]["datetime"] - msgs[0]["datetime"]).days,
            "legal_reference": legal,
            "representative_quote": msgs[0]["message_text"][:300] if msgs else "",
            "escalation_note": "",  # For human annotation
        })
    # Sort by total occurrences desc
    rows.sort(key=lambda x: -x["total_occurrences"])
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# OPEN QUESTIONS (08)
# ─────────────────────────────────────────────────────────────────────────────

def build_open_questions(annotated, incidents, actor_index):
    questions = []
    qid = [0]

    def Q(category, question, context="", priority="MEDIUM"):
        qid[0] += 1
        questions.append({
            "question_id": f"Q{qid[0]:03d}",
            "category": category,
            "priority": priority,
            "question": question,
            "context": context,
            "answer": "",
            "source_needed": "",
        })

    # Auto-generate questions from key findings
    passport = [m for m in annotated if "DOCUMENT_CONTROL" in m["tags"]]
    if passport:
        Q("DOCUMENT_CONTROL",
          "Can Cady confirm the sequence of passport events — when she last had it, "
          "when she noticed it missing, and what Henry's explanation was?",
          f"First flagged: {passport[0]['date']}",
          "HIGH")

    violence = [m for m in annotated if "VIOLENCE_DIRECT" in m["tags"]]
    if violence:
        Q("PHYSICAL_VIOLENCE",
          "What incidents of physical violence are described? Were any injuries sustained? "
          "Were there any witnesses or medical records?",
          f"{len(violence)} direct statements. First: {violence[0]['date']}",
          "HIGH")

    exit_attempts = [m for m in annotated if "EXIT_ATTEMPT" in m["tags"]]
    if exit_attempts:
        Q("EXIT_ATTEMPT",
          f"There are {len(exit_attempts)} exit attempt signals. What happened immediately "
          "after each one? Was there a repair cycle? Were there consequences?",
          "See 04_extracts.csv filtered by EXIT_ATTEMPT",
          "HIGH")

    imm = [m for m in annotated if "DEPENDENCY_IMMIGRATION" in m["tags"]
           and m["speaker"] == "Henry Woods"]
    if imm:
        Q("IMMIGRATION",
          "What is Cady's current visa/immigration status? Was Henry ever her sponsor? "
          "Does she have independent immigration status or is it linked to the marriage?",
          "Immigration-related messages from Henry span the full dataset",
          "HIGH")

    sc = [m for m in annotated if "SEXUAL_COMMERCIALISATION" in m["tags"]]
    if sc:
        Q("SEXUAL_COMMERCIALISATION",
          "The 'rent you out' message (Jan 17 2025) and related messages: were these "
          "understood as roleplay at the time? Did this framing continue after the wedding? "
          "Was there any commercial sexual arrangement actually proposed or acted on?",
          "Jan 17 2025 message: 'gonna rent you out to people'",
          "HIGH")

    repair = [m for m in annotated if "REPAIR_CYCLE" in m["tags"]]
    if repair:
        Q("REPAIR_CYCLE",
          f"There are {len(repair)} repair/apology messages. For each major incident, "
          "was the same behaviour repeated afterwards? Build the incident → apology → "
          "recurrence sequence.",
          "Filter 06_incidents.csv, then look 48h after each incident",
          "MEDIUM")

    Q("HUMOUR_MASK",
      "Which statements did Cady believe were jokes at the time? When did she realise "
      "they were serious? The 'Not even as a joke' exchange (Jan 22 2025) about what "
      "specifically?",
      "Jan 22 2025 exchange: Cady asks 'lol are you joking', Henry: 'Not even as a joke'",
      "HIGH")

    Q("TRIANGULATION_EX",
      "Holly is mentioned 16 times. Was Henry's use of Holly intended to destabilise "
      "Cady? The 'invite Holly to watch the fallout' message — what event was this about?",
      "'So tempted to send Holly an invite just to watch the fallout' (Feb 24 2025)",
      "MEDIUM")

    Q("SUPPORT_NETWORK",
      "Which friends/family members knew about the relationship difficulties? "
      "Nathan, Jody, Kit, Nick — who does Cady have contemporaneous contact with? "
      "Could any of them provide a witness statement?",
      "See 01_actor_index.csv for full actor network",
      "MEDIUM")

    Q("TIMELINE_GAP",
      "The corpus has very few messages in Oct 2025 (33 messages). What was happening "
      "immediately post-wedding? Were they not communicating by WhatsApp, or is data missing?",
      "October 2025: only 33 messages vs 191 in September 2025",
      "MEDIUM")

    return questions


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN NARRATIVE V2
# ─────────────────────────────────────────────────────────────────────────────

def build_markdown_v2(annotated, actor_index, pattern_log):
    lines = ["# Forensic Evidence Timeline — Version 2", ""]
    lines.append(
        "> **LEGAL CAVEAT**: Working analytical tool only. All language uses "
        "'could be evidence of…' framing. Consult a specialist DA solicitor or IDVA "
        "before any legal use. **National DA Helpline: 0808 2000 247** (free, 24/7). "
        "**Southall Black Sisters (immigration + DA): 020 8571 0800.**"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    total = len(annotated)
    tagged = sum(1 for m in annotated if m["tag_count"] > 0)
    review = sum(1 for m in annotated if m["needs_extra_review"])
    henry = sum(1 for m in annotated if m["speaker"] == "Henry Woods")

    lines += [
        "## Summary", "",
        f"| | |", f"|---|---|",
        f"| Total messages | {total:,} |",
        f"| Henry Woods messages | {henry:,} |",
        f"| Tagged (any tag) | {tagged:,} |",
        f"| NEEDS_EXTRA_REVIEW | {review:,} |",
        f"| Date range | {annotated[0]['date']} → {annotated[-1]['date']} |",
        "", "---", "",
    ]

    lines.append("## Top patterns by frequency")
    lines.append("")
    lines.append("| Pattern | Count | Henry | Cady | First seen | Legal ref |")
    lines.append("|---------|-------|-------|------|-----------|-----------|")
    for p in pattern_log[:20]:
        lines.append(
            f"| `{p['tag']}` | {p['total_occurrences']} | {p['henry_occurrences']} | "
            f"{p['cady_occurrences']} | {p['first_seen']} | "
            f"{p['legal_reference'][:80]}… |"
        )
    lines.append("")

    # Phase sections with key extracts
    for phase_id, phase_label, start, end in PHASES:
        phase_msgs = [m for m in annotated if m["phase_id"] == phase_id]
        if not phase_msgs:
            continue
        high = [m for m in phase_msgs if m["tag_count"] >= 2 or m["needs_extra_review"]]
        if not high:
            continue

        lines += ["---", "", f"## {phase_label}", ""]
        lines.append(f"*{len(phase_msgs):,} total messages. {len(high):,} high-priority.*")
        lines.append("")

        # Tag summary
        tf = defaultdict(int)
        for m in phase_msgs:
            for t in m["tags"].split("|"):
                if t: tf[t] += 1
        if tf:
            top = sorted(tf.items(), key=lambda x: -x[1])[:10]
            lines.append("**Top tags:** " + ", ".join(f"`{t}` ({n})" for t, n in top))
            lines.append("")

        for msg in high[:30]:
            sp = f"**{msg['speaker']}**"
            rv = " ⚠ NEEDS REVIEW" if msg["needs_extra_review"] else ""
            lines.append(f"#### {msg['date']} {msg['time']} — {sp}{rv}")
            lines.append("")
            safe = msg["message_text"].replace("|", "\\|")
            lines.append(f"> {safe}")
            lines.append("")
            lines.append(f"- **Tags**: `{msg['tags']}`")
            if msg["legal_framework"]:
                lines.append(f"- **Legal**: {msg['legal_framework'][:300]}")
            lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CSV WRITER
# ─────────────────────────────────────────────────────────────────────────────

def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {len(rows):>6,} rows → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--output-dir", default="forensic/output_v2")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("[1/9] Loading...")
    with open(args.data) as f:
        raw = f.read()
    try:
        content = json.loads(raw).get("fileContent", raw)
    except json.JSONDecodeError:
        content = raw

    print("[2/9] Parsing messages...")
    messages = parse_messages(content)
    print(f"      {len(messages):,} messages, {messages[0]['date']} → {messages[-1]['date']}")

    print("[3/9] Annotating with codebook v2...")
    annotated = annotate(messages)
    print(f"      {sum(1 for m in annotated if m['tag_count']>0):,} tagged, "
          f"{sum(1 for m in annotated if m['needs_extra_review']):,} NEEDS_REVIEW")

    print("[4/9] Building actor index...")
    actor_index = build_actor_index(messages)

    print("[5/9] Building search term counts...")
    search_counts = build_search_term_counts(messages)

    print("[6/9] Building extracts + context windows...")
    extracts = build_extracts(annotated)
    ctx = build_context_windows(annotated)

    print("[7/9] Building incidents...")
    incidents = build_incidents(annotated)

    print("[8/9] Building pattern log + open questions...")
    pattern_log = build_pattern_log(annotated)
    open_q = build_open_questions(annotated, incidents, actor_index)

    print("[9/9] Writing outputs...")
    out = args.output_dir

    write_csv(f"{out}/01_actor_index.csv", actor_index, list(actor_index[0].keys()))
    write_csv(f"{out}/02_codebook.csv",
              [{"tag": k, "description": v[0], "legal_reference": v[1], "category": v[2]}
               for k, v in CODEBOOK.items()],
              ["tag", "description", "legal_reference", "category"])
    write_csv(f"{out}/03_search_terms.csv", search_counts, list(search_counts[0].keys()))

    extract_fields = ["extract_id","message_id","date","time","speaker","exact_quote",
                      "primary_code","all_codes","phase_id","actors_mentioned",
                      "needs_extra_review","legal_framework","interpretation_note",
                      "impact_on_cady","later_significance","confidence"]
    write_csv(f"{out}/04_extracts.csv", extracts, extract_fields)

    ctx_fields = ["message_id","date","time","speaker","message_text","phase_id",
                  "tags","tag_count","needs_extra_review","context_role",
                  "target_msg_id","target_extract_date"]
    write_csv(f"{out}/05_context_windows.csv", ctx, ctx_fields)

    inc_fields = ["incident_id","start_date","start_time","end_date","end_time",
                  "phase_id","message_count","primary_tag","all_tags",
                  "henry_messages","cady_messages","needs_extra_review",
                  "key_quotes","open_questions"]
    write_csv(f"{out}/06_incidents.csv", incidents, inc_fields)

    pat_fields = ["pattern_id","tag","category","description","total_occurrences",
                  "henry_occurrences","cady_occurrences","first_seen","last_seen",
                  "span_days","legal_reference","representative_quote","escalation_note"]
    write_csv(f"{out}/07_pattern_log.csv", pattern_log, pat_fields)

    q_fields = ["question_id","category","priority","question","context","answer","source_needed"]
    write_csv(f"{out}/08_open_questions.csv", open_q, q_fields)

    md = build_markdown_v2(annotated, actor_index, pattern_log)
    md_path = f"{out}/possible_timeline_events_v2.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"       narrative → {md_path}")

    print(f"\nDone. Output: {out}/")


if __name__ == "__main__":
    main()
