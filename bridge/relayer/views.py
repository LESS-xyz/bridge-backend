from django.db import IntegrityError
from django.shortcuts import render
from rest_framework.decorators import api_view
from munch import munchify
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response

from bridge.settings import networks
from web3 import Web3
from eth_account.messages import encode_defunct
from eth_account import Account, messages
from bridge.relayer.models import Swap, Signature


@api_view(http_method_names=['POST'])
def provide_signature(request):
    validator_data = request.data
    from_tx_hash = validator_data['from_tx_hash']

    try:
        swap = Swap.objects.get(from_tx_hash=from_tx_hash)
    except Swap.DoesNotExist:
        swap = Swap(
            from_tx_hash=from_tx_hash,
            from_network_num=validator_data['from_network_num'],
        )
        swap.save()

    try:
        signature = Signature(
            swap=swap,
            signature=validator_data['signature'],
        )
        signature.save()
    except IntegrityError:
        raise PermissionDenied


@api_view(http_method_names=['POST'])
def is_signature_submitted(request):
    data = munchify(request.data)
    try:
        swap = Swap.objects.get(from_hash=data.tx_hash)
    except Swap.DoesNotExist:
        raise NotFound

    try:
        Signature.objects.get(swap=swap, signer=data.validator)
    except Signature.DoesNotExist:
        raise NotFound

    return Response(status=200)

