# lumenix/tasks.py

from celery import shared_task
from lumenix.services.vocabulary_sync import sync_vocabulary


@shared_task(bind=True, max_retries=3)
def sync_vocabulary_task(self, vocab_id: str):
    """
    Celery wrapper so Beat can schedule it.
    """
    res = sync_vocabulary(vocab_id)
    return res
