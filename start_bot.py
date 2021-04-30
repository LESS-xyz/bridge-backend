import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
import django
django.setup()

from bridge.bot.bot import Bot
from bridge.settings import bot_token

Bot(bot_token).start()
