from django.db import models
from bridge.settings import networks, relayers
import requests


class Swap(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created'
        RELAYERS_OFFLINE = 'relayers_offline'
        SIGNATURE_SUBMITTED = 'signature submitted'

    status = models.CharField(max_length=100, choices=Status.choices, default=Status.CREATED)

    created_at = models.DateTimeField(auto_now_add=True)

    from_tx_hash = models.CharField(max_length=100) #, unique=True)
    from_network_num = models.IntegerField()
    from_address = models.CharField(max_length=100)

    to_tx_hash = models.CharField(max_length=100)
    to_network_num = models.IntegerField()
    to_address = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=100, decimal_places=0)
    signature = models.TextField()
    signature_submitted_at = models.DateTimeField(null=True, default=None)
    relayer_ip = models.CharField(max_length=100)
