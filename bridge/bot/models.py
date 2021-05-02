from django.db import models
from telebot import TeleBot
from bridge.settings import bot_token
from django.db import transaction
from bridge.settings import networks
from web3 import Web3


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

    def send_message_to_subs(self):
        subs = BotSub.objects.all()
        bot = TeleBot(bot_token)
        network = networks[self.from_network_num]
        amount = self.amount / (10 ** network.token_decimals)

        if self.status in (Swap.Status.RELAYED, Swap.Status.RELAY_MESSAGE_SENT):
            message = f'successfully swapped {amount} {network.token_symbol}'
        else:
            message = f'received {amount} {network.token_symbol}'

        for sub in subs:
            try:
                message_id = BotSwapMessage.objects.get(swap=self, sub=sub).message_id
                bot.edit_message_text(message, sub.chat_id, message_id)
            except BotSwapMessage.DoesNotExist:
                msg_id = bot.send_message(sub.chat_id, message).message_id
                BotSwapMessage(swap=self, sub=sub, message_id=msg_id).save()
            except Exception:
                pass
        else:
            if self.status == Swap.Status.DEPOSITED:
                self.status = Swap.Status.DEPOSIT_MESSAGE_SENT
            elif self.status == Swap.Status.RELAYED:
                self.status = Swap.Status.RELAY_MESSAGE_SENT

            self.save()

    def update_relay_tx_status(self):
        network = networks[self.to_network_num]
        tx_hash_bytes = Web3.toBytes(hexstr=self.from_tx_hash)
        is_processed_tx_func = network.swap_contract.functions.isProcessedTransaction(tx_hash_bytes)
        data = is_processed_tx_func.call()
        if data[0]:
            self.to_tx_hash = data[1].hex()
            self.save()
            self.status = Swap.Status.RELAYED
            return True

        return False


class BotSub(models.Model):
    chat_id = models.IntegerField(unique=True)


class BotSwapMessage(models.Model):
    swap = models.ForeignKey(Swap, on_delete=models.CASCADE)
    sub = models.ForeignKey(BotSub, on_delete=models.CASCADE)
    message_id = models.IntegerField()
