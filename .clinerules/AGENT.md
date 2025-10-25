# Agent Development Guide for LLTeacher v2

This document provides comprehensive information for AI agents working on the LLTeacher codebase, including architecture patterns, development workflows, testing strategies, and best practices.

## 📋 Quick Reference

- **Project Type**: Django web application with AI-assisted educational features
- **Architecture**: Modular workspace structure using UV package manager
- **Testing**: 311+ comprehensive tests with 350x performance optimization
- **Key Pattern**: Service layer architecture with typed data contracts

## 🏗️ Project Architecture

### Workspace Structure

The project uses [UV workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) for modular dependency management. See [WORKSPACE_STRUCTURE.md](WORKSPACE_STRUCTURE.md) for detailed structure.

**Key Modules:**
- `src/accounts/` - User management and authentication
- `src/conversations/` - AI conversation handling and submissions  
- `src/homeworks/` - Homework and section management
- `src/llm/` - LLM configuration and services
- `src/llteacher/` - Main Django project

### Architecture Patterns

#### 1. Service Layer Pattern
All business logic is encapsulated in service classes with typed data contracts:

```python
@dataclass
class ConversationData:
    """Typed data contract for conversation operations."""
    id: UUID
    section_id: UUID
    messages: List[MessageViewData]
    can_submit: bool
    # ... other fields

class ConversationService:
    @staticmethod
    def get_conversation_data(conversation_id: UUID, user: User) -> ConversationData:
        """Service method with clear input/output contracts."""
        # Implementation here
```

#### 2. View-Service Separation
Views handle HTTP concerns, services handle business logic:

```python
class ConversationDetailView(View):
    def get(self, request: HttpRequest, conversation_id: UUID) -> HttpResponse:
        # Get data from service
        conversation_data = ConversationService.get_conversation_data(conversation_id, request.user)
        
        # Handle HTTP concerns (permissions, rendering)
        return render(request, 'template.html', {'conversation_data': conversation_data})
```

#### 3. Typed Data Contracts
All data passed between layers uses `@dataclass` for type safety:

```python
@dataclass
class MessageViewData:
    id: UUID
    content: str
    message_type: str
    timestamp: datetime
    is_from_student: bool
    is_from_ai: bool
    css_class: str  # For styling
```

## 🧪 Testing Strategy

### Test Organization
- **Location**: Each app has tests in `src/{app_name}/tests/`
- **Naming**: `test_{component}_{functionality}.py`
- **Structure**: One test class per component, descriptive test method names

### Running Tests

```bash
# Run all tests (fastest - uses optimized runner)
python run_tests.py accounts conversations homeworks llm

# Run specific app tests
python run_tests.py accounts
python run_tests.py conversations

# Run with verbose output
python run_tests.py accounts conversations homeworks llm --verbosity=2

# Alternative with uv
uv run python run_tests.py accounts conversations homeworks llm
```

### Test Performance
- **Optimized runner**: `python run_tests.py` (~0.061 seconds for 311 tests)
- **Standard Django**: `python manage.py test` (~21 seconds)
- **Speed improvement**: 350x faster with optimized runner

### Test Patterns

#### 1. Service Layer Testing
```python
class TestConversationService(TestCase):
    def test_get_conversation_data(self):
        # Test service methods directly
        result = ConversationService.get_conversation_data(conversation_id, user)
        self.assertIsInstance(result, ConversationData)
        self.assertEqual(result.id, conversation_id)
```

#### 2. View Testing with Mocks
```python
@patch('conversations.services.ConversationService.get_conversation_data')
def test_conversation_detail_view(self, mock_service):
    mock_service.return_value = mock_conversation_data
    response = self.client.get(url)
    self.assertEqual(response.status_code, 200)
```

#### 3. Permission Testing
```python
def test_student_cannot_submit_other_conversation(self):
    self.client.login(username='otherstudent', password='password123')
    response = self.client.post(submit_url)
    self.assertEqual(response.status_code, 403)
```

For comprehensive testing information, see [TESTING.md](TESTING.md).

## 🔧 Development Workflows

### Adding New Features

1. **Design First**: Update relevant design documents
2. **Models**: Add/modify Django models if needed
3. **Services**: Implement business logic in service layer
4. **Views**: Create views that use services
5. **Templates**: Add/update templates
6. **URLs**: Wire up URL patterns
7. **Tests**: Add comprehensive test coverage
8. **Documentation**: Update relevant docs

### Code Quality Standards

#### 1. Type Hints
Use type hints throughout, especially for service layer. Prefer built-in types and modern union syntax:

```python
# Preferred - use built-in types and modern union syntax
def get_messages(conversation_id: UUID) -> list[MessageData]:
    """Return list of messages."""

def get_metadata(conversation: Conversation) -> dict[str, str]:
    """Return metadata dictionary."""

def get_conversation_data(conversation_id: UUID, user: User) -> ConversationData | None:
    """Clear type contracts - use | None instead of Optional."""

def process_result(data: str | int) -> bool:
    """Use T | U instead of Union[T, U]."""

# Avoid - don't import from typing module
from typing import List, Dict, Optional, Union  # ❌ Don't do this
def get_messages(conversation_id: UUID) -> List[MessageData]:  # ❌ Use list instead
def get_metadata(conversation: Conversation) -> Dict[str, str]:  # ❌ Use dict instead
def get_conversation_data(conversation_id: UUID, user: User) -> Optional[ConversationData]:  # ❌ Use | None
def process_result(data: Union[str, int]) -> bool:  # ❌ Use str | int
```

**Built-in Type Preferences:**
- Use `list[T]` instead of `typing.List[T]`
- Use `dict[K, V]` instead of `typing.Dict[K, V]`
- Use `tuple[T, ...]` instead of `typing.Tuple[T, ...]`
- Use `set[T]` instead of `typing.Set[T]`
- Use `T | None` instead of `typing.Optional[T]`
- Use `T | U` instead of `typing.Union[T, U]`
- Only import from `typing` for complex types like `Protocol`, `TypeVar`, `Generic`

#### 2. Docstrings
Document all classes and methods:

```python
class ConversationService:
    """Service for managing conversation operations.
    
    Handles conversation creation, retrieval, and submission logic
    following the service layer pattern.
    """
    
    @staticmethod
    def start_conversation(user: User, section: Section) -> ConversationStartResult:
        """Start a new conversation for a user on a section.
        
        Args:
            user: The user starting the conversation
            section: The homework section for the conversation
            
        Returns:
            ConversationStartResult with success status and conversation_id
        """
```

#### 3. Error Handling
Use typed result objects for error handling:

```python
@dataclass
class ConversationStartResult:
    success: bool
    conversation_id: Optional[UUID] = None
    error: Optional[str] = None
```

### Database Patterns

#### 1. Soft Deletion
Use soft deletion pattern for important data:

```python
class Conversation(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def soft_delete(self):
        """Soft delete the conversation."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
```

#### 2. UUID Primary Keys
All models use UUID primary keys for security:

```python
class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

#### 3. Proper Relationships
Use appropriate relationship types with proper cascade behavior:

```python
class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE,
        related_name='messages'
    )
```

## 🎨 Frontend Patterns

### Template Organization
- **Base template**: `templates/base.html`
- **App templates**: `src/{app_name}/templates/{app_name}/`
- **Shared components**: Include reusable template fragments

### CSS and JavaScript
- **Bootstrap**: Used for responsive design
- **Real-time features**: Server-Sent Events for live chat
- **Progressive enhancement**: Features work without JavaScript

### Form Handling
```python
# Use CSRF protection
{% csrf_token %}

# Handle form errors gracefully
{% if form_data.errors %}
    <div class="alert alert-danger">
        {% for field, error in form_data.errors.items %}
            <li>{{ error }}</li>
        {% endfor %}
    </div>
{% endif %}
```

## 🔐 Security Patterns

### Authentication & Authorization
```python
@method_decorator(login_required)
def dispatch(self, *args, **kwargs):
    return super().dispatch(*args, **kwargs)

# Check ownership
if conversation.user != request.user:
    return HttpResponseForbidden("You can only access your own conversations.")

# Check role-based permissions
if not hasattr(request.user, 'student_profile'):
    return HttpResponseForbidden("Only students can submit conversations.")
```

### Data Validation
```python
# Service layer validation
def submit_section(user: User, conversation: Conversation) -> SubmissionResult:
    if conversation.is_deleted:
        return SubmissionResult(success=False, error="Cannot submit deleted conversation")
    
    if conversation.user != user:
        return SubmissionResult(success=False, error="Permission denied")
```

## 📊 Performance Considerations

### Database Optimization
- Use `select_related()` for foreign key relationships
- Use `prefetch_related()` for reverse foreign keys
- Index frequently queried fields

### Caching Strategy
- Template fragment caching for expensive renders
- Database query caching for repeated operations
- Static file optimization

## 🚀 Deployment & Operations

### Environment Setup
```bash
# Install UV package manager
pip install uv

# Install all dependencies
uv sync

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Database Management
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Populate test data
python manage.py populate_test_database
```

See [DATABASE_POPULATION.md](DATABASE_POPULATION.md) for test data setup.

## 📚 Key Documentation Files

- **[README.md](README.md)** - Project overview and quick start
- **[TESTING.md](TESTING.md)** - Comprehensive testing guide
- **[WORKSPACE_STRUCTURE.md](WORKSPACE_STRUCTURE.md)** - UV workspace organization
- **[SERVICES.md](SERVICES.md)** - Service layer architecture details
- **[VIEWS.md](VIEWS.md)** - View layer patterns and conventions
- **[DESIGN_V2.md](DESIGN_V2.md)** - System design and architecture
- **[DATABASE_POPULATION.md](DATABASE_POPULATION.md)** - Test data setup

## 🐛 Common Issues & Solutions

### Testing Issues
```bash
# If tests fail due to settings
export DJANGO_SETTINGS_MODULE=llteacher.test_settings

# If database issues occur
python manage.py migrate --run-syncdb
```

### Import Issues
```python
# Correct import patterns for workspace structure
from accounts.models import User, Student, Teacher
from conversations.services import ConversationService
from homeworks.models import Homework, Section
```

### Template Issues
```html
<!-- Correct template inheritance -->
{% extends "base.html" %}

<!-- Proper URL reversing -->
{% url 'conversations:detail' conversation_id=conversation.id %}

<!-- CSRF protection -->
{% csrf_token %}
```

## 🔄 Recent Changes & Patterns

### Direct Conversation Submission
Recent implementation of direct conversation submission shows the preferred pattern:

1. **Service Method**: `SubmissionService.submit_section(user, conversation)`
2. **View**: `ConversationSubmitView` handles HTTP concerns
3. **Template**: Form with CSRF protection and confirmation dialog
4. **URL**: RESTful pattern `/conversations/<uuid>/submit/`
5. **Tests**: Comprehensive coverage including permissions, errors, edge cases

### Code Cleanup Patterns
When removing legacy code:

1. **Remove View Classes**: Delete obsolete view classes and dataclasses
2. **Update URLs**: Remove old URL patterns
3. **Delete Templates**: Remove unused template files
4. **Update Tests**: Remove obsolete tests, add new comprehensive tests
5. **Verify**: Run full test suite to ensure nothing breaks

## 💡 Best Practices Summary

1. **Follow the Service Layer Pattern** - Keep business logic in services
2. **Use Typed Data Contracts** - `@dataclass` for all data structures
3. **Write Comprehensive Tests** - Cover happy path, errors, and edge cases
4. **Document Everything** - Clear docstrings and type hints
5. **Security First** - Always check permissions and validate input
6. **Performance Aware** - Use optimized queries and caching
7. **User Experience** - Progressive enhancement and clear error messages
8. **Code Quality** - Follow Django conventions and project patterns

This guide should provide everything needed to work effectively on the LLTeacher codebase while maintaining consistency with established patterns and practices.
