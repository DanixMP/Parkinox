from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from .models import Wallet


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """
    Auto-create wallet when a new User is created.
    
    Requirement 3.1: WHEN a new user is created, THE Backend SHALL 
    automatically create an associated wallet with zero balance.
    """
    if created:
        Wallet.objects.create(user=instance, balance=0)
