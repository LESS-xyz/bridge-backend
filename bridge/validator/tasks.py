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

    if swap.status == Swap.Status.CREATED:
        remaining_relayers = get_remaining_relayers(swap)
        swap.submit_signature_to_relayer(remaining_relayers)
    elif swap.status == Swap.Status.SIGNATURE_SUBMITTED:
        seconds_diff = (timezone.now() - swap.signature_submitted_at).seconds
        if seconds_diff > CHANGE_RELAYER_TIMEOUT:
            remaining_relayers = get_remaining_relayers(swap)
            if remaining_relayers and swap.update_relay_tx_status():
                swap.submit_signature_to_relayer(remaining_relayers)


def get_remaining_relayers(swap):
    result = []
    for relayer in relayers:
        if relayer not in swap.signature_submitted_to:
            response = requests.get('http://' + relayer + '/is_online/')
            if response.status_code == 200:
                result += relayer

    return result


@shared_task
def route_swaps():
    for swap in Swap.objects.all():
        process_swap.delay(swap.id)
