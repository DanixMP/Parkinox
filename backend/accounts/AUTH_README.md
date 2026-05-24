# JWT Authentication Implementation

## Overview

This document describes the JWT authentication implementation for the Parkinox Smart University Parking System. The authentication system uses `djangorestframework-simplejwt` to provide secure token-based authentication.

## Requirements Implemented

- **Requirement 1.1**: User authentication with JWT tokens
- **Requirement 1.5**: Operator token for WebSocket authentication
- **Requirement 1.6**: Token refresh functionality
- **Requirement 78.1**: Password hashing using Django's PBKDF2
- **Requirement 78.4**: Access token expiration (1 hour)
- **Requirement 78.5**: Refresh token expiration (7 days)
- **Requirement 79.1**: Login endpoint returning tokens and user info
- **Requirement 79.2**: Operator token included for operators/admins
- **Requirement 79.3**: Token refresh endpoint
- **Requirement 79.4**: Invalid credentials return 401
- **Requirement 79.5**: Expired tokens handled properly

## API Endpoints

### 1. Login Endpoint

**URL**: `POST /api/auth/login/`

**Request Body**:
```json
{
  "phone": "+989123456789",
  "password": "your_password"
}
```

**Success Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "full_name": "علی رضایی",
    "phone": "+989123456789",
    "email": "ali@example.com",
    "student_id": "40012345",
    "role": "student"
  },
  "operator_token": null
}
```

**Notes**:
- `operator_token` is only included for users with role 'operator' or 'admin'
- For operators/admins, `operator_token` equals `access_token`
- Students receive `operator_token: null`

**Error Response (401 Unauthorized)**:
```json
{
  "error": "Invalid credentials",
  "details": {
    "non_field_errors": ["Invalid credentials."]
  }
}
```

### 2. Token Refresh Endpoint

**URL**: `POST /api/auth/refresh/`

**Request Body**:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Response (401 Unauthorized)**:
```json
{
  "error": "Invalid or expired refresh token",
  "details": {
    "non_field_errors": ["Invalid or expired refresh token."]
  }
}
```

## Token Configuration

The JWT tokens are configured in `backend/config/settings/base.py`:

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),      # 1 hour
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),      # 7 days
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

## Password Hashing

Passwords are automatically hashed using Django's default PBKDF2 algorithm with SHA256:
- Algorithm: `pbkdf2_sha256`
- Iterations: 720,000 (Django 5.0 default)
- Secure and industry-standard

Example hashed password:
```
pbkdf2_sha256$720000$2D8bXof2WYD2LKzwizhoT4$SlkLo7edsVyOtp2ksVuqR9GaDobvp0VuzH6+4s4QKwE=
```

## Authentication Flow

### 1. Initial Login
```
Client → POST /api/auth/login/ (phone, password)
Server → Validates credentials
Server → Generates JWT tokens
Server → Returns access_token, refresh_token, user info, operator_token
Client → Stores tokens
```

### 2. Authenticated Requests
```
Client → GET/POST /api/protected-endpoint/
        Header: Authorization: Bearer <access_token>
Server → Validates JWT signature and expiration
Server → Returns requested data
```

### 3. Token Refresh
```
Client → POST /api/auth/refresh/ (refresh_token)
Server → Validates refresh token
Server → Generates new access_token
Server → Returns new access_token
Client → Updates stored access_token
```

## User Roles

The system supports three user roles:

1. **Student** (`role='student'`)
   - Default role for new users
   - Can register plates and use parking services
   - Does NOT receive `operator_token`

2. **Operator** (`role='operator'`)
   - Can manage gate events and process payments
   - Receives `operator_token` for WebSocket authentication
   - Has elevated permissions

3. **Admin** (`role='admin'`)
   - Full system access
   - Receives `operator_token` for WebSocket authentication
   - Can perform all operations

## Test Users

For development and testing, the following test users are available:

| Role     | Phone          | Password    | Full Name     |
|----------|----------------|-------------|---------------|
| Student  | +989123456789  | student123  | علی رضایی     |
| Operator | +989123456790  | operator123 | محمد احمدی   |
| Admin    | +989123456791  | admin123    | سارا کریمی   |

## Testing

### Running Unit Tests

```bash
cd backend
python manage.py test accounts
```

### Manual API Testing

```bash
# Test login
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "+989123456789", "password": "student123"}'

# Test token refresh
curl -X POST http://127.0.0.1:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "YOUR_REFRESH_TOKEN"}'
```

### Automated Test Script

```bash
cd backend
python test_api.py
```

## Security Considerations

1. **Token Storage**: 
   - Access tokens should be stored in memory
   - Refresh tokens can be stored in secure storage (QSettings for desktop app)
   - Never store tokens in localStorage in web applications

2. **Token Expiration**:
   - Access tokens expire after 1 hour
   - Refresh tokens expire after 7 days
   - Implement automatic token refresh before expiration

3. **HTTPS Required**:
   - Always use HTTPS in production
   - Tokens transmitted over HTTP can be intercepted

4. **Password Requirements**:
   - Minimum length enforced by Django validators
   - Common password validation enabled
   - User attribute similarity validation enabled

## WebSocket Authentication

For WebSocket connections (used by Operator Panel):

1. Operator/Admin logs in via REST API
2. Receives `operator_token` in login response
3. Uses `operator_token` to authenticate WebSocket connection
4. WebSocket consumer validates token on connection

Example WebSocket connection:
```python
ws_url = f"ws://backend/ws/panel/?token={operator_token}"
```

## Files Structure

```
backend/accounts/
├── models.py           # User model with custom manager
├── serializers.py      # Login and token refresh serializers
├── views.py            # LoginView and TokenRefreshView
├── urls.py             # URL routing for auth endpoints
├── tests.py            # Unit tests for authentication
└── AUTH_README.md      # This documentation file
```

## Integration with Other Components

### Wallet Creation
When a new user is created, a wallet is automatically created via Django signals (implemented in Task 3.1).

### Protected Endpoints
Other API endpoints use JWT authentication by default:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

To make an endpoint public (like login), use:
```python
class PublicView(APIView):
    permission_classes = [AllowAny]
```

## Troubleshooting

### Issue: "Invalid credentials" error
- Verify phone number format (must include country code)
- Check password is correct
- Ensure user account is active (`is_active=True`)

### Issue: "Invalid or expired refresh token"
- Refresh token may have expired (7 days)
- User needs to log in again
- Check token wasn't modified or corrupted

### Issue: 401 on protected endpoints
- Access token may have expired (1 hour)
- Use refresh token to get new access token
- Verify Authorization header format: `Bearer <token>`

## Next Steps

After implementing authentication (Task 2.2), the following tasks depend on it:

- **Task 2.3**: Write unit tests for authentication (✓ Completed)
- **Task 7.2**: Implement WebSocket consumer with JWT authentication
- **Task 9.2**: Configure JWT authentication on all protected endpoints
- **Task 11.1**: Implement Operator Panel login window

## References

- [Django REST Framework SimpleJWT Documentation](https://django-rest-framework-simplejwt.readthedocs.io/)
- [Django Authentication System](https://docs.djangoproject.com/en/4.2/topics/auth/)
- [JWT.io - Introduction to JSON Web Tokens](https://jwt.io/introduction)
