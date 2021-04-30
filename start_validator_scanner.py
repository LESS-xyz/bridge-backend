import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

from bridge.scanner import Scanner
from bridge.settings import networks
from bridge.validator.event_handlers import deposit_event_handler


for network in networks.values():
    Scanner(network, ['TransferToOtherBlockchain'], [deposit_event_handler]).start()
