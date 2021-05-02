import logging
from django.db import models
from bridge.settings import networks, secret
from web3 import Web3
from eth_account import Account, messages
from web3.exceptions import TransactionNotFound
from django.utils import timezone
from django.db.utils import OperationalError


class NetworkLock(models.Model):
    network_num = models.IntegerField()


class Swap(models.Model):
    class Status(models.TextChoices):
        WAITING_FOR_VALIDATION = 'waiting for validation'
        INVALID_TX_HASH = 'invalid tx hash'
        SENT_BY_ANOTHER_RELAYER = 'sent by another relayer'
        WAITING_FOR_SIGNATURES = 'waiting for signatures'
        WAITING_FOR_RELAY = 'waiting for relay'
        IN_MEMPOOL = 'in mempool'
        PENDING = 'pending'
        SUCCESS = 'success'
        REVERT = 'revert'
        FAIL = 'fail'

    status = models.CharField(max_length=100, choices=Status.choices, default=Status.WAITING_FOR_VALIDATION)

    created_at = models.DateTimeField(auto_now_add=True)

    from_tx_hash = models.CharField(max_length=100, unique=True)
    from_network_num = models.IntegerField()
    from_address = models.CharField(max_length=100, default='')

    to_tx_hash = models.CharField(max_length=100, default='')
    to_network_num = models.IntegerField(null=True, default=None)
    to_address = models.CharField(max_length=100, default='')

    amount = models.DecimalField(max_digits=100, decimal_places=0, null=True, default=None)
    relayed_to_blockchain_at = models.DateTimeField(null=True, default=None)

    def validate_deposit(self):
        from_network = networks[self.from_network_num]

        try:
            receipt = from_network.w3.eth.getTransactionReceipt(self.from_tx_hash)
        except TransactionNotFound:
            self.status = Swap.Status.INVALID_TX_HASH
            self.save(update_fields=['status'])
            return False

        event_data = from_network.swap_contract.events.TransferToOtherBlockchain().processReceipt(receipt)

        if not event_data:
            self.status = Swap.Status.INVALID_TX_HASH
            self.save(update_fields=['status'])
            return False

        event_args = event_data[0].args

        self.from_address = event_args.user
        self.to_address = event_args.newAddress
        self.to_network_num = event_args.blockchain
        self.amount = event_args.amount
        self.status = Swap.Status.WAITING_FOR_SIGNATURES
        self.save()

        return True

    def check_if_signatures_enough(self):
        signs = Signature.objects.filter(swap=self)

        network = networks[self.to_network_num]
        min_confimations = network.swap_contract.functions.minConfirmationSignatures().call()
        signs_count = signs.count()
        print(f'(swap.check_if_signatures_enough): {signs_count} / {min_confimations} ')

        if signs_count >= min_confimations:
            self.status = Swap.Status.WAITING_FOR_RELAY
            self.save(update_fields=['status'])
            return True

        return False

    def relay(self):
        if self.status != Swap.Status.WAITING_FOR_RELAY:
            print('(swap.relay) invalid status')
            return False
        try:
            lock = NetworkLock.objects.select_for_update(nowait=True).get_or_create(network_num=self.to_network_num)
        except OperationalError:
            print('(swap.relay) network locked')
            return False

        pending_swaps = Swap.objects.filter(
            to_network_num=self.to_network_num,
            status__in=(Swap.Status.IN_MEMPOOL, Swap.Status.PENDING)
        )

        if pending_swaps.count():
            print('(swap.relay) network locked')
            return False

        network = networks[self.to_network_num]
        from_tx_hash_bytes = Web3.toBytes(hexstr=self.from_tx_hash)
        is_processed_tx_func = network.swap_contract.functions.isProcessedTransaction(from_tx_hash_bytes)
        is_processed_tx_data = is_processed_tx_func.call(block_identifier='pending')

        if is_processed_tx_data[0]:
            self.status = Swap.Status.SENT_BY_ANOTHER_RELAYER
            self.to_tx_hash = is_processed_tx_data[1].hex()
            self.save()
            print('(swap.relay) sent by another relayer')
            return False

        signs = Signature.objects.filter(swap=self)
        amount = int(self.amount)

        to_address_checksum = Web3.toChecksumAddress(self.to_address)

        validator_signs = []
        for sign in signs:
            keccak_hex = Web3.solidityKeccak(
                ['address', 'uint256', 'bytes32'],
                [to_address_checksum, amount, from_tx_hash_bytes]
            ).hex()

            message_to_sign = messages.encode_defunct(hexstr=keccak_hex)

            signer = Account.recover_message(message_to_sign, signature=sign.signature)
            signer_checksum = Web3.toChecksumAddress(signer)

            if network.swap_contract.functions.isValidator(signer_checksum).call():
                validator_signs.append(sign.signature)
            else:
                print(f'(swap.relay) invalid validator {signer_checksum}')

        min_confirmations =  network.swap_contract.functions.minConfirmationSignatures().call()

        if len(validator_signs) < min_confirmations:
            print(f'(swap.relay) not enough signatures')
            return False

        gas_price = network.w3.eth.gasPrice
        max_gas_price = network.swap_contract.functions.maxGasPrice().call()
        if gas_price > max_gas_price:
            print(f'(swap.relay) high gas price: {gas_price} > {max_gas_price}')
            return

        relayer_address = Account.from_key(secret).address

        tx_params = {
            'nonce': network.w3.eth.getTransactionCount(relayer_address, 'pending'),
            'gasPrice': gas_price,
            'gas': 300_000,
        }

        combined_signatures = '0x' + ''.join(validator_signs)

        func = network.swap_contract.functions.transferToUserWithFee(
            to_address_checksum,
            amount,
            from_tx_hash_bytes,
            Web3.toBytes(hexstr=combined_signatures)
        )
        initial_tx = func.buildTransaction(tx_params)
        signed_tx = network.w3.eth.account.sign_transaction(initial_tx, secret).rawTransaction
        tx_hash = network.w3.eth.sendRawTransaction(signed_tx).hex()

        print(f'(swap.relay) tx hash: {tx_hash}')

        self.to_tx_hash = tx_hash
        self.relayed_to_blockchain_at = timezone.now()
        self.status = Swap.Status.IN_MEMPOOL
        self.save()

        return True

    def check_relayed_tx_status(self):
        if self.status not in (Swap.Status.IN_MEMPOOL, Swap.Status.PENDING) or not self.to_tx_hash:
            return

        try:
            receipt = networks[self.to_network_num].w3.eth.getTransactionReceipt(self.to_tx_hash)
        except TransactionNotFound:
            self.status = Swap.Status.IN_MEMPOOL
            self.save(update_fields=['status'])
            return

        try:
            if receipt['status'] == 1:
                self.status = Swap.Status.SUCCESS
            elif receipt['blockNumber'] is None:
                self.status = Swap.Status.PENDING
            else:
                self.status = Swap.Status.REVERT
        except KeyError:
            self.status = Swap.Status.IN_MEMPOOL
        self.save(update_fields=['status'])


class Signature(models.Model):
    swap = models.ForeignKey(Swap, on_delete=models.CASCADE)
    signature = models.TextField(unique=True)
