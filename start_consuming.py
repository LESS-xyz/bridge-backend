from bridge.rabbitmq import broker
from bridge.settings import networks

for network in networks:
    broker.consume(network.name)
