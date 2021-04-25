from bridge.rabbitmq import queue_task
from celery import shared_task
from bridge.relayer.models import Swap, Signature
from bridge.settings import networks, secret
from web3 import Web3
from eth_account import Account, messages
from web3.exceptions import TransactionNotFound


@shared_task
def validate_swap(swap_id):
    swap = Swap.objects.get(id=swap_id)
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


@shared_task
def check_sign_count(swap_id):
    swap = Swap.objects.get(id=swap_id)
    signs = Signature.objects.filter(swap=swap)

    network = networks[swap.to_network_num]

    if signs.count() >= network.swap_contract.functions.minConfirmations().call():
        swap.status = Swap.Status.WAITING_FOR_RELAY
        swap.save(update_fields=['status'])
        relay.to_queue(queue=network.name, swap_id=swap_id)



@queue_task
def relay(swap_id):
    swap = Swap.objects.get(id=swap_id)
    signs = Signature.objects.filter(swap=swap)

    network = networks[swap.to_network_num]

    validator_signs = []
    for sign in signs:
        keccak_hex = Web3.solidityKeccak(
            ['address', 'uint256', 'bytes32'],
            [swap.to_address, swap.amount, Web3.toBytes(swap.from_tx_hash)]
        ).hex()

        message_to_sign = messages.encode_defunct(hexstr=keccak_hex)

        signer = Account.recover_message(message_to_sign, signature=sign.signature)
        signer_checksum = Web3.toChecksumAddress(signer)


        if network.swap_contract.functinos.isValidator(signer_checksum).call():
            validator_signs.append(sign.signature)


    if not len(validator_signs) >= network.swap_contract.functinos.minConfirmations().call():
        return

    combined_singatures = '0x' + ''.join(signs)

    gas_price = network.w3.eth.gasPrice

    relayer_address = Account.from_key(secret)

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
    swap.save()


@shared_task
def check_swaps():
    swaps = Swap.objects.all()

    for swap in swaps:
        if swap.status == Swap.Status.WAITING_FOR_VALIDATION:
            validate_swap.delay(swap.id)
        elif swap.status == Swap.Status.WAITING_FOR_SIGNATURES:
            check_sign_count.delay(swap.id)
        elif swap.status == Swap.Status.WAITING_FOR_RELAY:
            network = networks[swap.to_network_num]
            relay.to_queue(queue=network.name, swap_id=swap.id)
