import threading
import traceback
import sys
import os
import time
from os import path
from web3 import Web3
from eth_account import Account, messages

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

from bridge.settings import networks, MAX_FILTER_LENGTH
from bridge.validator.models import Swap
from bridge.validator.utils import event_handler


class Scanner(threading.Thread):
    def __init__(self, network, event_name, handler):
        super().__init__()
        self.handler = handler
        self.network = network
        self.event = getattr(self.network.swap_contract.events, event_name)()

    def run(self):
        try:
            filename = os.path.dirname(__file__) + '/block_numbers/' + self.network.name

            if not os.path.exists(os.path.dirname(__file__) + '/block_numbers/'):
                os.makedirs(os.path.dirname(__file__) + '/block_numbers/')

            try:
                with open(filename) as f:
                    last_block_processed = int(f.read())
            except Exception:
                last_block_processed = self.network.w3.eth.block_number
            # if path.isfile(filename):

            current_block = self.network.w3.eth.block_number

            while True:
                if current_block - last_block_processed > MAX_FILTER_LENGTH:
                    to_block = last_block_processed + MAX_FILTER_LENGTH
                else:
                    to_block = current_block

                event_filter = self.event.createFilter(fromBlock=last_block_processed, toBlock=to_block)
                print(self.network.name + ': scanning...')
                events = event_filter.get_all_entries()
                for event in events:
                    self.handler(self.network, event)
                last_block_processed = to_block

                with open(filename, 'w') as f:
                    f.write(str(last_block_processed))

                time.sleep(10)

        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
