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


def is_network_locked(network_num):
    try:
        NetworkLock.objects.select_for_update().get_or_create(network_num=network_num)

        pending_swaps = Swap.objects.filter(
            to_network_num=network_num,
            status__in=(Swap.Status.IN_MEMPOOL, Swap.Status.PENDING)
        )
        return bool(pending_swaps.count())
    except OperationalError:
        return True


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

    def check_if_hash_processed(self):
        from_tx_hash_bytes = Web3.toBytes(hexstr=self.from_tx_hash)
        func = networks[self.to_network_num].swap_contract.functions.isProcessedTransaction(from_tx_hash_bytes)
        is_processed, tx_hash_bytes = func.call(block_identifier='pending')

        if is_processed:
            self.status = Swap.Status.SENT_BY_ANOTHER_RELAYER
            self.to_tx_hash = tx_hash_bytes.hex()
            self.save()

        return is_processed

    def print_log(self, text):
        print(f'{self.from_tx_hash} ({self.pk}): {text}')

    def validate_deposit(self):
        self.print_log('start validation')
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

        self.print_log('validation success')

        return True

    def check_if_signatures_enough(self):
        self.print_log('check if signatures enough')
        signs = Signature.objects.filter(swap=self)

        network = networks[self.to_network_num]
        min_confimations = network.swap_contract.functions.minConfirmationSignatures().call()
        signs_count = signs.count()
        self.print_log(f'{signs_count} / {min_confimations} signatures')

        if signs_count >= min_confimations:
            self.status = Swap.Status.WAITING_FOR_RELAY
            self.save(update_fields=['status'])
            return True

        return False

    def relay(self):
        self.print_log('start relaying')
        if self.status != Swap.Status.WAITING_FOR_RELAY:
            return

        if is_network_locked(self.to_network_num):
            self.print_log('relaying postponed due to locked network')
            return

        if self.check_if_hash_processed():
            self.print_log('processed by another relayer')
            return

        network = networks[self.to_network_num]
        contract_address = network.swap_contract.address
        if network.token_contract.functions.balanceOf(contract_address).call() < self.amount:
            self.print_log('insufficient token balance')
            return

        gas_price = network.w3.eth.gasPrice
        max_gas_price = network.swap_contract.functions.maxGasPrice().call()
        if gas_price > max_gas_price:
            self.print_log(f'high gas price {gas_price} > {max_gas_price}')
            return

        relayer_address = Account.from_key(secret).address

        if network.w3.eth.get_balance(relayer_address) < gas_price * 300_000:
            self.print_log('insufficient balance')
            return

        validator_signs = self.verified_validator_signs()
        min_confirmations = network.swap_contract.functions.minConfirmationSignatures().call()

        if len(validator_signs) < min_confirmations:
            self.print_log('not enough signatures')
            return

        tx_params = {
            'nonce': network.w3.eth.getTransactionCount(relayer_address, 'pending'),
            'gasPrice': gas_price,
            'gas': 300_000,
        }

        combined_signatures = '0x' + ''.join(validator_signs)

        func = network.swap_contract.functions.transferToUserWithFee(
            Web3.toChecksumAddress(self.to_address),
            int(self.amount),
            Web3.toBytes(hexstr=self.from_tx_hash),
            Web3.toBytes(hexstr=combined_signatures)
        )
        initial_tx = func.buildTransaction(tx_params)
        signed_tx = network.w3.eth.account.sign_transaction(initial_tx, secret).rawTransaction
        tx_hash = network.w3.eth.sendRawTransaction(signed_tx).hex()

        self.print_log(f'relay hash {tx_hash}')

        self.to_tx_hash = tx_hash
        self.relayed_to_blockchain_at = timezone.now()
        self.status = Swap.Status.IN_MEMPOOL
        self.save()

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

    def verified_validator_signs(self):
        result = []
        signs = Signature.objects.filter(swap=self)

        network = networks[self.to_network_num]
        for sign in signs:
            keccak_hex = Web3.solidityKeccak(
                ['address', 'uint256', 'bytes32'],
                [Web3.toChecksumAddress(self.to_address), int(self.amount), Web3.toBytes(hexstr=self.from_tx_hash)]
            ).hex()

            message_to_sign = messages.encode_defunct(hexstr=keccak_hex)
            signer = Account.recover_message(message_to_sign, signature=sign.signature)
            signer_checksum = Web3.toChecksumAddress(signer)

            if network.swap_contract.functions.isValidator(signer_checksum).call():
                result.append(sign.signature)
            else:
                self.print_log('invalid validator ' + signer_checksum)

        return result


class Signature(models.Model):
    swap = models.ForeignKey(Swap, on_delete=models.CASCADE)
    signature = models.TextField(unique=True)
