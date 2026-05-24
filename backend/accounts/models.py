from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator


class UserManager(BaseUserManager):
    """
    Custom user manager for User model with phone as the unique identifier.
    """
    
    def create_user(self, phone, password=None, **extra_fields):
        """
        Create and save a regular user with the given phone and password.
        """
        if not phone:
            raise ValueError('The Phone field must be set')
        
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone, password=None, **extra_fields):
        """
        Create and save a superuser with the given phone and password.
        """
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with role-based access control.
    
    Extends AbstractBaseUser with fields: full_name, student_id, phone, email,
    password_hash, role, is_active.
    
    Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 78.1, 78.2
    """
    
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('operator', 'Operator'),
        ('admin', 'Admin'),
    ]
    
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=150)
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=15,
        unique=True,
        validators=[phone_validator],
        help_text="Phone number in international format"
    )
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    # password field is inherited from AbstractBaseUser as 'password'
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student',
        help_text="User role: student, operator, or admin"
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['full_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['student_id']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.phone})"
    
    def has_role(self, *roles):
        """
        Check if user has one of the specified roles.
        """
        return self.role in roles
