from celery import shared_task
from bridge.validator.models import Swap
from datetime import datetime
from bridge.settings import relayers


CHANGE_RELAYER_TIMEOUT = 5 * 60


@shared_task
def check_swaps():
    swaps = Swap.objects.all()
    for swap in swaps:
        if (datetime.now() - swap.signature_submitted_at).seconds > CHANGE_RELAYER_TIMEOUT:
            relayer_ip = swap.relayer_url
            relayer_index = relayers.index(relayer_ip)
