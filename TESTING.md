# Testing Guide for LLTeacher

This document explains how to run tests for the LLTeacher Django application and the different testing configurations available.

## Test Performance

The application includes optimized test settings that provide significant performance improvements:

- **Standard Django tests**: ~21.348 seconds
- **Optimized tests**: ~0.061 seconds
- **Speed improvement**: **350x faster!** 🚀

## Running Tests

### Using UV
```bash
uv run python run_tests.py src 
uv run python manage.py test --settings=src.llteacher.test_settings src 
```

## Test Configuration

### Test Settings (`src/llteacher/test_settings.py`)

The optimized test settings include:

- **In-memory database**: Uses `:memory:` SQLite for isolation and speed
- **Password optimization**: Uses MD5 hasher instead of slower PBKDF2
- **Logging disabled**: Cleaner test output
- **Debug mode off**: Faster test execution
- **Cache disabled**: Uses dummy cache backend
- **Timezone optimization**: Disabled timezone support for tests

### Test Coverage

The application includes **149 comprehensive test cases** covering:

- **Model Creation & Validation**: UUID primary keys, timestamps, field validation
- **Relationships**: Foreign keys, one-to-one relationships, cascade deletes
- **Properties & Methods**: Custom properties, validation methods, soft delete functionality
- **Edge Cases**: Special characters, long content, boundary conditions
- **Database Constraints**: Unique constraints, ordering, table names
- **Model Behavior**: Default values, validation rules, custom save methods

## Test Structure

```
src/
├── accounts/
│   └── tests/
│       └── test_models.py          # User, Teacher, Student tests
├── homeworks/
│   └── tests/
│       └── test_models.py          # Homework, Section, SectionSolution tests
├── conversations/
│   └── tests/
│       └── test_models.py          # Conversation, Message, Submission tests
└── llm/
    └── tests/
        └── test_models.py          # LLMConfig tests
```

## Writing New Tests

### Test File Structure

Each test file should follow this pattern:

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

class ModelNameTest(TestCase):
    """Test cases for ModelName model."""
    
    def setUp(self):
        """Set up test data."""
        # Create test data here
        pass
    
    def test_model_creation(self):
        """Test basic model creation."""
        # Test implementation
        pass
    
    def test_model_validation(self):
        """Test model validation."""
        # Test implementation
        pass
```

### Test Categories

1. **Basic Tests**: Creation, string representation, table names
2. **Field Tests**: UUID primary keys, timestamps, field validation
3. **Relationship Tests**: Foreign keys, one-to-one, cascade deletes
4. **Validation Tests**: Custom validation methods, business logic
5. **Property Tests**: Custom properties and computed fields
6. **Edge Case Tests**: Special characters, long content, boundaries

### Best Practices

- Use descriptive test method names
- Test both positive and negative cases
- Test edge cases and boundary conditions
- Use `setUp()` for common test data
- Test model validation with `full_clean()`
- Test relationships and cascade behaviors
- Use appropriate assertions (`assertEqual`, `assertTrue`, `assertRaises`)

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the app is properly registered in `INSTALLED_APPS`
2. **Database Errors**: Check that migrations are up to date
3. **Permission Errors**: Ensure the test user has appropriate permissions
4. **Validation Errors**: Use `full_clean()` for model validation testing

### Debugging Tests

```bash
# Run with maximum verbosity
python run_tests.py --verbosity=3

# Run a single test method
python run_tests.py accounts.tests.test_models.UserModelTest.test_user_creation

# Run with debugger
python run_tests.py --debug-mode
```

## Continuous Integration

For CI/CD pipelines, use the optimized test settings:

```bash
python manage.py test --settings=src.llteacher.test_settings --verbosity=2
```

This ensures consistent test performance across different environments.

## Performance Tips

1. **Use the convenience script**: `python run_tests.py`
2. **Keep test database**: Use `--keepdb` flag during development
3. **Run specific tests**: Only run tests you're working on
4. **Use in-memory database**: The test settings automatically use this
5. **Disable unnecessary features**: Logging, caching, timezone support are disabled in test settings

## Contributing

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Ensure tests are comprehensive and cover edge cases
3. Test both positive and negative scenarios
4. Use descriptive test method names
5. Add appropriate docstrings
6. Ensure all tests pass before submitting

---

For more information about Django testing, see the [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/).
