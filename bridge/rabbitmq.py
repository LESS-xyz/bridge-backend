import pika
import os
import json
import traceback
import sys
import threading
from importlib import import_module


def queue_task(func):
    def to_queue(queue, **kwargs):
        print(json.dumps(kwargs))
        broker.publish(queue, func.__name__, kwargs)

    setattr(func, 'to_queue', to_queue)
    return func


class Broker:
    def __init__(self, include=None):
        self.include = include
        if not include:
            self.include = []

    def _connection(self):
        return pika.BlockingConnection(pika.ConnectionParameters(
            'rabbitmq',
            5672,
            os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
            pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                                  os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
            heartbeat=7200,
            blocked_connection_timeout=7200,
        ))

    def publish(self, queue, type, message):
        connection = self._connection()
        connection.channel().basic_publish(
            exchange='',
            routing_key=queue,
            body=message,
            properties=pika.BasicProperties(type=type),
        )
        connection.close()

    def _declare_queue(self, channel, name):
        channel.queue_declare(
            queue=name,
            durable=True,
            auto_delete=False,
            exclusive=False
        )

    def _callback(self, ch, method, properties, body):
        print(body.decode())
        message = json.loads(body.decode())
        print(type(message))
        try:
            for module_name in self.include:
                try:
                    module = import_module(module_name)
                    func = getattr(module, properties.type)
                except Exception:
                    continue

                func(**message)
        except Exception:
            print('\n'.join(traceback.format_exception(*sys.exc_info())),
                  flush=True)
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def consume(self, queue):
        channel = self._connection().channel()
        self._declare_queue(channel, queue)
        channel.basic_consume(
            queue=queue,
            on_message_callback=self._callback
        )
        print(f'{queue}: queue was started', flush=True)
        threading.Thread(target=channel.start_consuming).start()


broker = Broker(include=['bridge.relayer.tasks, bridge.validator.tasks'])