import requests
from web3 import Web3
from eth_account import Account, messages
from bridge.validator.models import Swap
from bridge.settings import relayers, secret
from datetime import datetime


def deposit_event_handler(network, event):
    args = event['args']

    recipient_address = args.newAddress
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
    swap.save()

    relayer_payload = {
        'signature': swap.signature,
        'from_network_num': swap.from_network_num,
        'from_tx_hash': swap.from_tx_hash,
    }

    for relayer in relayers:
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

    #address = Account.recover_message(message_to_sign, signature=signature.signature.hex())
