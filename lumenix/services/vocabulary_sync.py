# lumenix/services/vocabulary_sync.py

import hashlib
import json

import requests

from django.conf import settings
from django.db import transaction

from lumenix.models import Vocabulary, Scheme, Concept, ConceptHistory

BASE = settings.SCIO_VOCAB_API_BASE.rstrip("/")


def _hash_payload(obj: dict) -> str:
    """
    Stable SHA256 over the subset of fields we persist.
    Ensures ordering is deterministic for lists/dicts.
    """
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

def _flatten_concept_payload(vocab_id: str, scheme_map: dict, raw: dict) -> dict:
    """
    Map raw API concept to our Concept model dict.
    """
    # choose first scheme if multiple; API usually sends one in inScheme
    scheme_uri = (raw.get("inScheme") or [None])[0]
    scheme = scheme_map.get(scheme_uri)

    doc = {
        "pref_label": raw.get("prefLabel") or {},
        "alt_label":  raw.get("altLabel")  or {},
        "definition": raw.get("definition") or {},
        "notation":   raw.get("notation") or {},
        "broader":     raw.get("broader") or [],
        "narrower":    raw.get("narrower") or [],
        "exact_match": raw.get("exactMatch") or [],
        "close_match": raw.get("closeMatch") or [],
        "related":     raw.get("related") or [],
        "in_scheme":   raw.get("inScheme") or [],
    }

    ambrosia_supported = bool(raw.get("ambrosia-supported", False))

    doc["content_hash"] = _hash_payload(doc)
    return {
        "vocabulary_id": vocab_id,
        "scheme": scheme,
        "fields": doc,
        "ambrosia_supported": ambrosia_supported,
    }

def fetch_vocabulary(vocab_id: str) -> dict:
    r = requests.get(f"{BASE}/{vocab_id}", headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

@transaction.atomic
def sync_vocabulary(vocab_id: str, reset: bool = False) -> dict:
    """
    Upsert schemes and concepts for a given vocabulary ('plants' or 'pathogens').
    Creates ConceptHistory rows only for created/updated items.
    Returns simple counts.
    """
    data = fetch_vocabulary(vocab_id)

    # Ensure Vocabulary row exists
    vocab, _ = Vocabulary.objects.get_or_create(id=vocab_id)

    if reset:
        # delete concepts and their history for this vocab
        ConceptHistory.objects.filter(concept__vocabulary_id=vocab_id).delete()
        Concept.objects.filter(vocabulary_id=vocab_id).delete()
        Scheme.objects.filter(vocabulary_id=vocab_id).delete()

    # 1) Upsert schemes and pre-build scheme map
    scheme_map = {}
    for s in data.get("schemes", []):
        sch, _ = Scheme.objects.update_or_create(
            uri=s["id"],
            defaults={
                "vocabulary": vocab,
                "title": s.get("title") or {},
                "description": s.get("description") or {},
            },
        )
        scheme_map[sch.uri] = sch

    created, updated, unchanged = 0, 0, 0

    # 2) Upsert concepts
    for s in data.get("schemes", []):
        for c in s.get("concepts", []):
            uri = c["id"]
            mapped = _flatten_concept_payload(vocab_id, scheme_map, c)
            fields = mapped["fields"]
            scheme = mapped["scheme"]
            ambrosia_supported = mapped["ambrosia_supported"]

            obj, existed = Concept.objects.select_for_update().get_or_create(
                uri=uri,
                defaults={
                    "vocabulary": vocab,
                    "scheme": scheme,
                    **fields,
                    "ambrosia_supported": ambrosia_supported,
                },
            )
            if not existed:
                if obj.content_hash != fields["content_hash"] or obj.ambrosia_supported != ambrosia_supported:
                    # Update only when something changed
                    for k, v in fields.items():
                        setattr(obj, k, v)
                    obj.scheme = scheme
                    obj.vocabulary = vocab
                    obj.ambrosia_supported = ambrosia_supported
                    obj.save(update_fields=[*fields.keys(), "scheme", "vocabulary", "ambrosia_supported", "updated_at"])
                    ConceptHistory.objects.create(
                        concept=obj,
                        change_type="updated",
                        content_hash=obj.content_hash,
                        snapshot={
                            "uri": obj.uri,
                            "vocabulary": obj.vocabulary_id,
                            "scheme": obj.scheme.uri if obj.scheme else None,
                            **fields,
                        },
                    )
                    updated += 1
                else:
                    unchanged += 1
            else:
                ConceptHistory.objects.create(
                    concept=obj,
                    change_type="created",
                    content_hash=obj.content_hash,
                    snapshot={
                        "uri": obj.uri,
                        "vocabulary": obj.vocabulary_id,
                        "scheme": obj.scheme.uri if obj.scheme else None,
                        **fields,
                    },
                )
                created += 1

    return {"created": created, "updated": updated, "unchanged": unchanged}
