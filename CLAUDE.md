# LLTeacher v2 Project Guide

This document contains key information about the LLTeacher v2 project to help with development.

## Project Structure

- Django project with multiple apps following a testable-first architecture
- Each view has its own dataclass for structured data passing to templates
- Permissions are handled through decorators and mixins

## Running Tests

Use the canonical test command with uv:

```bash
uv run coverage run manage.py test --settings=src.llteacher.test_settings src
```

Example:
```bash
uv run coverage run manage.py test --settings=src.llteacher.test_settings src
```

The test command uses the test settings module located at `src.llteacher.test_settings`, which provides optimized test settings including an in-memory database for faster tests.

To run the code in testing mode we can use `--settings=src.llteacher.settings` instead.

## Missing Views to Implement

### Homeworks App

1. ✅ SectionDetailView - For viewing individual sections with their conversations
2. HomeworkEditView - For editing existing homework assignments (similar to CreateView but with existing data)

### Accounts App

1. UserRegistrationView - For user registration (teacher/student)
2. UserLoginView - For user authentication
3. ProfileManagementView - For viewing/editing user profiles

### Conversations App

1. ConversationStartView - For starting a new conversation on a section
2. ConversationDetailView - For viewing an existing conversation
3. MessageSendView - For sending messages in a conversation
4. SectionSubmitView - For submitting completed sections

### LLM App

1. LLMConfigListView - For listing available LLM configurations
2. LLMConfigCreateView - For creating new LLM configurations
3. LLMConfigEditView - For editing existing LLM configurations

## Implementation Workflow

1. Create tests for the view
2. Implement the view
3. Add URL pattern
4. Create template
5. Run tests
6. Commit changes

## Important Decorators

- `@login_required` - Basic authentication
- `@teacher_required` - Restricts to teacher users
- `@student_required` - Restricts to student users
- `@homework_owner_required` - Ensures teacher owns the homework
- `@section_access_required` - Checks section access permissions
- `@conversation_access_required` - Checks conversation access permissions
- `@submission_access_required` - Checks submission access permissions

## Implementation Progress

- ✅ SectionDetailView (Homeworks app)
