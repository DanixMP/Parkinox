from django.test import TestCase
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import User
from wallets.models import Wallet, WalletTransaction
from wallets.services import WalletService, InsufficientFundsError


class WalletSignalTestCase(TestCase):
    """
    Test that wallets are automatically created when users are created.
    
    Requirement 3.1: WHEN a new user is created, THE Backend SHALL 
    automatically create an associated wallet with zero balance.
    """
    
    def test_wallet_auto_created_on_user_creation(self):
        """Test that a wallet is automatically created when a user is created."""
        # Create a user
        user = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test User'
        )
        
        # Verify wallet was created
        self.assertTrue(hasattr(user, 'wallet'))
        self.assertIsNotNone(user.wallet)
        
        # Verify initial balance is zero
        self.assertEqual(user.wallet.balance, 0)
    
    def test_wallet_balance_non_negative_constraint(self):
        """Test that wallet balance cannot be negative."""
        user = User.objects.create_user(
            phone='+989123456788',
            password='testpass123',
            full_name='Test User 2'
        )
        
        wallet = user.wallet
        
        # Try to set negative balance (should fail at database level)
        wallet.balance = -100
        
        with self.assertRaises(Exception):
            wallet.save()


class WalletTransactionTestCase(TestCase):
    """
    Test wallet transaction model functionality.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test User'
        )
        self.operator = User.objects.create_user(
            phone='+989123456788',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )
    
    def test_create_topup_transaction(self):
        """Test creating a top-up transaction."""
        wallet = self.user.wallet
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            amount=50000,
            type='topup',
            description='Test top-up',
            performed_by=self.operator,
            reference_code='TEST-TOPUP-001'
        )
        
        self.assertEqual(transaction.type, 'topup')
        self.assertEqual(transaction.amount, 50000)
        self.assertEqual(transaction.performed_by, self.operator)
        self.assertEqual(transaction.reference_code, 'TEST-TOPUP-001')
    
    def test_create_fee_transaction(self):
        """Test creating a fee transaction."""
        wallet = self.user.wallet
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            amount=5000,
            type='fee',
            description='Parking fee'
        )
        
        self.assertEqual(transaction.type, 'fee')
        self.assertEqual(transaction.amount, 5000)
    
    def test_transaction_immutability(self):
        """Test that transactions cannot be modified after creation."""
        wallet = self.user.wallet
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            amount=10000,
            type='topup'
        )
        
        # Try to modify the transaction
        transaction.amount = 20000
        
        with self.assertRaises(ValueError) as context:
            transaction.save()
        
        self.assertIn('cannot be modified', str(context.exception))
    
    def test_unique_reference_code(self):
        """Test that reference codes must be unique."""
        wallet = self.user.wallet
        
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=10000,
            type='topup',
            reference_code='UNIQUE-REF-001'
        )
        
        # Try to create another transaction with the same reference code
        with self.assertRaises(Exception):
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=20000,
                type='topup',
                reference_code='UNIQUE-REF-001'
            )


class WalletServiceTestCase(TestCase):
    """
    Test WalletService for balance operations.
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 18.1, 18.2, 18.6, 18.7, 52.1, 52.2
    """
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test User'
        )
        self.operator = User.objects.create_user(
            phone='+989123456788',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )
        self.wallet = self.user.wallet
    
    def test_get_balance(self):
        """
        Test getting wallet balance.
        
        Requirement 5.1: Get current balance in Toman.
        """
        # Set a balance
        self.wallet.balance = 50000
        self.wallet.save()
        
        # Get balance using service
        balance = WalletService.get_balance(self.user.id)
        
        self.assertEqual(balance, 50000)
        self.assertIsInstance(balance, int)
    
    def test_get_balance_nonexistent_user(self):
        """Test getting balance for non-existent user raises error."""
        with self.assertRaises(ObjectDoesNotExist):
            WalletService.get_balance(99999)
    
    def test_topup_increases_balance(self):
        """
        Test that top-up increases wallet balance.
        
        Requirements:
        - 5.1: Increase wallet balance by specified amount
        - 5.2: Create transaction record with type 'topup'
        """
        initial_balance = self.wallet.balance
        topup_amount = 50000
        
        # Perform top-up
        txn = WalletService.topup(
            wallet_id=self.wallet.id,
            amount=topup_amount,
            operator_id=self.operator.id
        )
        
        # Refresh wallet from database
        self.wallet.refresh_from_db()
        
        # Verify balance increased
        self.assertEqual(self.wallet.balance, initial_balance + topup_amount)
        
        # Verify transaction was created
        self.assertIsNotNone(txn)
        self.assertEqual(txn.type, 'topup')
        self.assertEqual(txn.amount, topup_amount)
        self.assertEqual(txn.wallet, self.wallet)
    
    def test_topup_records_operator(self):
        """
        Test that top-up records the operator who performed it.
        
        Requirement 5.3: Record operator's user ID who performed the top-up.
        """
        txn = WalletService.topup(
            wallet_id=self.wallet.id,
            amount=30000,
            operator_id=self.operator.id
        )
        
        # Verify operator is recorded
        self.assertEqual(txn.performed_by, self.operator)
        self.assertIn(self.operator.full_name, txn.description)
    
    def test_topup_rejects_negative_amount(self):
        """
        Test that top-up rejects negative amounts.
        
        Requirement 5.5: Reject top-up requests with negative or zero amounts.
        """
        with self.assertRaises(ValueError) as context:
            WalletService.topup(
                wallet_id=self.wallet.id,
                amount=-1000,
                operator_id=self.operator.id
            )
        
        self.assertIn('positive', str(context.exception).lower())
    
    def test_topup_rejects_zero_amount(self):
        """
        Test that top-up rejects zero amounts.
        
        Requirement 5.5: Reject top-up requests with negative or zero amounts.
        """
        with self.assertRaises(ValueError) as context:
            WalletService.topup(
                wallet_id=self.wallet.id,
                amount=0,
                operator_id=self.operator.id
            )
        
        self.assertIn('positive', str(context.exception).lower())
    
    def test_deduct_fee_with_sufficient_balance(self):
        """
        Test deducting fee when balance is sufficient.
        
        Requirements:
        - 18.1: Deduct fee from wallet
        - 18.2: Create transaction record with type 'fee'
        """
        # Set initial balance
        self.wallet.balance = 50000
        self.wallet.save()
        
        fee_amount = 20000
        session_id = 123
        
        # Deduct fee
        txn = WalletService.deduct_fee(
            wallet_id=self.wallet.id,
            amount=fee_amount,
            session_id=session_id
        )
        
        # Refresh wallet from database
        self.wallet.refresh_from_db()
        
        # Verify balance decreased
        self.assertEqual(self.wallet.balance, 30000)
        
        # Verify transaction was created
        self.assertIsNotNone(txn)
        self.assertEqual(txn.type, 'fee')
        self.assertEqual(txn.amount, fee_amount)
        self.assertEqual(txn.wallet, self.wallet)
        self.assertIn(str(session_id), txn.description)
    
    def test_deduct_fee_with_insufficient_balance(self):
        """
        Test that deducting fee with insufficient balance raises error.
        
        Requirements:
        - 18.5: Set session status to 'unpaid' when balance insufficient
        - 18.6: Do not deduct any amount when balance insufficient
        """
        # Set low balance
        self.wallet.balance = 5000
        self.wallet.save()
        
        fee_amount = 20000
        
        # Try to deduct fee (should fail)
        with self.assertRaises(InsufficientFundsError):
            WalletService.deduct_fee(
                wallet_id=self.wallet.id,
                amount=fee_amount,
                session_id=123
            )
        
        # Refresh wallet from database
        self.wallet.refresh_from_db()
        
        # Verify balance unchanged
        self.assertEqual(self.wallet.balance, 5000)
        
        # Verify no transaction was created
        fee_transactions = WalletTransaction.objects.filter(
            wallet=self.wallet,
            type='fee'
        )
        self.assertEqual(fee_transactions.count(), 0)
    
    def test_deduct_fee_atomicity(self):
        """
        Test that fee deduction and transaction creation are atomic.
        
        Requirements:
        - 18.7: Perform wallet deduction and transaction creation atomically
        - 52.1: Execute in single database transaction
        """
        # Set initial balance
        self.wallet.balance = 50000
        self.wallet.save()
        
        initial_txn_count = WalletTransaction.objects.count()
        
        # Deduct fee
        WalletService.deduct_fee(
            wallet_id=self.wallet.id,
            amount=20000,
            session_id=123
        )
        
        # Verify both balance and transaction were updated
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 30000)
        self.assertEqual(WalletTransaction.objects.count(), initial_txn_count + 1)
    
    def test_check_sufficient_balance_true(self):
        """Test checking sufficient balance returns True when balance is enough."""
        self.wallet.balance = 50000
        self.wallet.save()
        
        result = WalletService.check_sufficient_balance(
            user_id=self.user.id,
            required_amount=30000
        )
        
        self.assertTrue(result)
    
    def test_check_sufficient_balance_false(self):
        """Test checking sufficient balance returns False when balance is insufficient."""
        self.wallet.balance = 10000
        self.wallet.save()
        
        result = WalletService.check_sufficient_balance(
            user_id=self.user.id,
            required_amount=30000
        )
        
        self.assertFalse(result)
    
    def test_check_sufficient_balance_exact(self):
        """Test checking sufficient balance returns True when balance equals required amount."""
        self.wallet.balance = 20000
        self.wallet.save()
        
        result = WalletService.check_sufficient_balance(
            user_id=self.user.id,
            required_amount=20000
        )
        
        self.assertTrue(result)
    
    def test_check_sufficient_balance_nonexistent_user(self):
        """Test checking balance for non-existent user raises error."""
        with self.assertRaises(ObjectDoesNotExist):
            WalletService.check_sufficient_balance(
                user_id=99999,
                required_amount=10000
            )
