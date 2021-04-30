import threading
import traceback
import sys
import os
import time
from bridge.settings import MAX_FILTER_LENGTH


class Scanner(threading.Thread):
    def __init__(self, network, event_names, event_handlers):
        super().__init__()
        self.handlers = event_handlers
        self.network = network
        self.events = [getattr(self.network.swap_contract.events, event_name)() for event_name in event_names]

    def run(self):
        while True:
            try:
                dir_path = os.path.join(os.path.dirname(__file__), 'block_numbers')

                try:
                    os.makedirs(dir_path)
                except FileExistsError:
                    pass

                block_file_path = os.path.join(dir_path, self.network.name)

                try:
                    with open(block_file_path) as f:
                        last_block_processed = int(f.read())
                except Exception:
                    last_block_processed = self.network.w3.eth.block_number - 1

                min_confirmations = self.network.swap_contract.functions.minConfirmationBlocks().call()

                while True:
                    current_block = self.network.w3.eth.block_number - min_confirmations
                    if last_block_processed >= current_block:
                        print(self.network.name + ': waiting for blocks...')
                        time.sleep(10)
                        continue

                    if current_block - last_block_processed > MAX_FILTER_LENGTH:
                        to_block = last_block_processed + MAX_FILTER_LENGTH
                    else:
                        to_block = current_block

                    print(self.network.name + ': scanning...')

                    for event, handler in zip(self.events, self.handlers):
                        event_filter = event.createFilter(fromBlock=last_block_processed + 1, toBlock=to_block)
                        events = event_filter.get_all_entries()
                        for event_data in events:
                            handler(self.network, event_data)

                        time.sleep(1)

                    last_block_processed = to_block

                    with open(block_file_path, 'w') as f:
                        f.write(str(last_block_processed))

                    time.sleep(10)

            except Exception as e:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(30)
