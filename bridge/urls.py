from django.contrib import admin
from django.urls import path
from bridge.relayer.views import provide_signature, is_online

urlpatterns = [
    path('provide_signature/', provide_signature),
    path('is_online/', is_online),
]
