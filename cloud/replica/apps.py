"""Seed default organization/site on migrate."""

from django.apps import AppConfig


class ReplicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'replica'

    def ready(self):
        pass
