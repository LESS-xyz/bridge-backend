import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

app = Celery('relayer_celery', broker='amqp://rabbit:rabbit@rabbitmq:5672/rabbit', include=['bridge.relayer.tasks'])

app.conf.beat_schedule['check_swaps'] = {
    'task': 'bridge.relayer.tasks.route_swaps',
    'schedule': crontab(minute=f'*/1'),
}