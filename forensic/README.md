# WhatsApp Forensic Evidence Timeline — How It Works

## What this tool does

This tool takes a WhatsApp chat export (via Google Sheets) and produces four structured output files
designed to support a domestic abuse case review. It tags messages by category, flags high-priority
messages for human review, maps each tag to the relevant UK law, and groups findings by case phase.

**It does NOT make legal conclusions.** Every finding uses "could be evidence of…" language.
A domestic abuse solicitor or IDVA (Independent Domestic Violence Adviser) should review
flagged output before any legal use.

---

## Output files

| File | What it contains |
|------|-----------------|
| `all_messages_tagged.csv` | Every message with tags, phase, and UK legal note |
| `tagged_hits_with_context.csv` | Flagged messages + 5 before and 5 after for full context |
| `monthly_tag_counts.csv` | How many times each tag appeared per month — shows escalation |
| `possible_timeline_events.md` | Human-readable narrative grouped by case phase |

---

## Tag categories

### Keyword tags (matched against message text)

| Tag | What it catches | Why it matters legally |
|-----|----------------|----------------------|
| `HENRY_DIRECT` | Any mention of "henry" | Direct perpetrator speech |
| `MARRIAGE_WEDDING` | Wedding, married, husband, wife, register office… | Marriage Act 1949; duress claims; immigration eligibility |
| `IMMIGRATION_VISA` | Visa, passport, Home Office, ILR, right to work… | Spouse visa dependency; Destitute DV Concession (DDVC) |
| `HOUSING_HOME` | Kicked out, locked out, move out, rent, homeless… | DA Act 2021 s.1(4) economic abuse; occupation orders |
| `FINANCIAL` | Money, debt, job, bills, £, bank… | Economic abuse; financial control as coercive behaviour |
| `ANGER_THREAT` | Angry, threat, divorce threat, scream, violence… | SCA 2015 s.76 coercive control; PHA 1997 harassment |
| `SAFETY_DISTRESS` | Scared, unsafe, can't sleep, panic, vomiting… | DA Act 2021 s.1(3) psychological harm; DASH risk checklist |
| `SEXUAL_BOUNDARY` | Condom, protection, consent, STI, aftercare… | SOA 2003 s.74 (consent); stealthing (R v Lawrence 2020) |
| `NATHAN_CONCERN` | Worried, are you okay, red flag, checking on you… | Third-party witness corroboration |
| `SUPPORT_WITNESS` | Toxic, abuse, pattern, controlling, coercive… | Contemporaneous witness records |

### Forensic-linguistic tags (pattern matching beyond keywords)

These go deeper than keywords — they catch *how* something is said, not just *what*.
Methodology: Evan Stark (2007), Duluth Power & Control Wheel, DARVO (Freyd 1997), LIWC.

| Tag | What it catches |
|-----|----------------|
| `FL_MINIMISATION` | "just", "only a bit", "overreacting", "too sensitive" |
| `FL_BLAME_SHIFT` | "your fault", "you made me", "because of you" |
| `FL_ISOLATION` | "no one else", "just us", "cut off", "no friends" |
| `FL_FUTURE_FAKING` | "one day we'll", "our future", "our home", "our children" |
| `FL_LOVE_BOMBING` | "never met anyone like you", "you're my whole world", "perfect" |
| `FL_GASLIGHTING` | "that never happened", "you're imagining", "I never said" |
| `FL_DARVO` | "I'm the victim", "look what you've done to me", "after everything I've done" |
| `FL_MONITORING` | "where are you", "why didn't you answer", "been trying to reach" |

---

## Case phases

| Phase | Dates | Focus |
|-------|-------|-------|
| `PRE` | Jul 2024 – 24 Jul 2025 | Long-distance courtship; baseline behaviour; early red flags |
| `P0` | 25 Jul – 30 Sep 2025 | Cohabitation begins; wedding (20 Sep 2025) |
| `P1` | Oct – Nov 2025 | Dependency builds post-marriage |
| `P2` | Dec 2025 | Financial/emotional instability peaks |
| `P3` | Jan 2026 | Crisis; third-party recognition |
| `P4` | Feb – May 2026 | Cycling/reconciliation/separation threats |

---

## NEEDS_EXTRA_REVIEW flag

A message is flagged `YES` if it contains any of:

```
divorce · visa · passport · kicked out · locked out · unsafe · scared ·
threat · violence · yelling · screaming · coercive · abuse · control ·
home office · suicide · self harm · anger · aggressive · rape · assault
```

These messages should be read by a human first — do not share them with anyone
without legal advice.

---

## How to re-run

```bash
# Save the Google Drive API output to a file first:
python3 forensic/forensic_timeline.py \
    --data forensic/data/raw_export.json \
    --output-dir forensic/output
```

### Scheduled runs (GitHub Actions)

A `.github/workflows/forensic_refresh.yml` workflow can run this on a schedule.
See `forensic/forensic_refresh.yml` for an example.

---

## Expert methodology this tool draws from

- **Evan Stark, 'Coercive Control' (2007)** — the definitive academic model for
  pattern-based intimate partner abuse: isolation, monitoring, degradation, enforcement.
  Used as framework in UK CPS guidance.
- **Michael P. Johnson, 'A Typology of Domestic Violence' (2008)** — distinguishes
  *intimate terrorism* (systematic control) from situational couple violence.
- **Duluth Power & Control Wheel** — 8 recognised abuse tactic dimensions, widely
  used in UK MARAC and DASH risk assessments.
- **LIWC (Linguistic Inquiry & Word Count)** — validated psycholinguistic tool used
  in academic forensic linguistics; categorises language by psychological function.
- **SafeLives DASH Risk Indicator Checklist (2009)** — the standard UK tool for
  identifying high-risk domestic abuse cases; used by police, MARAC, IDVAs.
- **DARVO (Deny, Attack, Reverse Victim and Offender)** — Jennifer Freyd (1997);
  identifies perpetrator strategy of positioning themselves as victim.
- **CPS Controlling or Coercive Behaviour prosecution guidance (2015, updated 2023)** —
  explains what evidence the Crown needs for SCA 2015 s.76 charges.

---

## Support contacts

| Organisation | Number | Notes |
|-------------|--------|-------|
| National DA Helpline | **0808 2000 247** | Free, 24/7 |
| Southall Black Sisters | **020 8571 0800** | Immigration + DA specialist |
| Refuge immigration team | **0808 2000 247** | NRPF (No Recourse to Public Funds) cases |
| Rights of Women legal line | **020 7251 6577** | Free legal advice, women only |
| SafeLives MARAC referral | via local IDVA | Ask police or GP |
| Karma Nirvana (honour-based) | **0800 599 9247** | If honour/family pressure involved |
