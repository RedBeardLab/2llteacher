# Project Structure

The LLTeacher v2 project uses a flat module structure under the `src/` directory for all Django applications.

## Directory Layout

```
2_llteacher/ (project root)
├── pyproject.toml              # Project dependencies and configuration
├── uv.lock                     # Locked dependency versions
├── manage.py                   # Django management script
├── run_tests.py                # Optimized test runner
├── README.md                   # Project documentation
├── DESIGN_V2.md                # System design document
├── TESTING.md                  # Testing guide
│
├── src/                        # All source code
│   ├── __init__.py
│   │
│   ├── accounts/               # User management and authentication
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           # User, Student, Teacher models
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── forms.py
│   │   ├── email_service.py
│   │   ├── utils.py
│   │   ├── migrations/
│   │   ├── templates/
│   │   │   └── accounts/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       └── ...
│   │
│   ├── conversations/          # AI conversation handling
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           # Conversation, Message, Submission
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services.py         # Business logic
│   │   ├── migrations/
│   │   ├── templates/
│   │   │   └── conversations/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_services.py
│   │       └── ...
│   │
│   ├── homeworks/              # Homework and section management
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           # Homework, Section, SectionSolution
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── forms.py
│   │   ├── services.py         # Business logic
│   │   ├── migrations/
│   │   ├── templates/
│   │   │   └── homeworks/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_services.py
│   │       └── ...
│   │
│   ├── llm/                    # LLM configuration and services
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           # LLMConfig
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services.py         # LLM interaction logic
│   │   ├── migrations/
│   │   ├── templates/
│   │   │   └── llm/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_services.py
│   │       └── ...
│   │
│   └── llteacher/              # Main Django project
│       ├── __init__.py
│       ├── asgi.py
│       ├── wsgi.py
│       ├── settings.py         # Django settings
│       ├── test_settings.py    # Optimized test settings
│       ├── urls.py             # URL configuration
│       ├── views.py            # Homepage view
│       ├── context_processors.py
│       ├── management/
│       │   └── commands/
│       │       └── populate_test_database.py
│       └── permissions/
│           ├── __init__.py
│           ├── decorators.py
│           └── tests/
│
├── static/                     # Static files (CSS, JS)
│   ├── css/
│   │   ├── main.css
│   │   ├── conversation-detail.css
│   │   └── r-execution.css
│   └── js/
│       ├── conversation-detail.js
│       ├── real-time-chat.js
│       └── r-execution-manager.js
│
└── templates/                  # Shared templates
    ├── base.html
    └── homepage.html
```

## Key Structure Notes

### 1. Flat Source Directory

All Django applications are organized directly under `src/` rather than nested in an `apps/` directory. This simplifies:
- Import paths
- Python path management
- Test discovery
- IDE navigation

### 2. Application Organization

Each Django app follows the standard structure:
- `models.py` - Data models
- `views.py` - View layer
- `services.py` - Business logic (where applicable)
- `urls.py` - URL routing
- `forms.py` - Form definitions (where applicable)
- `admin.py` - Django admin configuration
- `apps.py` - App configuration
- `templates/{app_name}/` - App-specific templates
- `tests/` - Comprehensive test suite
- `migrations/` - Database migrations

### 3. Import Patterns

With the flat structure, imports are straightforward:

```python
# Importing models
from accounts.models import User, Student, Teacher
from conversations.models import Conversation, Message
from homeworks.models import Homework, Section
from llm.models import LLMConfig

# Importing services
from conversations.services import ConversationService
from homeworks.services import HomeworkService

# Importing views
from accounts.views import UserRegistrationView
from conversations.views import ConversationDetailView
```

### 4. Template Organization

Templates are organized in two levels:

1. **Shared templates**: Located in `templates/` at the root
   - `base.html` - Base template for all pages
   - `homepage.html` - Homepage template

2. **App-specific templates**: Located in `src/{app_name}/templates/{app_name}/`
   - Each app has its own templates directory
   - Templates are namespaced by app name

### 5. Static Files

Static files are centralized in the `static/` directory:
- `static/css/` - Stylesheets
- `static/js/` - JavaScript files

### 6. Testing

Tests are organized within each app:
- Location: `src/{app_name}/tests/`
- Naming: `test_{component}_{functionality}.py`
- Run with: `python run_tests.py {app_name}`

### 7. Python Path

The `src/` directory is automatically added to the Python path by:
- The `manage.py` script
- The `run_tests.py` script
- Django's `sys.path` configuration

This allows for clean imports without path manipulation:

```python
# Instead of: from src.accounts.models import User
# Simply use:
from accounts.models import User
```

## Development Workflow

### Running Tests

```bash
# Run all tests
python run_tests.py accounts conversations homeworks llm

# Run specific app
python run_tests.py accounts

# Run with verbosity
python run_tests.py accounts --verbosity=2
```

### Running the Development Server

```bash
python manage.py runserver
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Adding a New App

1. Create the app directory under `src/`:
   ```bash
   mkdir -p src/newapp
   ```

2. Create standard Django app files:
   - `__init__.py`
   - `models.py`
   - `views.py`
   - `urls.py`
   - `admin.py`
   - `apps.py`

3. Create directories:
   - `src/newapp/migrations/`
   - `src/newapp/templates/newapp/`
   - `src/newapp/tests/`

4. Add to `INSTALLED_APPS` in `src/llteacher/settings.py`:
   ```python
   INSTALLED_APPS = [
       # ...
       "newapp",
   ]
   ```

5. Add URL patterns to `src/llteacher/urls.py`:
   ```python
   urlpatterns = [
       # ...
       path("newapp/", include("newapp.urls")),
   ]
   ```

## Benefits of This Structure

1. **Simplicity**: Flat structure is easier to navigate and understand
2. **Clean Imports**: No complex path manipulation needed
3. **Standard Django**: Follows Django conventions
4. **IDE-Friendly**: Better autocomplete and navigation in IDEs
5. **Test Discovery**: Easier for test runners to find tests
6. **Scalable**: Can easily add new apps as the project grows

## Migration from Previous Structure

If you're migrating from the old `apps/` structure:

1. Move all apps from `apps/{app_name}` to `src/{app_name}`
2. Update `INSTALLED_APPS` in settings to remove the `apps.` prefix
3. Update all import statements to remove the `apps.` prefix
4. Update template paths in settings.py
5. Run tests to verify everything works

This structure change was made to simplify the project organization while maintaining all functionality and improving developer experience.
