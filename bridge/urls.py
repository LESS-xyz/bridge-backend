from django.contrib import admin
from django.urls import path
from bridge.relayer.views import provide_signature

urlpatterns = [
    path('provide_signature/', provide_signature),
]
