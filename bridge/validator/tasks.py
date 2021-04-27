import requests
from celery import shared_task
from validator_celery import app
from bridge.validator.models import Swap
from datetime import datetime
from bridge.settings import relayers, networks, CHANGE_RELAYER_TIMEOUT
from django.db import transaction
from django.db.utils import OperationalError
from web3 import Web3


def send_sign_to_relayer(swap, relayer_list):
    relayer_payload = {
        'signature': swap.signature,
        'from_network_num': swap.from_network_num,
        'from_tx_hash': swap.from_tx_hash,
    }

    for relayer in relayer_list:
        try:
            response = requests.post('http://' + relayer + '/provide_signature/', json=relayer_payload)
            print(response.status_code)
            if response.status_code != 200:
                continue
            swap.relayer_ip = relayer
            swap.status = Swap.Status.SIGNATURE_SUBMITTED
            swap.signature_submitted_at = datetime.now()
            swap.save()
            break
        except Exception as e:
            print('exceptions')
            print(repr(e))
            pass
    else:
        swap.status = Swap.Status.RELAYERS_OFFLINE
        swap.save(update_fields=['status'])


@app.task
@transaction.atomic
def check_swap(swap_id):
    print('check swap')
    try:
        swap = Swap.objects.select_for_update(nowait=True).get(id=swap_id)
    except OperationalError:
        print('swap model locked')
        return

    if swap.status in (Swap.Status.RELAYERS_OFFLINE, Swap.Status.CREATED):
        send_sign_to_relayer(swap, relayers)
    '''
    elif swap.status == Swap.Status.SIGNATURE_SUBMITTED:
        
        if (datetime.now() - swap.signature_submitted_at).seconds > CHANGE_RELAYER_TIMEOUT:
            relayer_list = relayers.pop(swap.relayer_url)
            send_sign_to_relayer(swap, relayer_list)
    '''

def check_sended_swap_status(swap):
    network = networks[swap.to_network_num]
    tx_hash_bytes = Web3.toBytes(hexstr=swap.from_tx_hash)
    is_processed = network.swap_contract.functions.isProcessedTransaction(tx_hash_bytes).call()
    if (datetime.now() - swap.signature_submitted_at).seconds > CHANGE_RELAYER_TIMEOUT and not is_processed:
        relayer_list = relayers.pop(swap.relayer_url)
        send_sign_to_relayer(swap, relayer_list)


@shared_task
def check_swaps():
    print('check swaps')
    swaps = Swap.objects.all()

    for swap in swaps:
        check_swap.delay(swap.id)
