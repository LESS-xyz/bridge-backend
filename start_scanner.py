import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

from bridge.validator.scanner import Scanner
from bridge.settings import networks
from bridge.validator.utils import event_handler


for network in networks.values():
    Scanner(network, 'TransferToOtherBlockchain', event_handler).start()