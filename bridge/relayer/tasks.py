from celery import shared_task
from relayer_celery import app
from bridge.relayer.models import Swap, Signature, NetworkLock
from bridge.settings import networks, secret
from web3 import Web3
from eth_account import Account, messages
from web3.exceptions import TransactionNotFound
from datetime import datetime
from django.db import transaction
from django.db.utils import OperationalError


def validate_swap(swap):
    print('validate_swap')
    from_network = networks[swap.from_network_num]

    try:
        receipt = from_network.w3.eth.getTransactionReceipt(swap.from_tx_hash)
    except TransactionNotFound:
        swap.status = Swap.Status.INVALID_TX_HASH
        swap.save(update_fields=['status'])
        return

    event_data = from_network.swap_contract.events.TransferToOtherBlockchain().processReceipt(receipt)

    if not event_data:
        swap.status = Swap.Status.INVALID_TX_HASH
        swap.save(update_fields=['status'])
        return

    event_args = event_data[0].args

    swap.from_address = event_args.user
    swap.to_address = event_args.newAddress
    swap.to_network_num = event_args.blockchain
    swap.amount = event_args.amount
    swap.status = Swap.Status.WAITING_FOR_SIGNATURES
    swap.save()

    check_swap.delay(swap.id)


def check_sign_count(swap):
    print('check sign count')
    signs = Signature.objects.filter(swap=swap)

    network = networks[swap.to_network_num]

    if signs.count() >= network.swap_contract.functions.minConfirmationSignatures().call():
        swap.status = Swap.Status.WAITING_FOR_RELAY
        swap.save(update_fields=['status'])
        check_swap.delay(swap.id)


@transaction.atomic
def relay(swap):
    try:
        lock = NetworkLock.objects.select_for_update(nowait=True).get(network_num=swap.to_network_num)
    except OperationalError:
        print('network locked')
        return

    print('relay message recieved:', swap.__dict__)

    if swap.status != Swap.Status.WAITING_FOR_RELAY:
        print('invalid status')
        return

    pending_swaps = Swap.objects.filter(
        to_network_num=swap.to_network_num,
        status__in=(Swap.Status.IN_MEMPOOL, Swap.Status.PENDING)
    )

    if pending_swaps.count():
        print('queue locked')
        return

    signs = Signature.objects.filter(swap=swap)

    network = networks[swap.to_network_num]
    amount = int(swap.amount)

    validator_signs = []
    for sign in signs:
        keccak_hex = Web3.solidityKeccak(
            ['address', 'uint256', 'bytes32'],
            [Web3.toChecksumAddress(swap.to_address), amount, Web3.toBytes(hexstr=swap.from_tx_hash)]
        ).hex()

        message_to_sign = messages.encode_defunct(hexstr=keccak_hex)

        signer = Account.recover_message(message_to_sign, signature=sign.signature)
        signer_checksum = Web3.toChecksumAddress(signer)

        if network.swap_contract.functions.isValidator(signer_checksum).call():
            validator_signs.append(sign.signature)

    if len(validator_signs) < network.swap_contract.functions.minConfirmationSignatures().call():
        return

    combined_singatures = '0x' + ''.join(validator_signs)

    gas_price = network.w3.eth.gasPrice
    max_gas_price = network.swap_contract.functions.maxGasPrice().call()
    if gas_price > max_gas_price:
        return

    relayer_address = Account.from_key(secret).address

    tx_params = {
        'nonce': network.w3.eth.getTransactionCount(relayer_address, 'pending'),
        'gasPrice': gas_price,
        'gas': 300_000,
    }

    func = network.swap_contract.functions.transferToUserWithFee(
        swap.to_address,
        amount,
        Web3.toBytes(hexstr=swap.from_tx_hash),
        Web3.toBytes(hexstr=combined_singatures)
    )
    initial_tx = func.buildTransaction(tx_params)
    signed_tx = network.w3.eth.account.sign_transaction(initial_tx, secret).rawTransaction
    tx_hash = network.w3.eth.sendRawTransaction(signed_tx)
    tx_hex = tx_hash.hex()

    swap.to_tx_hash = tx_hex
    swap.relayed_to_blockchain_at = datetime.now()
    swap.status = Swap.Status.IN_MEMPOOL
    swap.save()


def check_swap_status_in_blockchain(swap):
    print('check swap status in blockchin')

    if swap.status not in (Swap.Status.IN_MEMPOOL, Swap.Status.PENDING):
        return

    network = networks[swap.to_network_num]

    try:
        receipt = network.w3.eth.getTransactionReceipt(swap.to_tx_hash)
    except TransactionNotFound:
        return

    try:
        if receipt['status'] == 1:
            swap.status = Swap.Status.SUCCESS
        elif receipt['blockNumber'] is None:
            swap.status = Swap.Status.PENDING
        else:
            swap.status = Swap.Status.REVERT
    except KeyError:
        swap.status = Swap.Status.IN_MEMPOOL

    swap.save()


@app.task
@transaction.atomic
def check_swap(swap_id):
    print('check swap')
    try:
        swap = Swap.objects.select_for_update(nowait=True).get(id=swap_id)
    except OperationalError:
        print('swap model locked')
        return

    if swap.status == Swap.Status.WAITING_FOR_VALIDATION:
        validate_swap(swap)
    elif swap.status == Swap.Status.WAITING_FOR_SIGNATURES:
        check_sign_count(swap)
    elif swap.status == Swap.Status.WAITING_FOR_RELAY:
        relay(swap)
    elif swap.status in (Swap.Status.IN_MEMPOOL, Swap.Status.PENDING):
        check_swap_status_in_blockchain(swap)


@shared_task
def check_swaps():
    print('check swaps')
    swaps = Swap.objects.all()

    for swap in swaps:
        check_swap.delay(swap.id)