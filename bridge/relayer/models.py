from django.db import models


class Swap(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created'
        CANNOT_GET_DEPOSIT_PARAMS = 'waiting for getting swap params'
        WAITING_FOR_SIGNATURES = 'waiting for signatures'
        UNREACHABLE_PROVIDER = 'provider offline'
        IN_MEMPOOL = 'mempool'
        PENDING = 'pending'
        SUCCESS = 'success'
        FAIL = 'fail'

    status = models.CharField(max_length=100, choices=Status.choices, default=Status.CREATED)

    created_at = models.DateTimeField(auto_now_add=True)

    from_tx_hash = models.CharField(max_length=100) #, unique=True)
    from_network_num = models.IntegerField()
    from_address = models.CharField(max_length=100, default='')

    to_tx_hash = models.CharField(max_length=100, default='')
    to_network_num = models.IntegerField(null=True, default=None)
    to_address = models.CharField(max_length=100, default='')

    amount = models.DecimalField(max_digits=100, decimal_places=0, null=True, default=None)
    relayed_to_blockchain_at = models.DateTimeField(null=True, default=None)


class Signature(models.Model):
    swap = models.ForeignKey(Swap, on_delete=models.CASCADE)
    signature = models.TextField(unique=True)
