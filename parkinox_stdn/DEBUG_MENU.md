# 🔧 DEBUG MENU - Superuser Features

## Overview

The DEBUG MENU is a comprehensive development and testing tool exclusively available to superusers (staff members) registered in the Django backend. It provides real-time API testing, configuration management, and system diagnostics.

## Access

### How to Open DEBUG MENU

1. Go to **Settings** screen
2. Tap the **Settings icon** (⚙️) in the top-right corner **5 times**
3. The DEBUG MENU will open automatically (no visual feedback during tapping)

### Requirements

- User must be registered as a **superuser** or **staff member** in Django backend
- User must be logged in
- Access is automatically verified against the backend

## Features

### 🌐 API Configuration

**Purpose**: Manage API base URL for development and testing

**Features**:
- View current API base URL
- Change API base URL dynamically
- Reset to default (`https://parkinox.ir/api`)
- Changes take effect immediately

**Default URL**: `https://parkinox.ir/api`

**Use Cases**:
- Switch between production and development servers
- Test against local development environment
- Test against staging servers

### 🧪 API Testing

**Purpose**: Test API endpoints in real-time without external tools

**Available Tests**:

1. **Test Auth Endpoint** (`GET /auth/student/me/`)
   - Verifies authentication is working
   - Returns current user information
   - Useful for checking token validity

2. **Test Wallet Endpoint** (`GET /wallets/student/`)
   - Checks wallet functionality
   - Returns wallet balance and transaction history
   - Verifies wallet API connectivity

3. **Test Parking Endpoint** (`GET /parking/sessions/`)
   - Tests parking session API
   - Returns active and past sessions
   - Verifies parking system connectivity

4. **Test Cars Endpoint** (`GET /cars/student/`)
   - Tests vehicle plate management API
   - Returns registered plates
   - Verifies car management system

**How to Use**:
1. Tap the "Test" button next to any endpoint
2. Wait for response
3. View results in a dialog showing JSON response or error message

### 🔐 Token Management

**Purpose**: Inspect and manage authentication tokens

**Features**:
- View Access Token (truncated for security)
- View Refresh Token (truncated for security)
- Clear all tokens (forces re-login)

**Use Cases**:
- Debug authentication issues
- Verify token format
- Force logout for testing
- Test token refresh mechanism

### 📱 Device Information

**Purpose**: View device and system information

**Displays**:
- Platform (iOS/Android)
- Screen brightness mode
- Screen resolution
- Device pixel ratio

**Use Cases**:
- Debug UI rendering issues
- Test responsive design
- Verify device capabilities

### ⚠️ Danger Zone

**Purpose**: Destructive operations for testing

**Operations**:
- **Clear All Local Data**: Removes all cached data, tokens, and preferences
  - Requires confirmation
  - Forces user to login again
  - Useful for testing fresh install scenarios

## API Endpoints Reference

### Authentication
- `GET /auth/student/me/` - Get current user info
- `POST /auth/student/otp/send/` - Send OTP
- `POST /auth/student/otp/verify/` - Verify OTP
- `POST /auth/refresh/` - Refresh access token

### Wallet
- `GET /wallets/student/` - Get wallet info
- `POST /wallets/student/demo-topup/` - Demo top-up

### Parking
- `GET /parking/sessions/` - Get parking sessions
- `GET /parking/rates/` - Get parking rates

### Cars
- `GET /cars/student/` - Get user's plates
- `POST /cars/student/` - Add new plate

## Superuser Setup (Backend)

To enable DEBUG MENU access for a user:

### Django Admin

1. Go to Django Admin (`/admin/`)
2. Navigate to Users
3. Select the user
4. Check **"Staff status"** or **"Superuser status"**
5. Save

### Command Line

```bash
python manage.py shell
from django.contrib.auth.models import User
user = User.objects.get(username='username')
user.is_staff = True  # or is_superuser = True
user.save()
```

## Response Format

All API test responses are displayed as JSON in a dialog:

```json
{
  "id": 1,
  "username": "student123",
  "email": "student@example.com",
  "full_name": "John Doe",
  "phone": "+989123456789",
  "is_superuser": true,
  "is_staff": true
}
```

## Error Handling

If an API test fails, you'll see:

```
Error: [Error message from server]
Status Code: [HTTP status code]
```

**Common Errors**:
- `401 Unauthorized` - Token expired or invalid
- `403 Forbidden` - User doesn't have permission
- `404 Not Found` - Endpoint doesn't exist
- `500 Server Error` - Backend error

## Security Notes

⚠️ **Important**:
- DEBUG MENU is only accessible to superusers
- Tokens are partially masked for security
- All API calls use the same authentication as the app
- Debug data is not logged or stored
- Clear tokens immediately after testing if needed

## Troubleshooting

### DEBUG MENU Not Appearing

**Problem**: Tapping settings icon doesn't open DEBUG MENU

**Solutions**:
1. Verify user is superuser in Django admin
2. Check that user is logged in
3. Ensure API is reachable
4. Try clearing app cache and restarting

### API Tests Failing

**Problem**: All API tests return errors

**Solutions**:
1. Check API base URL is correct
2. Verify internet connection
3. Check if backend is running
4. Verify authentication token is valid
5. Check backend logs for errors

### Token Issues

**Problem**: "Unauthorized" errors on all tests

**Solutions**:
1. Clear tokens and re-login
2. Check token expiration
3. Verify refresh token is working
4. Check backend token settings

## Development Workflow

### Testing New Features

1. Open DEBUG MENU
2. Change API URL to development server if needed
3. Test relevant endpoints
4. Check responses for expected data
5. Debug any issues using response data

### Testing API Changes

1. Update backend API
2. Open DEBUG MENU
3. Test updated endpoint
4. Verify response format
5. Update app code if needed

### Testing Authentication

1. Clear tokens in DEBUG MENU
2. Login again
3. Test auth endpoint
4. Verify tokens are set correctly
5. Test other endpoints

## Future Enhancements

Planned features for DEBUG MENU:
- [ ] Request/Response logging
- [ ] Network performance metrics
- [ ] Database query inspection
- [ ] Cache management
- [ ] Feature flag toggles
- [ ] Mock data generation
- [ ] API response simulation
- [ ] Crash log viewer

## Support

For issues or questions about DEBUG MENU:
1. Check this documentation
2. Review backend logs
3. Contact development team
4. Check GitHub issues

---

**Last Updated**: May 27, 2026
**Version**: 1.0.0
