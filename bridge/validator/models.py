from django.db import models
from django.contrib.postgres.fields import ArrayField
import requests
import logging
from django.utils import timezone
from bridge.settings import networks, relayers
from web3 import Web3


class Swap(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created'
        RELAYERS_OFFLINE = 'relayers_offline'
        SIGNATURE_SUBMITTED = 'signature submitted'
        SUCCESS = 'success'

    status = models.CharField(max_length=100, choices=Status.choices, default=Status.CREATED)

    created_at = models.DateTimeField(auto_now_add=True)

    from_tx_hash = models.CharField(max_length=100, unique=True)
    from_network_num = models.IntegerField()
    from_address = models.CharField(max_length=100)

    to_tx_hash = models.CharField(max_length=100)
    to_network_num = models.IntegerField()
    to_address = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=100, decimal_places=0)
    signature = models.TextField()
    signature_submitted_at = models.DateTimeField(null=True, default=None)
    signature_submitted_to = ArrayField(models.CharField(max_length=200), default=list)

    def submit_signature_to_relayer(self):
        relayer_payload = {
            'signature': self.signature,
            'from_network_num': self.from_network_num,
            'from_tx_hash': self.from_tx_hash,
        }

        relayers_list = [relayer for relayer in relayers if relayer not in self.signature_submitted_to]

        for relayer in relayers_list:
            try:
                response = requests.post('http://' + relayer + '/provide_signature/', json=relayer_payload)
                if response.status_code != 200:
                    continue

                self.signature_submitted_to.append(relayer)
                self.status = Swap.Status.SIGNATURE_SUBMITTED
                self.signature_submitted_at = timezone.now()
                self.save()
                print(f'(swap.send_signature_to_relayer): signature submitted to {relayer}')
                break
            except Exception as e:
                logging.info(repr(e))
                pass
        else:
            self.status = Swap.Status.RELAYERS_OFFLINE
            self.save(update_fields=['status'])

    def update_relay_tx_status(self):
        network = networks[self.to_network_num]
        tx_hash_bytes = Web3.toBytes(hexstr=self.from_tx_hash)
        is_processed_tx_func = network.swap_contract.functions.isProcessedTransaction(tx_hash_bytes)
        data = is_processed_tx_func.call(block_identifier='pending')
        if data[0]:
            self.to_tx_hash = data[1].hex()
            self.status = Swap.Status.SUCCESS
            self.save()
            return True

        return False

