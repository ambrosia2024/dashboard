# lumenix/tasks.py

from celery import shared_task

from lumenix.models import ToxinQuerySpec
from lumenix.services.toxin_query import sync_toxin_query_spec
from lumenix.services.vocabulary_sync import sync_vocabulary


@shared_task(bind=True, max_retries=3)
def sync_vocabulary_task(self, vocab_id: str):
    """
    Celery wrapper so Beat can schedule it.
    """
    res = sync_vocabulary(vocab_id)
    return res


@shared_task(bind=True, max_retries=3)
def sync_toxin_query_spec_task(self, spec_id: int):
    spec = ToxinQuerySpec.active_objects.get(pk=spec_id)
    return sync_toxin_query_spec(spec)
