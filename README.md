# Admin Dashboard Backend

A Flask-based REST API backend for an admin dashboard application with user management, authentication, and data export features.

## Features

- **User Authentication**: JWT-based authentication with access and refresh tokens
- **User Management**: CRUD operations for users with role-based access control
- **Email Verification**: Secure email verification system with timed tokens
- **Password Reset**: Secure password reset functionality via email
- **Role-Based Access Control**: Admin and user roles with protected endpoints
- **Rate Limiting**: Request rate limiting to prevent abuse
- **Data Export**: PDF and Excel export capabilities for user data
- **Demo Mode**: Demo user functionality for testing purposes
- **Database Migrations**: Alembic-based database schema management
- **CORS Support**: Configurable CORS for frontend integration

## Tech Stack

- **Framework**: Flask
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Flask-JWT-Extended
- **Email**: Flask-Mail
- **Migrations**: Flask-Migrate (Alembic)
- **Rate Limiting**: Flask-Limiter
- **PDF Generation**: WeasyPrint
- **Excel Export**: openpyxl
- **CORS**: Flask-CORS

## Project Structure

```
admin_dashboard_backend/
├── app.py                 # Application entry point
├── app_init.py           # Flask app factory
├── models.py             # SQLAlchemy models
├── extensions.py         # Flask extensions configuration
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── blueprints/           # API blueprints
│   ├── auth.py          # Authentication endpoints
│   ├── users.py         # User management endpoints
│   └── demo.py          # Demo data endpoints
├── migrations/          # Database migration files
├── templates/           # HTML templates for PDF generation
├── static/             # Static files
└── tests/              # Test files
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd admin_dashboard_backend
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root with the following variables:
   ```env
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://user:password@localhost/dbname
   ALLOWED_ORIGINS=http://localhost:5173
   EMAIL_VERIFICATION_TOKEN_EXPIRES=3600
   EMAIL_VERIFICATION_SALT=email-verification
   EMAIL_VERIFICATION_URL=http://localhost:5000/api/auth/verify-email/{token}
   EMAIL_RESET_PASSWORD_URL=http://localhost:5000/api/auth/reset-password/{token}
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USE_SSL=False
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=noreply@example.com
   REQUEST_MAIL_VERIFICATION=True
   FLASK_DEBUG=False
   ```

5. **Initialize the database**
   ```bash
   flask db upgrade
   ```

## Running the Application

Start the development server:
```bash
python app.py
```

The server will run on `http://0.0.0.0:5000` by default.

## API Endpoints

### Authentication (`/api/auth`)

- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and receive JWT tokens
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Logout (revoke token)
- `POST /api/auth/verify-email/{token}` - Verify email address
- `POST /api/auth/request-verification` - Request email verification
- `POST /api/auth/request-password-reset` - Request password reset
- `POST /api/auth/reset-password/{token}` - Reset password with token

### Users (`/api/users`)

- `GET /api/users` - Get all users (admin only)
- `GET /api/users/stats` - Get user statistics (admin only)
- `GET /api/users/<id>` - Get user by ID
- `PUT /api/users/<id>` - Update user (admin or own user)
- `DELETE /api/users/<id>` - Delete user (admin only)
- `GET /api/users/export/pdf` - Export users to PDF (admin only)
- `GET /api/users/export/excel` - Export users to Excel (admin only)

### Demo (`/api/demo`)

- `POST /api/demo/seed` - Seed demo data (demo users only)
- `DELETE /api/demo/clear` - Clear demo data (demo users only)

## Database Models

### User Model

- `id` - Primary key
- `username` - Unique username
- `email` - Unique email address
- `pending_email` - Email pending verification
- `password_hash` - Hashed password
- `is_email_verified` - Email verification status
- `role` - User role (user/admin)
- `is_active` - Account active status
- `is_demo` - Demo user flag
- `is_demo_data` - Demo data flag
- `last_seen` - Last activity timestamp
- `created_at` - Account creation timestamp
- `updated_at` - Last update timestamp

## Security Features

- **Password Hashing**: Uses Werkzeug's password hashing
- **JWT Tokens**: Time-limited access and refresh tokens
- **Token Blocklist**: Revoked tokens are blocked
- **Rate Limiting**: Prevents brute force attacks
- **Email Verification**: Ensures valid email addresses
- **Role-Based Access**: Admin-only endpoints protected
- **CORS Configuration**: Controlled cross-origin access

## Testing

Run tests using pytest:
```bash
pytest
```

## Database Migrations

Create a new migration:
```bash
flask db migrate -m "description of changes"
```

Apply migrations:
```bash
flask db upgrade
```

Rollback migrations:
```bash
flask db downgrade
```

## Configuration

Key configuration options in `.env`:

- `SECRET_KEY` - Secret key for JWT and session encryption
- `DATABASE_URL` - PostgreSQL connection string
- `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins
- `EMAIL_VERIFICATION_TOKEN_EXPIRES` - Token expiration time in seconds
- `MAIL_SERVER` - SMTP server for email sending
- `REQUEST_MAIL_VERIFICATION` - Enable/disable email verification requirement

## Development

The application supports debug mode when `FLASK_DEBUG=True` is set in the environment.

## License

[Specify your license here]
