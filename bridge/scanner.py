import threading
import traceback
import sys
import os
import time
from bridge.settings import MAX_FILTER_LENGTH


def never_fall(func):
    def wrapper(*args, **kwargs):
        while True:
            try:
                func(*args, **kwargs)
            except Exception as e:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(60)

    return wrapper


class Scanner(threading.Thread):
    def __init__(self, network, event_names, event_handlers):
        super().__init__()
        self.handlers = event_handlers
        self.network = network
        self.events = [getattr(self.network.swap_contract.events, event_name)() for event_name in event_names]

        dir_path = os.path.join(os.path.dirname(__file__), 'block_numbers')

        try:
            os.makedirs(dir_path)
        except FileExistsError:
            pass

        self.block_file_path = os.path.join(dir_path, self.network.name)

    def print_log(self, text):
        print(f'{self.network.name}: {text}')

    @never_fall
    def start_polling(self):
        min_confirmations = self.network.swap_contract.functions.minConfirmationBlocks().call()

        try:
            with open(self.block_file_path) as f:
                last_block_processed = int(f.read())
        except:
            last_block_processed = self.network.w3.eth.block_number - min_confirmations - 1

        while True:
            last_block_confirmed = self.network.w3.eth.block_number - min_confirmations
            if last_block_processed >= last_block_confirmed:
                self.print_log('waiting for blocks...')
                time.sleep(10)
                continue

            if last_block_confirmed - last_block_processed > MAX_FILTER_LENGTH:
                to_block = last_block_processed + MAX_FILTER_LENGTH
            else:
                to_block = last_block_confirmed

            from_block = last_block_processed + 1

            self.print_log(f'scanning [{from_block}, {to_block}] / {last_block_confirmed}')

            for event, handler in zip(self.events, self.handlers):
                event_filter = event.createFilter(fromBlock=from_block, toBlock=to_block)
                events = event_filter.get_all_entries()
                for event_data in events:
                    self.print_log(f'event received {event_data}')
                    handler(self.network, event_data)

            last_block_processed = to_block

            with open(self.block_file_path, 'w') as f:
                f.write(str(last_block_processed))

            time.sleep(30)

    def run(self):
        self.start_polling()
