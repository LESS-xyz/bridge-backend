import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

from bridge.rabbitmq import broker
from bridge.settings import networks

for network in networks.values():
    broker.consume(network.name)
