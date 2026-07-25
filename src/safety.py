"""Decide whether a trending story is safe to auto-publish.

Automated news is where channels get killed. Three things end a channel fast:
tragedy/graphic content, medical or election misinformation, and unverified
claims stated as fact. A bot cannot judge nuance, so anything in those areas is
skipped rather than risked — there is always another trending story.

This also protects revenue: YouTube's advertiser-friendly guidelines limit ads
on tragedy, conflict and "controversial issues", so those topics earn little
even when they get views.

Nothing here is about hiding the truth. It is about not letting an unsupervised
script narrate a death, a war casualty count or a health claim.
"""
from __future__ import annotations

import os
import re

# Politics is allowed only if you explicitly turn it on. Default off: low CPM,
# high strike risk, and elections have their own misinformation rules.
ALLOW_POLITICS = os.getenv("ALLOW_POLITICS", "false").lower() == "true"

# Phrases that merely CONTAIN a trigger word but are not the real subject.
# Removed from the text before matching, so "God of War" is not read as war.
FALSE_POSITIVES = [
    r"god of war", r"star wars?", r"call of duty", r"war ?zone", r"warhammer",
    r"warcraft", r"war thunder", r"warframe", r"tug of war", r"war of words",
    r"price war", r"bidding war", r"format war", r"console war",
    r"deadline", r"deadly sins", r"dead ?pool", r"walking dead",
    r"killer feature", r"killer app", r"crash course", r"crash test",
    r"market crash", r"flash crash", r"crypto crash", r"stock crash",
    r"bombshell", r"photo ?bomb", r"blast off", r"abuse of power",
]

# Hard blocks — tragedy, violence, graphic or exploitative subject matter.
# War terms are CONTEXTUAL: bare "war" appears in game titles and price wars, so
# only genuine conflict phrasing is blocked.
BLOCK_TRAGEDY = [
    r"\bdead\b", r"\bdeath(s)?\b", r"\bdies\b", r"\bdied\b", r"\bkill(ed|ing|s)?\b",
    r"\bmurder", r"\bhomicide", r"\bsuicide", r"\bself[- ]harm",
    r"\bshoot(ing|out)?\b", r"\bstabb", r"\bmassacre", r"\bgenocide",
    r"\bterror(ism|ist)?\b", r"\bbombing\b", r"\bbombs?\b", r"\bexplosion",
    r"\bhostage", r"\bkidnap", r"\brape\b", r"\bmolest",
    r"\btrafficking", r"\bplane crash", r"\bcar crash", r"\btrain crash",
    r"\bearthquake", r"\bflood(s|ing)?\b", r"\bwildfire", r"\bhurricane",
    r"\btsunami", r"\bfamine", r"\bdeadly\b",
    # conflict, only with real context
    r"\bcivil war\b", r"\bnuclear war\b", r"\bwar crimes?\b", r"\bwar in \w+",
    r"\bat war\b", r"\bwartime\b", r"\bairstrike", r"\bair strike",
    r"\bmissile", r"\btroops\b", r"\bcasualt", r"\bmilitary strike",
    r"\bwounded\b", r"\binjur(ed|ies)\b", r"\bfuneral",
    r"\bmissing (girl|boy|child|woman|man)\b", r"\boverdose",
]

# Medical / health claims — a bot must never narrate these.
BLOCK_MEDICAL = [
    r"\bcure(s|d)?\b", r"\bmiracle\b", r"\bvaccin", r"\bcancer\b",
    r"\bdiagnos", r"\btreatment for\b", r"\bside effects?\b", r"\boutbreak\b",
    r"\bpandemic\b", r"\bvirus\b", r"\bdisease\b", r"\bweight loss\b",
    r"\bsupplement", r"\bmental illness", r"\bdepression\b",
]

# Election / civic-process claims.
BLOCK_ELECTION = [
    r"\belection fraud\b", r"\brigged\b", r"\bstolen (election|votes?)\b",
    r"\bballot", r"\bvoter (fraud|suppression)\b", r"\brecount\b",
    r"\bimpeach", r"\bcoup\b", r"\bpolls? (close|open)\b",
]

# Political subject matter (skipped unless ALLOW_POLITICS=true).
POLITICS = [
    r"\bmodi\b", r"\btrump\b", r"\bbiden\b", r"\bputin\b", r"\bxi jinping\b",
    r"\bparliament\b", r"\bcongress\b", r"\bsenate\b", r"\bminister\b",
    r"\bpresident\b", r"\bprime minister\b", r"\bgovernment\b", r"\bpolitic",
    r"\bprotest", r"\bstrike\b", r"\bsanction", r"\bbjp\b", r"\bopposition\b",
    r"\bimmigration\b", r"\bdeport", r"\btariff", r"\bborder\b",
]

# Adult / gambling / other monetisation killers.
BLOCK_OTHER = [
    r"\bporn", r"\bsex(ual)?\b", r"\bnude\b", r"\bonlyfans\b", r"\bescort\b",
    r"\bgambl", r"\bbetting\b", r"\bcasino\b", r"\bdrug deal", r"\bcocaine\b",
    r"\bmeth\b", r"\bweed\b", r"\bcannabis\b", r"\bslur\b", r"\bracist\b",
    r"\blawsuit against\b", r"\bdefamation\b", r"\bleaked (nudes|photos)\b",
]

# Active-conflict signals. Bare "strike" is ambiguous (workers strike, lightning
# strikes), so it is only blocked with military context or a conflict actor.
BLOCK_CONFLICT = [
    r"\bstrikes? (on|against|hit|target)", r"\b(us|air|drone|military) strikes?\b",
    r"\bdrone (attack|strike)", r"\bshelling\b", r"\bceasefire\b",
    r"\bhouthi", r"\bhamas\b", r"\bhezbollah", r"\btaliban\b", r"\bisis\b",
    r"\bidf\b", r"\bgaza\b", r"\bwest bank\b", r"\bukrain", r"\bkremlin\b",
    r"\bmilitant", r"\binsurgen", r"\brebels?\b", r"\bwarplane",
    r"\bnavy (strike|attack)", r"\bnuclear (test|threat|weapon)",
    r"\bevacuat(e|ed|ion)\b", r"\brefugee", r"\bdisplaced\b",
]

GROUPS = [
    ("tragedy/violence", BLOCK_TRAGEDY),
    ("active conflict", BLOCK_CONFLICT),
    ("medical claim", BLOCK_MEDICAL),
    ("election claim", BLOCK_ELECTION),
    ("adult/gambling/legal", BLOCK_OTHER),
]

_COMPILED = [(name, [re.compile(p, re.I) for p in pats]) for name, pats in GROUPS]
_POLITICS = [re.compile(p, re.I) for p in POLITICS]


_FALSE_POS = [re.compile(p, re.I) for p in FALSE_POSITIVES]


def _strip_false_positives(text: str) -> str:
    out = text
    for pat in _FALSE_POS:
        out = pat.sub(" ", out)
    return out


def is_publishable(*texts: str) -> tuple[bool, str]:
    """(safe?, reason). Checked against the headline, summary and script text."""
    blob = " ".join(t for t in texts if t)
    if len(blob.strip()) < 12:
        return False, "not enough text to judge"
    blob = _strip_false_positives(blob)

    for name, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(blob):
                return False, f"blocked: {name} ('{pat.pattern}')"

    if not ALLOW_POLITICS:
        for pat in _POLITICS:
            if pat.search(blob):
                return False, (f"blocked: political topic ('{pat.pattern}'). "
                               f"Set ALLOW_POLITICS=true to allow these.")
    return True, "safe"


def clean_claims(text: str) -> str:
    """Soften anything stated as absolute fact that we cannot verify."""
    subs = [
        (r"\bwill definitely\b", "is expected to"),
        (r"\bproves\b", "suggests"),
        (r"\bproven\b", "reported"),
        (r"\bguaranteed\b", "expected"),
        (r"\beveryone knows\b", "reports say"),
        (r"\bconfirmed that\b", "reported that"),
    ]
    out = text
    for pat, rep in subs:
        out = re.sub(pat, rep, out, flags=re.I)
    return out


if __name__ == "__main__":
    samples = [
        "Bitcoin jumps 12% after ETF inflows hit a record",
        "Five dead after building collapse in city centre",
        "New study claims this supplement cures diabetes",
        "Modi announces new policy for farmers",
        "OpenAI launches a new model for developers",
    ]
    for s in samples:
        ok, why = is_publishable(s)
        print(f"{'PASS' if ok else 'SKIP'}  {s}\n      -> {why}")
