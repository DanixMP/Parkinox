# Parkinox v3

A comprehensive parking management system with mobile applications for students and operators, and a Django REST API backend.

## Project Structure

```
Parkinox-v3-M/
├── backend/              # Django REST API
├── parkinox_stdn/        # Flutter app for students
├── parkinox_op/          # Flutter app for operators
└── Core/                 # Core utilities and shared code
```

## Components

### Backend (Django REST API)
- **Location**: `backend/`
- **Framework**: Django with Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **Features**:
  - User authentication and authorization
  - Parking space management
  - Reservation system
  - Rate configuration
  - WebSocket support for real-time updates
  - Plate recognition integration

### Student Mobile App (Flutter)
- **Location**: `parkinox_stdn/`
- **Framework**: Flutter
- **Features**:
  - User authentication
  - Parking space search and booking
  - Reservation management
  - OTP verification
  - Settings and profile management

### Operator Mobile App (Flutter)
- **Location**: `parkinox_op/`
- **Framework**: Flutter
- **Features**:
  - Dashboard with statistics
  - Parking space monitoring
  - Gate event management
  - Real-time updates via WebSocket

## Getting Started

### Prerequisites
- Python 3.8+
- Flutter SDK
- Node.js (if applicable)
- Git

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Start the development server:
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/`

### Mobile Apps Setup

1. Navigate to the app directory:
```bash
cd parkinox_stdn  # or parkinox_op
```

2. Get Flutter dependencies:
```bash
flutter pub get
```

3. Run the app:
```bash
flutter run
```

## API Documentation

The backend provides a REST API with the following main endpoints:

- **Authentication**: `/api/auth/`
- **Accounts**: `/api/accounts/`
- **Parking**: `/api/parking/`
- **Plates**: `/api/plates/`
- **Reservations**: `/api/reservations/`

For detailed API documentation, refer to the backend's API documentation or use the Django admin interface at `/admin/`.

## Authentication

The system uses token-based authentication. For more details, see `backend/accounts/AUTH_README.md`.

## Configuration

### Backend Configuration
- Development settings: `backend/config/settings/development.py`
- Production settings: `backend/config/settings/production.py`
- Base settings: `backend/config/settings/base.py`

### Environment Variables
See `.env.example` for required environment variables.

## Testing

### Backend Tests
```bash
cd backend
python manage.py test
```

### Mobile App Tests
```bash
cd parkinox_stdn  # or parkinox_op
flutter test
```

## Project Features

- **Real-time Updates**: WebSocket support for live parking space status
- **Plate Recognition**: Integration with plate recognition system
- **Multi-role Support**: Different interfaces for students and operators
- **Rate Management**: Configurable parking rates
- **Reservation System**: Book parking spaces in advance
- **OTP Verification**: Secure user verification

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

[UNIVERSITY PROJECT ONLY.]

## Support

For issues and questions, please open an issue on GitHub.

## Authors

- [MP.]

## Changelog

See CHANGELOG.md for version history and updates.
