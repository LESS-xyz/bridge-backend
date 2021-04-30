import requests
from celery import shared_task
from validator_celery import app
from bridge.validator.models import Swap
from django.utils import timezone
from bridge.settings import relayers, CHANGE_RELAYER_TIMEOUT
from django.db import transaction
from django.db.utils import OperationalError


@app.task
@transaction.atomic
def process_swap(swap_id):
    print('check swap')
    try:
        swap = Swap.objects.select_for_update(nowait=True).get(id=swap_id)
    except OperationalError:
        print('swap model locked')
        return

    if swap.status in (Swap.Status.RELAYERS_OFFLINE, Swap.Status.CREATED):
        swap.submit_signature_to_relayer()
    elif swap.status == Swap.Status.SIGNATURE_SUBMITTED:
        is_relayed = swap.update_relay_tx_status()
        seconds_diff = (timezone.now() - swap.signature_submitted_at).seconds
        if not is_relayed and seconds_diff > CHANGE_RELAYER_TIMEOUT:
            swap.submit_signature_to_relayer()


@shared_task
def route_swaps():
    for swap in Swap.objects.all():
        process_swap.delay(swap.id)
