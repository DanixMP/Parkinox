from django.contrib import admin
from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """
    Admin interface for Wallet model.
    """
    list_display = ['id', 'user', 'balance', 'last_updated']
    list_filter = ['last_updated']
    search_fields = ['user__full_name', 'user__phone', 'user__student_id']
    readonly_fields = ['last_updated']
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of wallets through admin."""
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    """
    Admin interface for WalletTransaction model.
    Transactions are immutable - no editing or deletion allowed.
    """
    list_display = ['id', 'wallet', 'type', 'amount', 'performed_by', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['wallet__user__full_name', 'reference_code', 'description']
    readonly_fields = ['wallet', 'amount', 'type', 'description', 'performed_by', 
                      'reference_code', 'created_at']
    
    def has_add_permission(self, request):
        """Prevent manual creation through admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of transactions."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of transactions."""
        return False
