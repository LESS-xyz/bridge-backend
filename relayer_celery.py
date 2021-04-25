import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

app = Celery('relayer_celery', broker='amqp://rabbit:rabbit@rabbitmq:5672/rabbit', include=['bridge.relayer.tasks'])
# app.config_from_object('django.conf:settings', namespace='CELERY')
# app.conf.update(result_expires=3600, enable_utc=True, timezone=CELERY_TIMEZONE)

app.conf.beat_schedule['check_swaps'] = {
    'task': 'bridge.relayer.tasks.check_swaps',
    'schedule': crontab(minute=f'*/1'),
}