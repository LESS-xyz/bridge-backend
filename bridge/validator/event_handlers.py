import requests
from web3 import Web3
from eth_account import Account, messages
from bridge.validator.models import Swap
from bridge.settings import relayers, secret
from bridge.validator.tasks import process_swap
from django.db.utils import IntegrityError


def deposit_event_handler(network, event):
    args = event['args']

    recipient_address = Web3.toChecksumAddress(args.newAddress)
    deposit_tx_hash_bytes = event.transactionHash
    amount = args.amount

    print(network.name)
    print(recipient_address, deposit_tx_hash_bytes, amount)

    keccak_hex = Web3.solidityKeccak(
        ['address', 'uint256', 'bytes32'],
        [recipient_address, amount, deposit_tx_hash_bytes]
    ).hex()

    message_to_sign = messages.encode_defunct(hexstr=keccak_hex)
    signature = Account.sign_message(message_to_sign, private_key=secret)
    print(signature.signature.hex())

    swap = Swap(
        from_tx_hash=deposit_tx_hash_bytes.hex(),
        from_network_num=network.num,
        from_address=args.user,
        to_network_num=args.blockchain,
        to_address=args.newAddress,
        amount=args.amount,
        signature=signature.signature.hex()[2:]
    )

    try:
        swap.save()
    except IntegrityError:
        pass

    process_swap.delay(swap.id)
