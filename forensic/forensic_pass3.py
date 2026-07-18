#!/usr/bin/env python3
"""
Forensic Corpus Analyzer — Pass 3: Deep Dive
============================================
Pass 3 focuses on:
  A. Exit attempt sequences — what did Henry say in the 30 messages after each?
  B. Repair cycle mapping — incident → apology → recurrence
  C. Holly triangulation thread — full chronological narrative
  D. December 2024 escalation — full context (the first major spike)
  E. "Warming up / lads" thread — the sexual commercialisation pattern in action
  F. "Not even a joke" exchange — full context window
  G. Ownership language arc — from first to last
  H. Word frequency analysis of Henry-only corpus

Produces:
  pass3_exit_sequences.csv
  pass3_repair_sequences.csv
  pass3_holly_thread.csv
  pass3_dec2024_escalation.csv
  pass3_ownership_arc.csv
  pass3_deep_narrative.md
"""

import json, re, csv, os, sys, argparse
from datetime import datetime, timedelta
from collections import defaultdict

# ── Reuse parser from v2 ─────────────────────────────────────────────────────

def parse_messages(content):
    rows = content.split("\n")
    msg_rows = [r.strip() for r in rows if r.strip().startswith("| \\[")]
    pat = re.compile(
        r"\| \\\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d+:\d+:\d+)[\s ]+([ap]m)\\\]\s+"
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
        text = text.replace("‎", "").replace(" ", " ").strip()
        if "encrypted" in text.lower() or "messages and calls" in text.lower():
            continue
        try:
            dt = datetime.strptime(f"{date_str} {time_str} {ampm.upper()}", "%m/%d/%y %I:%M:%S %p")
        except ValueError:
            continue
        messages.append({"datetime": dt, "date": dt.strftime("%Y-%m-%d"),
                         "time": dt.strftime("%H:%M:%S"), "speaker": speaker,
                         "message_text": text})
    messages.sort(key=lambda x: x["datetime"])
    for i, m in enumerate(messages):
        m["message_id"] = f"MSG_{i:05d}"
    return messages

# ── helpers ──────────────────────────────────────────────────────────────────

def fmt(msg, n=250):
    return f"[{msg['date']} {msg['time']}] {msg['speaker']}: {msg['message_text'][:n]}"

def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {len(rows):>6,} rows → {path}")

# ── A. Exit attempt sequences ─────────────────────────────────────────────────

EXIT_SIGNALS = re.compile(
    r"\b(annulment|divorce)\b|"
    r"i.m done with this relationship|done with this|"
    r"i will leave you|i.m leaving you|leaving you|"
    r"don.t talk to me i.m leaving|"
    r"report to home office.*divorce|"
    r"file for annulment|file for divorce",
    re.IGNORECASE,
)

def find_exit_sequences(messages, window=30):
    rows = []
    for i, msg in enumerate(messages):
        if msg["speaker"] != "Cady":
            continue
        if not EXIT_SIGNALS.search(msg["message_text"]):
            continue
        # Capture 5 before + exit + 30 after
        lo = max(0, i - 5)
        hi = min(len(messages) - 1, i + window)
        seq = []
        for j in range(lo, hi + 1):
            m = messages[j]
            role = "EXIT_SIGNAL" if j == i else ("BEFORE" if j < i else "AFTER")
            seq.append({
                "exit_signal_date": msg["date"],
                "exit_signal_text": msg["message_text"][:300],
                "seq_role": role,
                "date": m["date"],
                "time": m["time"],
                "speaker": m["speaker"],
                "message_text": m["message_text"],
                "henry_response_type": "",  # human to fill
            })
        rows.extend(seq)
    return rows

# ── B. Repair cycle sequences ─────────────────────────────────────────────────

INCIDENT_TAGS = {
    "CONTROL_OWNERSHIP", "CONTROL_TOTAL", "SEXUAL_PRESSURE",
    "SEXUAL_COMMERCIALISATION", "SEXUAL_OBJECTIFICATION",
    "ANGER_THREAT", "THREAT_VIOLENCE", "THREAT_HOUSING",
    "VIOLENCE_DIRECT", "DOCUMENT_CONTROL",
}

REPAIR_SIGNALS = re.compile(
    r"\b(sorry|apologise|apologize|forgive me|i didn.t mean|"
    r"didn.t mean to|won.t happen again|i love you so much|"
    r"miss you so much|please come back|i need you|"
    r"you.re everything|i was wrong|i fucked up|my bad)\b",
    re.IGNORECASE,
)

def find_repair_sequences(messages, extracts_path, window_after=20):
    """For each high-severity Henry incident, find the next repair message."""
    # Load extract tags
    tag_map = {}
    with open(extracts_path) as f:
        for r in csv.DictReader(f):
            tag_map[r["message_id"]] = r["all_codes"]

    rows = []
    for i, msg in enumerate(messages):
        mid = f"MSG_{i:05d}"
        tags = tag_map.get(mid, "")
        if not tags or msg["speaker"] != "Henry Woods":
            continue
        if not any(t in tags for t in INCIDENT_TAGS):
            continue
        # Look for repair in next 20 messages
        repair_idx = None
        for j in range(i + 1, min(len(messages), i + window_after + 1)):
            if REPAIR_SIGNALS.search(messages[j]["message_text"]):
                repair_idx = j
                break
        rows.append({
            "incident_date": msg["date"],
            "incident_time": msg["time"],
            "incident_speaker": msg["speaker"],
            "incident_text": msg["message_text"][:300],
            "incident_tags": tags,
            "repair_found": "YES" if repair_idx else "NO",
            "repair_date": messages[repair_idx]["date"] if repair_idx else "",
            "repair_speaker": messages[repair_idx]["speaker"] if repair_idx else "",
            "repair_text": messages[repair_idx]["message_text"][:300] if repair_idx else "",
            "gap_messages": (repair_idx - i) if repair_idx else "",
            "gap_hours": (
                round((messages[repair_idx]["datetime"] - msg["datetime"]).total_seconds() / 3600, 1)
                if repair_idx else ""
            ),
            "same_behaviour_later": "",  # human to fill
        })
    return rows

# ── C. Holly triangulation thread ─────────────────────────────────────────────

def holly_thread(messages, context=5):
    rows = []
    for i, msg in enumerate(messages):
        if "holly" not in msg["message_text"].lower():
            continue
        lo = max(0, i - context)
        hi = min(len(messages) - 1, i + context)
        for j in range(lo, hi + 1):
            m = messages[j]
            rows.append({
                "holly_mention_date": msg["date"],
                "holly_mention_speaker": msg["speaker"],
                "holly_mention_text": msg["message_text"][:300],
                "context_role": "TARGET" if j == i else ("BEFORE" if j < i else "AFTER"),
                "date": m["date"],
                "time": m["time"],
                "speaker": m["speaker"],
                "message_text": m["message_text"],
            })
    return rows

# ── D. December 2024 escalation ───────────────────────────────────────────────

HIGH_SEVERITY = re.compile(
    r"\b(control|slut|whore|holes|not allowed to say no|"
    r"trophy|sex club|rent you out|without protection|"
    r"totally control|will never|won.t ever|"
    r"my property|my slut|keeping her|keeping you)\b",
    re.IGNORECASE,
)

def dec2024_escalation(messages):
    rows = []
    for msg in messages:
        if not msg["date"].startswith("2024-12"):
            continue
        is_high = bool(HIGH_SEVERITY.search(msg["message_text"]))
        rows.append({
            "date": msg["date"],
            "time": msg["time"],
            "speaker": msg["speaker"],
            "message_text": msg["message_text"],
            "high_severity": "YES" if is_high else "",
        })
    return rows

# ── E. "Warming up / lads" — sexual commercialisation in action ───────────────

LADS_THREAD = re.compile(
    r"\b(lads|guys|men|blokes|warmed up|warm you up|rent you|"
    r"share you|passing you|hand you|borrow you|loan you|"
    r"multiple guys|a few guys|a few men|other guys|other men|"
    r"content|shoot content|pornhub|onlyfans|film you|"
    r"pay for sex|pay for access|sugar|sponsor)\b",
    re.IGNORECASE,
)

def lads_thread(messages, context=10):
    rows = []
    seen = set()
    for i, msg in enumerate(messages):
        if not LADS_THREAD.search(msg["message_text"]):
            continue
        lo = max(0, i - context)
        hi = min(len(messages) - 1, i + context)
        for j in range(lo, hi + 1):
            uid = (i, j)
            if uid in seen:
                continue
            seen.add(uid)
            m = messages[j]
            rows.append({
                "trigger_date": msg["date"],
                "trigger_speaker": msg["speaker"],
                "trigger_text": msg["message_text"][:200],
                "context_role": "TARGET" if j == i else ("BEFORE" if j < i else "AFTER"),
                "date": m["date"],
                "time": m["time"],
                "speaker": m["speaker"],
                "message_text": m["message_text"],
            })
    return rows

# ── F. "Not even a joke" exchange — full context ──────────────────────────────

def not_a_joke_thread(messages, context=15):
    rows = []
    for i, msg in enumerate(messages):
        t = msg["message_text"].lower()
        if any(p in t for p in ["not even as a joke", "not even a joke",
                                  "not joking", "i'm serious", "i am serious",
                                  "deadly serious", "i mean it"]):
            lo = max(0, i - context)
            hi = min(len(messages) - 1, i + context)
            for j in range(lo, hi + 1):
                m = messages[j]
                rows.append({
                    "trigger_date": msg["date"],
                    "trigger_text": msg["message_text"][:200],
                    "context_role": "TARGET" if j == i else ("BEFORE" if j < i else "AFTER"),
                    "date": m["date"],
                    "time": m["time"],
                    "speaker": m["speaker"],
                    "message_text": m["message_text"],
                })
    return rows

# ── G. Ownership language arc — first → last ──────────────────────────────────

OWNERSHIP = re.compile(
    r"\b(my slut|trophy slut|my trophy|my property|my girl|"
    r"keep you|keeping you|belong to me|you.re mine|she.s mine|"
    r"my whore|my hole|my little|warming up|warmed up|"
    r"total control|under my control|dom.sub|d.s|24.7|"
    r"chained to|rent you|rent her)\b",
    re.IGNORECASE,
)

def ownership_arc(messages):
    rows = []
    for msg in messages:
        if msg["speaker"] != "Henry Woods":
            continue
        if OWNERSHIP.search(msg["message_text"]):
            rows.append({
                "date": msg["date"],
                "time": msg["time"],
                "message_text": msg["message_text"],
                "pattern_matched": ", ".join(OWNERSHIP.findall(msg["message_text"])),
            })
    return rows

# ── H. Henry-only word frequency ─────────────────────────────────────────────

STOP_WORDS = set("""
a about all also am an and any are as at be been being but by can
could do don dont for from get got had has have he her him his how
i if in into is it its i've i'm i'll i'd just know like ll m me
my no not now of on one or our out re s she so some t that the
their them then there they this to too up us was we well were what
when which who will with would you your ve
""".split())

def henry_word_freq(messages, top_n=100):
    freq = defaultdict(int)
    for msg in messages:
        if msg["speaker"] != "Henry Woods":
            continue
        words = re.findall(r"\b[a-z']{3,}\b", msg["message_text"].lower())
        for w in words:
            if w not in STOP_WORDS:
                freq[w] += 1
    return [{"word": w, "count": c}
            for w, c in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]

# ── Markdown deep narrative ───────────────────────────────────────────────────

LEGAL_CAVEAT = (
    "> **LEGAL CAVEAT**: Working analytical tool only. Consult a specialist DA "
    "solicitor or IDVA before any legal use. **National DA Helpline: 0808 2000 247**."
)

def build_narrative(
    exit_rows, repair_rows, holly_rows, dec_rows,
    lads_rows, notjoke_rows, ownership_rows, word_freq
):
    lines = ["# Pass 3 Deep Dive — Evidence Narrative", "", LEGAL_CAVEAT, "", "---", ""]

    # Summary stats
    exit_signals = [r for r in exit_rows if r["seq_role"] == "EXIT_SIGNAL"]
    repair_found = [r for r in repair_rows if r["repair_found"] == "YES"]
    henry_ownership = ownership_rows

    lines += [
        "## Pass 3 Summary", "",
        f"| Finding | Count |", f"|---------|-------|",
        f"| Exit attempt sequences captured | {len(set(r['exit_signal_date']+r['exit_signal_text'][:50] for r in exit_rows if r['seq_role']=='EXIT_SIGNAL'))} |",
        f"| High-severity Henry incidents with repair within 20 messages | {len(repair_found)} |",
        f"| Ownership/control language hits (Henry) | {len(henry_ownership)} |",
        f"| Holly triangulation events | {len(set(r['holly_mention_date']+r['holly_mention_text'][:30] for r in holly_rows if r['context_role']=='TARGET'))} |",
        f"| 'Lads / warming up' thread hits | {len(set(r['trigger_date']+r['trigger_text'][:30] for r in lads_rows if r['context_role']=='TARGET'))} |",
        "",
    ]

    # A. Exit attempts
    lines += ["---", "", "## A. Exit Attempt Sequences", "",
              "*What did Henry say in the 30 messages after each exit attempt?*", ""]

    seen_exits = set()
    for r in exit_rows:
        if r["seq_role"] != "EXIT_SIGNAL":
            continue
        uid = r["exit_signal_date"] + r["exit_signal_text"][:30]
        if uid in seen_exits:
            continue
        seen_exits.add(uid)
        lines.append(f"### Exit signal: {r['exit_signal_date']}")
        lines.append(f"> {r['exit_signal_text']}")
        lines.append("")
        henry_after = [x for x in exit_rows
                        if x["exit_signal_date"] == r["exit_signal_date"]
                        and x["exit_signal_text"][:30] == r["exit_signal_text"][:30]
                        and x["seq_role"] == "AFTER"
                        and x["speaker"] == "Henry Woods"]
        if henry_after:
            lines.append("**Henry's responses after:**")
            for h in henry_after[:10]:
                lines.append(f"- `{h['date']} {h['time']}` {h['message_text'][:200]}")
        else:
            lines.append("*No Henry responses captured in window.*")
        lines.append("")

    # B. Repair cycle — top 10 shortest repair gaps
    lines += ["---", "", "## B. Repair Cycle — Fastest Apologies After High-Severity Messages", "",
              "*Incident → apology gap (hours). Short gaps suggest a practiced cycle.*", "",
              "| Incident date | Incident (truncated) | Repair gap (hrs) | Repair speaker | Repair text |",
              "|--------------|---------------------|-----------------|----------------|-------------|"]

    fast_repairs = sorted(
        [r for r in repair_rows if r["repair_found"] == "YES" and r["gap_hours"] != ""],
        key=lambda x: float(x["gap_hours"]) if x["gap_hours"] else 9999
    )
    for r in fast_repairs[:20]:
        inc_short = r["incident_text"][:80].replace("|", "\\|")
        rep_short = r["repair_text"][:80].replace("|", "\\|")
        lines.append(f"| {r['incident_date']} | {inc_short} | {r['gap_hours']}h | {r['repair_speaker']} | {rep_short} |")
    lines.append("")

    # C. Holly thread
    lines += ["---", "", "## C. Holly Triangulation — Chronological Thread", "",
              "*Every time Henry mentions Holly, with context.*", ""]
    seen_holly = set()
    for r in holly_rows:
        if r["context_role"] != "TARGET":
            continue
        uid = r["holly_mention_date"] + r["holly_mention_text"][:30]
        if uid in seen_holly:
            continue
        seen_holly.add(uid)
        lines.append(f"**{r['holly_mention_date']} — {r['holly_mention_speaker']}:**")
        lines.append(f"> {r['holly_mention_text']}")
        lines.append("")

    # D. December 2024 escalation
    lines += ["---", "", "## D. December 2024 Escalation — First Major Spike", "",
              "*December 2024 shows 27 SEXUAL_OBJECTIFICATION + 51 FINANCIAL hits — "
              "the month where the pattern intensifies before the Jan 2025 peak.*", ""]
    high_dec = [r for r in dec_rows if r["high_severity"] == "YES" and r["speaker"] == "Henry Woods"]
    for r in high_dec[:30]:
        lines.append(f"- **{r['date']} {r['time']}**: {r['message_text'][:300]}")
    lines.append("")

    # E. Lads / warming up thread
    lines += ["---", "", "## E. Sexual Commercialisation in Action — 'Lads / Warming Up' Thread", "",
              "*Henry organising or referencing other men having sex with Cady. "
              "Legally significant under SOA 2003 s.74 (consent) and potentially "
              "s.52-53 (controlling prostitution).*", ""]
    lads_targets = [r for r in lads_rows if r["context_role"] == "TARGET"
                     and r["speaker"] == "Henry Woods"]
    seen_lads = set()
    for r in lads_targets:
        uid = r["date"] + r["trigger_text"][:20]
        if uid in seen_lads: continue
        seen_lads.add(uid)
        lines.append(f"**{r['date']} {r['time']} — Henry:**")
        lines.append(f"> {r['message_text'][:400]}")
        lines.append("")

    # F. Not-even-a-joke
    lines += ["---", "", "## F. 'Not Even a Joke' — Serious Statements Packaged as Banter", "",
              "*The HUMOUR_MASK mechanism: statements Henry confirmed were not jokes.*", ""]
    seen_nj = set()
    for r in notjoke_rows:
        if r["context_role"] != "TARGET":
            continue
        uid = r["date"] + r["trigger_text"][:20]
        if uid in seen_nj: continue
        seen_nj.add(uid)
        lines.append(f"**{r['date']} {r['time']}:**")
        lines.append(f"> {r['message_text'][:300]}")
        ctx = [x for x in notjoke_rows
                if x["trigger_date"] == r["date"] and x["trigger_text"][:20] == r["trigger_text"][:20]]
        for c in ctx:
            if c["context_role"] != "TARGET":
                lines.append(f"- [{c['context_role']}] `{c['date']}` **{c['speaker']}**: {c['message_text'][:200]}")
        lines.append("")

    # G. Ownership arc
    lines += ["---", "", "## G. Ownership Language Arc (Henry) — First to Last", "",
              "*How did the controlling/ownership language evolve? "
              "First appearance to last appearance.*", ""]
    for r in ownership_rows:
        lines.append(f"- **{r['date']}** `{r['pattern_matched']}` → {r['message_text'][:200]}")
    lines.append("")

    # H. Top 50 Henry words
    lines += ["---", "", "## H. Henry Word Frequency (top 50, stop words removed)", "",
              "*Psycholinguistic profile of Henry's language across 22 months.*", "",
              "| Rank | Word | Count |", "|------|------|-------|"]
    for i, r in enumerate(word_freq[:50], 1):
        lines.append(f"| {i} | {r['word']} | {r['count']} |")
    lines.append("")

    return "\n".join(lines)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--extracts", default="forensic/output_v2/04_extracts.csv")
    ap.add_argument("--output-dir", default="forensic/output_pass3")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    out = args.output_dir

    print("[1/9] Loading & parsing...")
    with open(args.data) as f:
        raw = f.read()
    try:
        content = json.loads(raw).get("fileContent", raw)
    except json.JSONDecodeError:
        content = raw
    messages = parse_messages(content)
    print(f"      {len(messages):,} messages")

    print("[2/9] A — Exit attempt sequences...")
    exit_rows = find_exit_sequences(messages)
    write_csv(f"{out}/pass3_exit_sequences.csv", exit_rows,
              ["exit_signal_date","exit_signal_text","seq_role","date","time",
               "speaker","message_text","henry_response_type"])

    print("[3/9] B — Repair cycle mapping...")
    repair_rows = find_repair_sequences(messages, args.extracts)
    write_csv(f"{out}/pass3_repair_sequences.csv", repair_rows,
              ["incident_date","incident_time","incident_speaker","incident_text",
               "incident_tags","repair_found","repair_date","repair_speaker",
               "repair_text","gap_messages","gap_hours","same_behaviour_later"])

    print("[4/9] C — Holly thread...")
    holly_rows = holly_thread(messages)
    write_csv(f"{out}/pass3_holly_thread.csv", holly_rows,
              ["holly_mention_date","holly_mention_speaker","holly_mention_text",
               "context_role","date","time","speaker","message_text"])

    print("[5/9] D — December 2024 escalation...")
    dec_rows = dec2024_escalation(messages)
    write_csv(f"{out}/pass3_dec2024_escalation.csv", dec_rows,
              ["date","time","speaker","message_text","high_severity"])

    print("[6/9] E — Lads / warming-up thread...")
    lads_rows = lads_thread(messages)
    write_csv(f"{out}/pass3_lads_thread.csv", lads_rows,
              ["trigger_date","trigger_speaker","trigger_text","context_role",
               "date","time","speaker","message_text"])

    print("[7/9] F — Not-even-a-joke thread...")
    nj_rows = not_a_joke_thread(messages)
    write_csv(f"{out}/pass3_not_a_joke.csv", nj_rows,
              ["trigger_date","trigger_text","context_role","date","time",
               "speaker","message_text"])

    print("[8/9] G+H — Ownership arc & word frequency...")
    own_rows = ownership_arc(messages)
    write_csv(f"{out}/pass3_ownership_arc.csv", own_rows,
              ["date","time","message_text","pattern_matched"])
    wf = henry_word_freq(messages)
    write_csv(f"{out}/pass3_henry_word_freq.csv", wf, ["word","count"])

    print("[9/9] Building narrative...")
    md = build_narrative(exit_rows, repair_rows, holly_rows, dec_rows,
                         lads_rows, nj_rows, own_rows, wf)
    md_path = f"{out}/pass3_deep_narrative.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"       narrative → {md_path}")

    # Quick stats to console
    repair_found = [r for r in repair_rows if r["repair_found"]=="YES"]
    exit_signals = len(set(r["exit_signal_date"]+r["exit_signal_text"][:20]
                           for r in exit_rows if r["seq_role"]=="EXIT_SIGNAL"))
    print(f"\n  Exit signals: {exit_signals}")
    print(f"  Repair cycles found: {len(repair_found)} / {len(repair_rows)}")
    print(f"  Ownership arc entries: {len(own_rows)}")
    print(f"\nDone. Output: {out}/")


if __name__ == "__main__":
    main()
