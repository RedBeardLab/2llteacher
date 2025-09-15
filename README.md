# LLTeacher v2

AI-assisted educational platform for teachers and students.

## 🚀 Project Status

**Phase 1 Complete**: Data Models & Testing Infrastructure ✅

- ✅ **Models**: All Django models implemented according to design specifications
- ✅ **Testing**: 149 comprehensive test cases with 350x performance optimization
- ✅ **Architecture**: Clean, modular structure with proper separation of concerns
- ✅ **Documentation**: Comprehensive testing guide and setup instructions

**Next Phase**: Service Layer & API Development 🔄

## Project Structure

This project uses [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) for dependency management.

### Workspace Members

- **`apps/accounts`** - User management and authentication
- **`apps/conversations`** - AI conversation handling and submissions
- **`apps/homeworks`** - Homework and section management
- **`apps/llm`** - LLM configuration and services
- **`core`** - Shared utilities and base classes
- **`permissions`** - Permission decorators and utilities
- **`services`** - Business logic service layer
- **`src/llteacher`** - Main Django project

## Setup

1. Install uv: `pip install uv`
2. Install dependencies: `uv sync`
3. Run migrations: `python manage.py migrate`
4. Create superuser: `python manage.py createsuperuser`
5. **Configure API Key** (see Configuration section below)
6. Populate test data: `python manage.py populate_test_database`
7. Run development server: `python manage.py runserver`

## Configuration

### API Key Setup

The AI tutoring functionality requires an OpenAI API key. You have two options:

#### Option 1: Through Admin Interface (Recommended)

1. Start the development server: `python manage.py runserver`
2. Go to the admin interface: `http://localhost:8000/admin/`
3. Navigate to **LLM > LLM Configs**
4. Edit the "Test GPT-4 Config" entry
5. Replace `test-api-key-placeholder` with your actual OpenAI API key
6. Save the configuration

#### Option 2: Update Test Database Population

If you want to set the API key during initial setup:

1. Edit `src/llteacher/management/commands/populate_test_database.py`
2. Find the line with `api_key='test-api-key-placeholder'`
3. Replace the placeholder with your actual OpenAI API key
4. Run: `python manage.py populate_test_database --reset`

### Getting an OpenAI API Key

1. Go to [OpenAI's website](https://platform.openai.com/)
2. Sign up or log in to your account
3. Navigate to the API section
4. Generate a new API key
5. Copy the key (it starts with `sk-`)

### Testing Your Configuration

1. Go to the admin interface: `http://localhost:8000/admin/`
2. Navigate to **LLM > LLM Configs**
3. Click on your configuration
4. Use the "Test Configuration" feature (if available)
5. Or create a conversation as a student to test the AI responses

### Important Notes

- **Never commit real API keys to version control**
- The test database includes a placeholder API key that won't work
- You must replace it with a real key for AI functionality to work
- API keys should be kept secure and not shared

### Troubleshooting

**"No valid LLM configuration available"**
- Check that you have a default LLM config marked as active
- Verify your API key is correctly set (not the placeholder)

**"Technical issue" errors in conversations**
- Check the Django logs for specific API errors
- Verify your OpenAI API key has sufficient credits
- Ensure the API key has the correct permissions

**AI responses not generating**
- Confirm the LLM config is set as default (`is_default=True`)
- Check that the configuration is active (`is_active=True`)
- Verify the model name (e.g., 'gpt-4', 'gpt-3.5-turbo') is correct

## Development

- Each app is a separate workspace member with its own `pyproject.toml`
- Use `uv add <package>` to add dependencies to specific workspaces
- Use `uv sync` to install all workspace dependencies

## Testing

The project includes comprehensive testing with **149 test cases** covering all models and their functionality.

### Quick Start

```bash
# Run all tests (fastest - uses in-memory database)
uv run python run_tests.py

# Run with verbose output
uv run python run_tests.py --verbosity=2

# Run specific app tests
uv run python run_tests.py apps.accounts.tests
```

### Performance

- **Standard Django tests**: ~21.348 seconds
- **Optimized tests**: ~0.061 seconds
- **Speed improvement**: **350x faster!** 🚀

### Test Coverage

- ✅ **Models**: Complete coverage of all Django models
- ✅ **Relationships**: Foreign keys, one-to-one, cascade deletes
- ✅ **Validation**: Custom validation methods and business logic
- ✅ **Edge Cases**: Special characters, long content, boundaries
- ✅ **Properties**: Custom properties and computed fields

For detailed testing information, see [TESTING.md](TESTING.md).
