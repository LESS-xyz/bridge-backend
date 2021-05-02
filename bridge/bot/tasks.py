from bot_celery import app
from django.db import transaction
from django.db.utils import OperationalError
from bridge.bot.models import Swap
from celery import shared_task


@app.task
@transaction.atomic
def process_swap(swap_id):
    print('check swap')
    try:
        swap = Swap.objects.select_for_update(nowait=True).get(id=swap_id)
    except OperationalError:
        print('swap model locked')
        return

    if swap.status in (Swap.Status.RELAYED, Swap.Status.DEPOSITED):
        swap.send_message_to_subs()
    if swap.status == Swap.Status.DEPOSIT_MESSAGE_SENT:
        if swap.update_relay_tx_status():
            swap.send_message_to_subs()


@shared_task
def route_swaps():
    for swap in Swap.objects.all():
        process_swap.delay(swap.id)