# Database Population for Manual Testing

This document describes the comprehensive database population system for creating realistic test data for manual testing of the Django application.

## Overview

The `populate_test_database` management command creates a complete, interconnected dataset that includes:
- Users (teachers and students) with proper authentication
- LLM configuration for AI functionality
- Homeworks with multiple sections and solutions
- Realistic conversations between students and AI
- Message exchanges and submissions

## Usage

### Basic Population
```bash
python manage.py populate_test_database
```

### Reset and Repopulate
```bash
python manage.py populate_test_database --reset
```

## What Gets Created

### Users & Authentication
- **2 Teachers**: teacher1 (John Doe), teacher2 (Jane Smith)
- **3 Students**: student1 (Alice Johnson), student2 (Bob Wilson), student3 (Carol Brown)
- **Password**: All users have password `testpass123`
- **Profiles**: Proper Teacher/Student profiles are created automatically

### LLM Configuration
- **Test GPT-4 Config**: Mock LLM configuration for testing AI features
- **Safe API Key**: Uses placeholder key for testing without real API calls
- **Tutor Prompt**: Configured with educational AI tutor personality

### Homeworks & Content
- **Python Basics** (by teacher1): 3 sections covering variables, control structures, and functions
- **Data Analysis with Python** (by teacher2): 2 sections on dictionaries and list comprehensions
- **Complete Solutions**: Each section includes detailed solution code
- **Due Dates**: Realistic future due dates for testing

### Conversations & Messages
- **9 Conversations**: Each student has conversations on multiple sections
- **54 Messages**: Realistic back-and-forth between students and AI
- **9 Submissions**: 60% of conversations include student submissions
- **Message Types**: Proper student/AI message type classification

## Data Relationships

The population follows proper dependency order:
1. **Users & Profiles** → Foundation for all other data
2. **LLM Configuration** → Required for homework creation
3. **Homeworks & Sections** → Content structure with solutions
4. **Conversations & Messages** → Student interactions with content

## Sample Content

### Homework Topics
- **Variables and Data Types**: Basic Python data types and operations
- **Control Structures**: If-else statements and loops
- **Functions and Lists**: Function definition and list operations
- **Working with Dictionaries**: Grade management system
- **List Comprehensions**: Product data filtering and analysis

### Conversation Examples
- Variable creation and type checking
- If-else statement usage and multiple conditions
- List operations and average calculations
- Realistic student questions and AI tutor responses

## Testing Scenarios

This populated database enables testing of:

### Authentication & User Management
- Login with different user types (teacher/student)
- Role-based access control
- User profile functionality

### Homework Management
- Homework creation and editing (teachers)
- Section viewing and navigation (students)
- Solution access (teachers)
- Due date handling

### Conversation System
- Starting new conversations on sections
- Message sending and receiving
- AI response simulation
- Conversation history

### Submission Workflow
- Student submission creation
- Submission tracking and status
- Teacher review capabilities

## Command Options

### `--reset`
Safely deletes all test data before creating new data:
- Removes in proper dependency order to avoid foreign key conflicts
- Only affects test users and related data
- Preserves any production data with different usernames

## File Structure

```
src/llteacher/management/commands/
└── populate_test_database.py     # Comprehensive database population

src/accounts/management/commands/
└── create_test_users.py          # Simple user creation (legacy)
```

## Safety Features

- **Transaction Safety**: All creation happens in a single database transaction
- **Idempotent Design**: Can be run multiple times safely with `--reset`
- **Error Handling**: Graceful handling of creation errors with clear output
- **Test Data Isolation**: Only affects designated test usernames

## Extending the System

To add more test data:

1. **More Users**: Add entries to the user creation lists
2. **Additional Homeworks**: Extend the homework creation section
3. **More Conversations**: Add conversation templates or increase per-student conversations
4. **Different Content**: Modify homework topics and section content

## Integration with Testing

This populated database works seamlessly with:
- **Manual UI Testing**: Complete data for clicking through all features
- **API Testing**: Realistic data for endpoint testing
- **Integration Testing**: Full workflow testing with proper relationships
- **Performance Testing**: Sufficient data volume for basic performance checks

## Summary Statistics

After population, the database contains:
- **6 Users** (5 test + 1 superuser if created)
- **2 Teachers** with proper profiles
- **3 Students** with proper profiles
- **1 LLM Configuration** ready for testing
- **2 Homeworks** with realistic content
- **5 Sections** with complete solutions
- **9 Conversations** across different topics
- **54 Messages** with realistic exchanges
- **9 Submissions** for workflow testing

This provides a comprehensive foundation for thorough manual testing of all application features.
