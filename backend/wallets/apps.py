from django.apps import AppConfig


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures the post_save signal for wallet creation is registered.
        """
        import wallets.signals
