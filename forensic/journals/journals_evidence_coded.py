"""
Journal + Transcript Evidence Coder
Applies the v2 forensic codebook to Cady's contemporaneous records.
Produces: coded evidence CSV + summary statistics.
"""

import csv
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Coded evidence entries — hand-coded from journals + transcripts
# format: date, source, speaker, text, tags, legal_ref, notes
EVIDENCE = [
    # ─── DECEMBER 2025 ───────────────────────────────────────────────────────

    ("2025-12-14", "Constellation poem", "Cady",
     "The star of credibility denial / The star of avoidance dressed as 'ADHD vibes' / The star of you building a lab to survive a home",
     "REALITY_UNDERMINE|MINIMISATION|FEAR_BY_CADY_DOCUMENTED",
     "SCA 2015 s.76",
     "Contemporaneous naming of control pattern 5 months before crisis. 'Lab to survive a home' = coercive control frame."),

    ("2025-12-14", "Union Session document", "Cady",
     "Friction most often arises when: Stress responses (overwhelm, defensiveness, withdrawal) outrun regulation",
     "MINIMISATION|REPAIR_CYCLE",
     "SCA 2015 s.76 — CPS CC guidance",
     "Cady trying to create formal governance structures to solve the problem. Evidence of her attempts before leaving."),

    ("2025-12-14", "Union Session document — Conflict Doctrine", "Cady",
     "Patterns formally retired: Raised voices as a regulation strategy / Indefinite withdrawal during moments of overwhelm",
     "CONTROL_OWNERSHIP|ISOLATION_SOCIAL",
     "SCA 2015 s.76",
     "Contemporaneous record of what behaviours required formal 'retirement' — implies repeated prior occurrence."),

    ("2025-12-15", "Letter to Henry — financial", "Cady",
     "The money stuff landed hard. Not just the £12k, but realizing it had been avoided since I moved in. I think what surprised me most is that it took an acid trip for that protection mechanism to drop.",
     "DEPENDENCY_FINANCIAL|MINIMISATION",
     "SCA 2015 s.76 — coercive control / financial abuse",
     "£12k non-disclosure confirmed. Avoidance 'since I moved in' = systematic. Requires altered state to disclose = shame/control dynamic."),

    ("2025-12-15", "Letter to Henry — sexual", "Cady",
     "Same with the sex and disclosure. I stayed calm, but that doesn't mean it didn't matter. I'm sexually open and confident, but I still need to be informed and protected. I need to know that my body is being treated with care, not as something that will probably be fine.",
     "SEXUAL_PRESSURE|DEPENDENCY_FINANCIAL",
     "SOA 2003 s.74 — consent / sexual health disclosure",
     "Sexual non-disclosure (STI/exposure risk implied). Cady's body treated as 'probably fine' without her informed consent."),

    ("2025-12-15", "Letter to Henry — request", "Cady",
     "What I need going forward is less protection through avoidance and more honesty early — especially with money and anything that affects my body or our stability.",
     "EXIT_ATTEMPT|REPAIR_CYCLE",
     "CPS CC guidance — pattern documentation",
     "Clear request for change. Written in regulated state. Not heeded — corroborated by April 2026 crisis."),

    # ─── JANUARY 2026 ────────────────────────────────────────────────────────

    ("2026-01-05", "Values worksheet", "Cady",
     "Reality and trust (we don't distort, debate, or litigate your inner world) / Partnership, not ownership (I'm not an accessory/assistant)",
     "REALITY_UNDERMINE|CONTROL_OWNERSHIP",
     "SCA 2015 s.76",
     "Cady naming 'ownership' and 'reality distortion' as problems by Jan 5, 2026. Entry tagged #DA signs by Cady herself."),

    ("2026-01-06", "Boundary statement — verbatim", "Cady",
     "When you feel criticised, you escalate and become punitive. That's not acceptable to me. If it happens again, I will end the conversation immediately and leave the space.",
     "EXIT_ATTEMPT|BLAME_SHIFT",
     "CPS CC guidance — exit attempt documentation",
     "Verbatim, 6 January 2026. First formal exit warning. Corroborates pattern of Henry escalating when challenged."),

    ("2026-01-06", "Five stated limits — written", "Cady",
     "No threats (divorce/leaving) during conflict. / No reality games: no denying/reframing what just happened. / No contempt, no intimidation, no swearing at me. / If any of those are broken, I will proceed with separation planning.",
     "EXIT_ATTEMPT|REALITY_UNDERMINE|MINIMISATION",
     "SCA 2015 s.76 — CPS CC guidance",
     "Five written limits with consequence stated. Date: 6 Jan 2026. Henry violated all five by April 2026."),

    ("2026-01-10", "Granola transcript 1 — DARVO", "Henry",
     "me saying, I'm upset at this thing and you going, you have no right to be. [...] I've just now said. So I've now said that you've done something. Your immediate response is, no, I haven't.",
     "DARVO|BLAME_SHIFT|REALITY_UNDERMINE",
     "CPS CC guidance — DARVO pattern",
     "Henry framing Cady's self-defence as 'abusive.' Classic DARVO. Both parties recording — confirms mutual recording context."),

    ("2026-01-10", "Granola transcript 1 — self-protection frame", "Henry",
     "My thinking now currently is. I need to protect myself.",
     "DARVO|MINIMISATION",
     "CPS CC guidance",
     "Henry deploying 'self-protection' frame after Cady names pattern. Stonewalling follows immediately."),

    ("2026-01-10", "Granola transcript 1 — legal threat", "Cady",
     "I will never. The last thing you need is a fucking legal situation. I would never do that to you. What could that do for me? Create more pain for everyone. That is 100% against my entire philosophy of life.",
     "EXIT_BLOCKED|DARVO",
     "CPS CC guidance",
     "Henry accused Cady of threatening jail. Cady denied it clearly. Transcript evidence = Henry weaponising legal threat concern."),

    ("2026-01-10", "Granola transcript 2 — contempt naming", "Cady",
     "It's belittling and humiliating, which is one of the legal definitions that I'm going to write down about.",
     "DARVO|EXIT_ATTEMPT",
     "SCA 2015 s.76 — domestic abuse awareness",
     "Cady naming legal definitions in real time. Henry immediately weaponises: 'So you're building a legal case against me now?'"),

    ("2026-01-10", "Granola transcript 2 — DARVO explicit", "Henry",
     "So you're building a legal case against me now?",
     "DARVO|REALITY_UNDERMINE",
     "CPS CC guidance — DARVO",
     "Immediate weaponisation of Cady naming the pattern. Classic DARVO move."),

    ("2026-01-10", "Granola transcript 2 — Henry threat to leave", "Henry",
     "If you do that I will leave. I will pack and leave.",
     "THREAT_EXPLICIT|EXIT_BLOCKED",
     "SCA 2015 s.76 — coercive control",
     "Henry threatening to leave if Cady pursues legal advice. Directly blocking her access to support."),

    ("2026-01-10", "Granola transcript 2 — GP evidence", "Cady",
     "My GP recommends I go get advice about this.",
     "FEAR_BY_CADY_DOCUMENTED|EXIT_ATTEMPT",
     "DA Act 2021 — health impact",
     "GP recommendation confirmed. Contemporaneous medical professional awareness of domestic situation."),

    ("2026-01-10", "Granola transcript 2 — false claim", "Henry",
     "I did not say that. [re: 'journals could send you to jail']",
     "REALITY_UNDERMINE|DARVO",
     "CPS CC guidance — gaslighting",
     "Henry denying statement that Cady clearly recalls. Both parties recording — Henry aware of transcript evidence but still denying."),

    ("2026-01-10", "Granola transcript 3 — boundary ignored", "Cady",
     "I have asked you to pause. [...] But you have not. [...] I've asked you different ways to go upstairs. I've said I'm. But you just ignore me.",
     "BOUNDARY_VIOLATION|CONTROL_TOTAL|EXIT_BLOCKED",
     "SCA 2015 s.76",
     "Cady requesting space repeatedly; Henry refusing to leave the room. Controlling physical space."),

    ("2026-01-10", "Granola transcript 3 — space control", "Cady",
     "I don't understand the need to control it. Being right here together, when it's tense.",
     "CONTROL_TOTAL|EXIT_BLOCKED",
     "SCA 2015 s.76 — coercive control",
     "Cady explicitly naming the control. Henry dismisses: 'Control it?'"),

    ("2026-01-11", "Bancroft exit plan", "Cady",
     "You are not doing 'separation' as an emotional event. You're doing it as a sequence: Phase 1: Buy time. Phase 2: Secure status/right-to-work. Phase 3: Build independent income + housing. Phase 4: Separate cleanly.",
     "EXIT_ATTEMPT|DEPENDENCY_IMMIGRATION",
     "DA Act 2021 — trapped victim with immigration constraints",
     "Contemporaneous documentation of exit planning. Visa dependency = DEPENDENCY_IMMIGRATION constraint. Not inability to leave — deliberate strategic sequencing."),

    ("2026-01-11", "Henry suicidal threat", "Henry",
     "'he's just like his father I feel, just like whoah is me… I wanna die' — whiplash emotionally",
     "THREAT_EXPLICIT|DARVO",
     "CPS CC guidance — emotional coercion",
     "Henry's suicidal statement documented by Cady. Kit called as witness. 'Whiplash' = Cady's contemporaneous emotional response. Potential coercive use of mental health crisis."),

    ("2026-01-11", "Kit as witness", "Kit",
     "'That was so good' — Kit, re: Cady's conversation about Henry with Jackie, after Kit was called due to Henry's suicidal threat",
     "FEAR_BY_CADY_DOCUMENTED",
     "DA Act 2021 — third party witness",
     "Kit as potential third-party witness to suicidal threat incident. Present at house, called by Cady."),

    ("2026-01-11", "Financial abuse documented", "Cady",
     "Henry has no income but is consuming high-burn discretionary nights. £100 on coke. Night-long benders ~£200/event. Net cashflow ≈ –£2,000/mo. Cady: 'your nervous system has normalized it — which means we should not.'",
     "DEPENDENCY_FINANCIAL|CONTROL_OWNERSHIP",
     "SCA 2015 s.76 — financial control",
     "Henry spending on cocaine with no income while household is -£2000/mo. Cady tracking all finances. Financial dependency documented."),

    ("2026-01-11", "Housing precarity noted", "Cady",
     "'Dad doesn't want it given to Henry then I get kicked out'",
     "DEPENDENCY_HOUSING",
     "Housing Act 1996 s.177 — domestic violence and homelessness",
     "Cady documenting fear of being evicted if parental money goes to Henry. Not on mortgage. Housing precarity = DEPENDENCY_HOUSING."),

    ("2026-01-15", "Physical symptoms — visa approval day", "Cady",
     "I've probably lost about five pounds from the stress, from the constant readiness. Even with today's relief, my body still half-expects the other shoe to drop.",
     "FEAR_BY_CADY_DOCUMENTED",
     "DA Act 2021 — physical health impact",
     "5lb weight loss documented. Stress physical manifestation. Date: 15 January 2026 — same day as visa approval."),

    ("2026-01-15", "Emotional inventory — rage", "Cady",
     "Rage. At how much I've had to manage alone. At the constant bracing. At needing to make my life legible as 'proof.' Rage that doesn't need to burn anything down today—just needs to be acknowledged as information: this has been too much. I have carried too much.",
     "FEAR_BY_CADY_DOCUMENTED|DEPENDENCY_FINANCIAL",
     "DA Act 2021 — psychological harm",
     "Contemporaneous emotional inventory. 'Constant bracing' = hypervigilance. 'Making life legible as proof' = DEPENDENCY_IMMIGRATION stress."),

    ("2026-01-15", "Relief — from dependency lifting", "Cady",
     "Right to work isn't admin. It's access. It's ground. It's becoming myself in public. It's the right to apply, to earn, to choose what I do — to stop asking for permission and start moving it through.",
     "DEPENDENCY_IMMIGRATION",
     "Immigration Rules Appendix FM — spousal visa constraint",
     "Visa = permission to exist economically. Losing it = total dependency on Henry. Contemporaneous record of what immigration dependency meant."),

    ("2026-01-15", "Grief — for lost home", "Cady",
     "Grief. For what I wanted 'home' to mean. For the version of marriage I've been craving. For the version of Henry I believed in—the one I thought I was building alongside.",
     "FEAR_BY_CADY_DOCUMENTED|FUTURE_FAKE",
     "SCA 2015 s.76 — coercive control harm",
     "Grief for promised future not delivered. Corroborates FUTURE_FAKE pattern in WhatsApp corpus."),

    ("2026-01-17", "Kin narrative — Henry post-wedding", "Cady",
     "You describe a different layer: stressed finances, lack of planning, and you holding most of the emotional and logistical labor. When you confronted him, he said your requests were fair, but you did not see apology, ownership, or follow-through.",
     "REPAIR_CYCLE|MINIMISATION|DEPENDENCY_FINANCIAL",
     "CPS CC guidance — practiced cycle",
     "Written Jan 17, 2026. Pattern of repair without follow-through documented. Corroborates 83 WhatsApp REPAIR_CYCLE messages."),

    ("2026-01-17", "Kin narrative — watching behaviour", "Cady",
     "You are watching what he does, not what he says.",
     "EXIT_ATTEMPT|FEAR_BY_CADY_DOCUMENTED",
     "CPS CC guidance",
     "Contemporaneous record of Cady's watchful, strategic stance — not passive, not oblivious. Active monitoring."),
]


def write_coded_csv():
    out_path = OUTPUT_DIR / "journals_coded_evidence.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "source", "speaker", "text", "tags", "legal_ref", "notes"])
        for row in EVIDENCE:
            writer.writerow(row)
    print(f"Written: {out_path} ({len(EVIDENCE)} entries)")


def write_summary():
    # Count tags
    tag_counts = {}
    for entry in EVIDENCE:
        for tag in entry[4].split("|"):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Group by source type
    sources = {}
    for entry in EVIDENCE:
        src = entry[1].split(" — ")[0]
        sources[src] = sources.get(src, 0) + 1

    # Legal refs
    legal_refs = {}
    for entry in EVIDENCE:
        for ref in entry[5].split(" — "):
            r = ref.strip()
            if r:
                legal_refs[r] = legal_refs.get(r, 0) + 1

    out_path = OUTPUT_DIR / "journals_evidence_summary.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Journal Evidence Summary\n")
        f.write(f"## {len(EVIDENCE)} coded entries from contemporaneous records\n\n")

        f.write("## Tag Frequency\n```\n")
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            bar = "█" * count
            f.write(f"{tag:<35} {count:>3}  {bar}\n")
        f.write("```\n\n")

        f.write("## Evidence by Source\n```\n")
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            f.write(f"{src:<45} {count:>3}\n")
        f.write("```\n\n")

        f.write("## Legal Framework Coverage\n```\n")
        for ref, count in sorted(legal_refs.items(), key=lambda x: -x[1]):
            f.write(f"{ref:<45} {count:>3}\n")
        f.write("```\n\n")

        f.write("## Key Evidence by Category\n\n")

        # Exit attempts
        exits = [e for e in EVIDENCE if "EXIT_ATTEMPT" in e[4]]
        f.write(f"### Exit Attempts ({len(exits)} documented)\n")
        for e in exits:
            f.write(f"- **{e[0]}** ({e[1]}): {e[6]}\n")
        f.write("\n")

        # Fear documented
        fears = [e for e in EVIDENCE if "FEAR_BY_CADY" in e[4]]
        f.write(f"### Fear / Harm Documented ({len(fears)} entries)\n")
        for e in fears:
            f.write(f"- **{e[0]}**: {e[2]} — {e[3][:80]}...\n")
        f.write("\n")

        # DARVO
        darvos = [e for e in EVIDENCE if "DARVO" in e[4]]
        f.write(f"### DARVO Pattern ({len(darvos)} instances — journal/transcript corroboration)\n")
        for e in darvos:
            f.write(f"- **{e[0]}** ({e[1]}): \"{e[3][:80]}...\"\n")
        f.write("\n")

        # Financial
        financial = [e for e in EVIDENCE if "DEPENDENCY_FINANCIAL" in e[4] or "FINANCIAL" in e[4]]
        f.write(f"### Financial Abuse / Dependency ({len(financial)} entries)\n")
        for e in financial:
            f.write(f"- **{e[0]}**: {e[6]}\n")
        f.write("\n")

        # Immigration
        imm = [e for e in EVIDENCE if "DEPENDENCY_IMMIGRATION" in e[4]]
        f.write(f"### Immigration Dependency ({len(imm)} entries)\n")
        for e in imm:
            f.write(f"- **{e[0]}**: {e[6]}\n")
        f.write("\n")

    print(f"Written: {out_path}")


def write_timeline_json():
    """Produce a combined timeline JSON for cross-referencing with WhatsApp corpus."""
    timeline = []
    for entry in EVIDENCE:
        timeline.append({
            "date": entry[0],
            "source": entry[1],
            "speaker": entry[2],
            "text": entry[3],
            "tags": entry[4].split("|"),
            "legal_ref": entry[5],
            "notes": entry[6],
            "evidence_type": "CONTEMPORANEOUS_RECORD"
        })
    out_path = OUTPUT_DIR / "journals_timeline.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, ensure_ascii=False)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    write_coded_csv()
    write_summary()
    write_timeline_json()
    print("\nDone. Journal evidence coded and exported.")
