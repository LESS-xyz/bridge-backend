from bridge.rabbitmq import queue_task
from celery import shared_task
from bridge.relayer.models import Swap, Signature
from bridge.settings import networks
from web3 import Web3
from eth_account import Account


@queue_task
def relay(swap_id):
    swap = Swap.objects.get(id=swap_id)
    signs = Signature.objects.filter(swap=swap)

    combined_singatures = '0x' + ''.join(signs)
    network = networks[swap.to_network_num]

    gas_price = network.w3.eth.gasPrice

    relayer_address = Account.from_key(network.private_key)

    tx_params = {
        'nonce': network.w3.eth.getTransactionCount(relayer_address, 'pending'),
        'gasPrice': gas_price,
        'gas': 300_000,
    }
    func = network.swap_contract.functions.transferToUserWithFee(
        swap.to_address,
        swap.amount,
        Web3.toBytes(hexstr=swap.from_tx_hash),
        Web3.toBytes(hexstr=combined_singatures)
    )
    initial_tx = func.buildTransaction(tx_params)
    signed_tx = network.w3.eth.account.sign_transaction(initial_tx, network.private_key).rawTransaction
    tx_hash = network.w3.eth.sendRawTransaction(signed_tx)
    tx_hex = tx_hash.hex()

    swap.to_tx_hash = tx_hex


@shared_task
def check_swaps():
    swaps = Swap.objects.all()

    for swap in swaps:
        check_swap.delay(args=[swap.id])


@shared_task
def check_swap(swap_id):
    swap = Swap.objects.get(pk=swap_id)

    if swap.status == Swap.Status.WAITING_FOR_SIGNATURES:
        signs = Signature.objects.filter(swap=swap)
        network = networks[swap.to_network_num]
        min_confimations = network.w3.eth.swap_contract.functions.minConfirmations().call()
        if signs.count() >= min_confimations:
            relay.to_queue(kwargs={'swap_id': swap_id})
