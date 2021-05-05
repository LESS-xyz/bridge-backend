from celery import shared_task
from relayer_celery import app
from bridge.relayer.models import Swap
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone
from bridge.settings import MEMPOOL_TIMEOUT


@app.task
@transaction.atomic
def process_swap(swap_id):
    try:
        swap = Swap.objects.select_for_update(nowait=True).get(id=swap_id)
    except OperationalError:
        return

    if swap.status == Swap.Status.WAITING_FOR_VALIDATION:
        swap.validate_deposit()
    elif swap.status == Swap.Status.WAITING_FOR_SIGNATURES:
        if swap.check_if_signatures_enough():
            swap.relay()
    elif swap.status == Swap.Status.WAITING_FOR_RELAY and not swap.to_tx_hash:
        swap.relay()
    elif swap.status in (Swap.Status.IN_MEMPOOL, Swap.Status.PENDING):
        swap.check_relayed_tx_status()
    elif swap.status == Swap.Status.IN_MEMPOOL:
        diff_seconds = (timezone.now() - swap.relayed_to_blockchain_at).seconds
        if diff_seconds > MEMPOOL_TIMEOUT:
            swap.status = Swap.Status.WAITING_FOR_RELAY
            swap.to_tx_hash = ''
            swap.save()
            swap.relay()


@shared_task
def route_swaps():
    for swap in Swap.objects.all():
        process_swap.delay(swap.id)
