import time
import telebot
import threading
import traceback
import sys


from bridge.bot.models import BotSub
from django.db import IntegrityError

from bridge.settings import networks
from web3 import Web3


class Bot(threading.Thread):
    def __init__(self, token):
        super().__init__()
        self.bot = telebot.TeleBot(token)

        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            try:
                BotSub(chat_id=message.chat.id).save()
                self.bot.reply_to(message, 'Hello!')
            except IntegrityError:
                pass

        @self.bot.message_handler(commands=['stop'])
        def stop_handler(message):
            try:
                BotSub.objects.get(chat_id=message.chat.id).delete()
                self.bot.reply_to(message, 'Bye!')
            except BotSub.DoesNotExist:
                pass

        @self.bot.message_handler(commands=['relayer_balances'])
        def balances_handler(message):
            response = ''
            for network in networks.values():
                response += network.name + ':' + '\n'
                relayer_role = network.swap_contract.functions.RELAYER_ROLE().call()
                relayers_count = network.swap_contract.functions.getRoleMemberCount(relayer_role).call()
                for i in range(relayers_count):
                    relayer = network.swap_contract.functions.getRoleMember(relayer_role, i).call()
                    relayer_checksum = Web3.toChecksumAddress(relayer)
                    balance = network.w3.eth.get_balance(relayer_checksum) / (10 ** network.decimals)
                    response += f'{relayer_checksum}: {balance} {network.symbol}\n'
                response += '\n'

            self.bot.reply_to(message, response)

        @self.bot.message_handler(commands=['token_balances'])
        def token_balances_handler(message):
            response = ''
            for network in networks.values():
                balance = network.token_contract.functions.balanceOf(network.swap_contract.address).call()
                response += f'{network.name}: {balance / (10 ** network.token_decimals)}\n'

            self.bot.reply_to(message, response)

        @self.bot.message_handler(commands=['ping'])
        def ping_handler(message):
            self.bot.reply_to(message, 'Pong')

    def run(self):
        while True:
            try:
                self.bot.polling(none_stop=True)
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(15)
