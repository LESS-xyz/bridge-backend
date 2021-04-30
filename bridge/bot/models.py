from django.db import models


class Swap(models.Model):
    class Status(models.TextChoices):
        DEPOSITED = 'deposited'
        DEPOSIT_MESSAGE_SENT = 'deposit message sent'
        RELAYED = 'relayed'
        RELAY_MESSAGE_SENT = 'relay message sent'

    status = models.CharField(max_length=100, choices=Status.choices, default=Status.DEPOSITED)
    created_at = models.DateTimeField(auto_now_add=True)

    from_tx_hash = models.CharField(max_length=100, unique=True)
    from_network_num = models.IntegerField()
    from_address = models.CharField(max_length=100)

    to_tx_hash = models.CharField(max_length=100)
    to_network_num = models.IntegerField()
    to_address = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=100, decimal_places=0)


class BotSub(models.Model):
    chat_id = models.IntegerField(unique=True)


class BotSwapMessage(models.Model):
    swap = models.ForeignKey(Swap, on_delete=models.CASCADE)
    sub = models.ForeignKey(BotSub, on_delete=models.CASCADE)
    message_id = models.IntegerField()
