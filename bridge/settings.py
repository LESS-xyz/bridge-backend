import os
import yaml
import requests
from munch import munchify
from web3 import Web3, HTTPProvider

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = False

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bridge.validator',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bridge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bridge.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'multisig_bridge'),
        'USER': os.getenv('POSTGRES_USER', 'multisig_bridge'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'multisig_bridge'),
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.getenv('POSTGRES_PORT', 5432),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

MAX_FILTER_LENGTH = 50


def get_abi(api_url, api_key, address):
    url = f'{api_url}api?module=contract&action=getabi&address={address}&apikey={api_key}'
    return requests.get(url).json()['result']


with open(os.path.dirname(__file__) + '/../config.yaml') as f:
    config_data = yaml.safe_load(f)

SECRET_KEY = config_data['django_secret_key']

networks = {}

for data in config_data['networks']:
    network = munchify(data)
    network.w3 = Web3(HTTPProvider(data['node']))

    swap_contract_abi = get_abi(
        network.explorer_api_url,
        network.explorer_api_key,
        network.swap_contract,
    )
    network.swap_contract = network.w3.eth.contract(address=network.swap_contract, abi=swap_contract_abi)
    '''
    token_abi = get_abi(network.explorer_api_url, network.explorer_api_key, token_address)
    token_dict = {}
    token_address = token_dict['address'] = swap_contract.functions.tokenAddress().call()
    token_dict['abi'] = 

    token_dict['contract'] = token_contract = w3.eth.contract(address=token_address, abi=token_dict['abi'])
    token_dict['decimals'] = token_contract.functions.decimals().call()
    token_dict['symbol'] = token_contract.functions.symbol().call()

    data['swap_contract'] = swap_contract_dict
    data['token'] = token_dict
    '''
    networks[network.num] = network


relayers = config_data['relayers']
print('settings loaded')
