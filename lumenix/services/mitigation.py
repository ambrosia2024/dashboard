"""
Retrieval of food-safety control measures for Ambra (issue #112).

The corpus is small and curated - a couple of dozen clause-level measures drawn
from Codex texts - so every active row is loaded and ranked in Python. That is
deliberate: at this size it is faster than a full-text query, it needs no new
database extension, and the ranking is plain enough to argue with. Swap in
Postgres full-text search, or embeddings, when the corpus outgrows a few hundred
rows; `measures_for` is the only thing that would change.

Nothing here invents guidance. Every row is a paraphrase of a numbered clause and
carries the citation and link back to the published standard.
"""

import logging
import re

from lumenix.models import MitigationMeasure

logger = logging.getLogger(__name__)

# Words too common to say anything about which clause is relevant.
_STOPWORDS = {
    "what", "which", "when", "where", "how", "why", "should", "could", "would",
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "this", "that",
    "there", "their", "they", "it", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "can", "about", "into", "over", "under", "my", "our",
    "me", "we", "you", "your", "i", "to", "of", "in", "on", "at", "by", "as",
    "if", "so", "not", "no", "any", "all", "some", "more", "most", "than",
}

# A question mentioning any of these is asking about the thing the dashboard
# actually models, so temperature and cold-chain clauses move up the ranking.
_TEMPERATURE_HINTS = {
    "temperature", "temperatures", "warm", "warmer", "warming", "hot", "heat",
    "cold", "chill", "chilled", "cooling", "cool", "refrigeration", "refrigerated",
    "storage", "growth", "climate", "season", "summer",
}


# A crop is also its broader categories, so a clause written for "fresh produce"
# still applies to a lettuce. Without this the general clauses never match a
# specific crop and the ranking is decided entirely by the hazard tag.
_COMMODITY_PARENTS = {
    "lettuce": ("leafy vegetables", "vegetables", "fresh produce"),
    "spinach": ("leafy vegetables", "vegetables", "fresh produce"),
    "cabbage": ("leafy vegetables", "vegetables", "fresh produce"),
    "chicory": ("leafy vegetables", "vegetables", "fresh produce"),
    "endive": ("leafy vegetables", "vegetables", "fresh produce"),
    "rocket": ("leafy vegetables", "vegetables", "fresh produce"),
    "parsley": ("leafy vegetables", "vegetables", "fresh produce"),
    "basil": ("leafy vegetables", "vegetables", "fresh produce"),
    "leafy vegetables": ("vegetables", "fresh produce"),
    "tomato": ("vegetables", "fresh produce"),
    "melon": ("fruits", "fresh produce"),
    "berries": ("fruits", "fresh produce"),
    "sprouts": ("vegetables", "fresh produce"),
}

# Which part of the chain a question is about, so a field question does not get
# answered with a consumer-labelling clause.
_STAGE_HINTS = {
    "primary": {"farm", "field", "grow", "growing", "irrigation", "irrigate", "manure",
                "soil", "fertilizer", "fertiliser", "compost", "crop", "planting", "seed"},
    "harvest": {"harvest", "harvesting", "picking", "cooling", "cool", "precool", "vacuum"},
    "processing": {"pack", "packing", "packhouse", "processing", "process", "wash", "washing",
                   "rinse", "cut", "cutting", "facility", "plant", "equipment", "sanitation"},
    "storage": {"storage", "store", "storing", "transport", "distribution", "chain",
                "refrigeration", "refrigerated", "shelf", "fridge", "chilled", "cold"},
    "consumer": {"consumer", "consumers", "label", "labelling", "labeling", "retail",
                 "shop", "supermarket", "home", "kitchen"},
}


def _tokens(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOPWORDS}


def _commodity_terms(label):
    """The crop plus the broader categories it belongs to, all lowercase."""
    low = (label or "").lower().strip()
    if not low:
        return set()
    terms = {low}
    for key, parents in _COMMODITY_PARENTS.items():
        if key in low:
            terms.add(key)
            terms.update(parents)
    return terms


def _stages_for(question_tokens):
    return {stage for stage, words in _STAGE_HINTS.items() if question_tokens & words}


def _tag_matches(tags, label):
    """True when a tag and the label refer to the same thing, either way round.

    Tags are short ("lettuce", "listeria monocytogenes"), labels come from the
    run ("Iceberg lettuce", "Listeria monocytogenes"), so neither is reliably
    contained in the other - check both directions.
    """
    if not tags or not label:
        return False
    low = label.lower()
    for tag in tags:
        tag = (tag or "").lower().strip()
        if not tag:
            continue
        if tag in low or low in tag:
            return True
        # "Listeria monocytogenes" should still match a tag of "listeria".
        if any(part and part in low for part in tag.split() if len(part) > 4):
            return True
    return False


def _score(measure, crop, hazard, question_tokens, want_temperature, stages):
    """Relevance of one measure. Topic beats tags: a clause tagged for the right
    crop and hazard but about the wrong subject should lose to one that actually
    answers the question."""
    score = 0.0

    if measure.hazards:
        if _tag_matches(measure.hazards, hazard):
            score += 3.0
        else:
            # Written for a different hazard - almost never the right answer.
            score -= 2.0
    else:
        score += 0.5  # applies to any hazard

    if measure.commodities:
        terms = _commodity_terms(crop)
        if any(_tag_matches(measure.commodities, term) for term in terms):
            score += 2.0
    else:
        score += 0.25  # applies to any commodity

    if question_tokens:
        text = _tokens(f"{measure.heading} {measure.measure}")
        # Heading words count double: they say what the clause is actually about.
        heading_hits = len(question_tokens & _tokens(measure.heading))
        overlap = len(question_tokens & text)
        score += min(overlap, 6) * 0.6 + min(heading_hits, 3) * 0.8

    if stages:
        score += 1.2 if measure.stage in stages else -0.4

    if want_temperature and measure.temperature_related:
        score += 1.5

    return score


# Asking "what is the highest value" is a chart question; asking "what do I do
# about it" is a mitigation question. Only the second should pull in guidance -
# it keeps the prompt small and stops citations appearing under answers that are
# purely about the data.
_MITIGATION_HINTS = {
    "do", "avoid", "prevent", "reduce", "control", "manage", "mitigate", "mitigation",
    "advice", "recommend", "recommendation", "recommendations", "guidance", "guidelines",
    "action", "actions", "measure", "measures", "practice", "practices", "steps",
    "protect", "handle", "handling", "store", "storage", "safe", "safety", "hygiene",
    "wash", "washing", "irrigation", "manure", "harvest", "cold", "chain", "fao", "codex",
}


def looks_like_mitigation_question(question):
    """True when the question is asking what to do, rather than what the data says."""
    text = (question or "").lower()
    if not text.strip():
        return False
    # "what should I do", "how do I reduce" and friends survive stopword removal
    # badly, so check the raw phrasing too.
    for phrase in ("what do i", "what should", "how do i", "how can i", "how should",
                   "what can i", "what action", "how to"):
        if phrase in text:
            return True
    return bool(_tokens(text) & _MITIGATION_HINTS)


def measures_for(crop=None, hazard=None, question="", limit=5):
    """Return the best-matching active measures, most relevant first.

    Returns an empty list on any failure: Ambra must still be able to answer from
    the chart if this lookup breaks, and a workshop is no place for a 500.
    """
    try:
        question_tokens = _tokens(question)
        want_temperature = bool(question_tokens & _TEMPERATURE_HINTS)

        stages = _stages_for(question_tokens)
        rows = list(MitigationMeasure.objects.filter(status=1))
        scored = [(m, _score(m, crop, hazard, question_tokens, want_temperature, stages)) for m in rows]
        scored = [(m, s) for m, s in scored if s > 0]
        scored.sort(key=lambda pair: (-pair[1], pair[0].source_code, pair[0].clause))
        return [m for m, _ in scored[:limit]]
    except Exception:  # noqa: BLE001 - retrieval must never break the answer
        logger.warning("Mitigation lookup failed for crop=%s hazard=%s", crop, hazard, exc_info=True)
        return []


def as_prompt_block(measures):
    """Render measures for the model: numbered, each with the citation to use."""
    lines = []
    for i, m in enumerate(measures, start=1):
        lines.append(
            f"[{i}] {m.source_code}, {m.clause} - {m.heading}\n"
            f"    {m.measure}"
        )
    return "\n".join(lines)


def as_sources(measures):
    """Render measures for the UI, so a reader can go to the original."""
    return [
        {
            "citation": f"{m.source_code}, {m.clause}",
            "title": m.source_title,
            "heading": m.heading,
            "url": m.source_url,
            "licence": m.source_licence,
        }
        for m in measures
    ]
