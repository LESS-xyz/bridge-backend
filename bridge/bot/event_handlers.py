from bridge.bot.models import Swap
from web3 import Web3
from bridge.bot.tasks import process_swap


def deposit_event_handler(network, event):
    args = event['args']

    recipient_address = Web3.toChecksumAddress(args.newAddress)
    deposit_tx_hash_bytes = event.transactionHash
    amount = args.amount

    print(network.name)
    print(recipient_address, deposit_tx_hash_bytes, amount)

    swap = Swap(
        from_tx_hash=deposit_tx_hash_bytes.hex(),
        from_network_num=network.num,
        from_address=args.user,
        to_network_num=args.blockchain,
        to_address=args.newAddress,
        amount=args.amount,
    )
    swap.save()

    process_swap.delay(swap.id)
