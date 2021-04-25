from bridge.rabbitmq import broker
from bridge.settings import networks

for network in networks.values():
    broker.consume(network.name)
