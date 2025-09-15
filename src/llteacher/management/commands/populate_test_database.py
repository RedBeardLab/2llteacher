from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from accounts.models import Teacher, Student
from llm.models import LLMConfig
from homeworks.models import Homework, Section, SectionSolution
from conversations.models import Conversation, Message, Submission

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with comprehensive test data for manual testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all existing test data before creating new data',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting database...')
            self.reset_database()

        self.stdout.write('Creating comprehensive test data...')
        
        with transaction.atomic():
            # Create users and profiles
            users = self.create_users()
            
            # Create LLM configuration
            llm_config = self.create_llm_config()
            
            # Create homeworks with sections
            homeworks = self.create_homeworks(users['teachers'], llm_config)
            
            # Create conversations and messages
            self.create_conversations_and_messages(users['students'], homeworks)

        self.print_summary()

    def reset_database(self):
        """Reset all test data."""
        # Delete in reverse dependency order
        Submission.objects.all().delete()
        Message.objects.all().delete()
        Conversation.objects.all().delete()
        SectionSolution.objects.all().delete()
        Section.objects.all().delete()
        Homework.objects.all().delete()
        LLMConfig.objects.all().delete()
        Teacher.objects.all().delete()
        Student.objects.all().delete()
        User.objects.filter(username__in=[
            'teacher1', 'teacher2', 'student1', 'student2', 'student3'
        ]).delete()
        self.stdout.write('  ✓ Database reset complete')

    def create_users(self):
        """Create test users and profiles."""
        self.stdout.write('Creating users and profiles...')
        
        # Teachers
        teacher1_user = User.objects.create_user(
            username='teacher1',
            email='teacher1@test.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        teacher1 = Teacher.objects.create(user=teacher1_user)
        
        teacher2_user = User.objects.create_user(
            username='teacher2',
            email='teacher2@test.com',
            first_name='Jane',
            last_name='Smith',
            password='testpass123'
        )
        teacher2 = Teacher.objects.create(user=teacher2_user)
        
        # Students
        student1_user = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            first_name='Alice',
            last_name='Johnson',
            password='testpass123'
        )
        student1 = Student.objects.create(user=student1_user)
        
        student2_user = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            first_name='Bob',
            last_name='Wilson',
            password='testpass123'
        )
        student2 = Student.objects.create(user=student2_user)
        
        student3_user = User.objects.create_user(
            username='student3',
            email='student3@test.com',
            first_name='Carol',
            last_name='Brown',
            password='testpass123'
        )
        student3 = Student.objects.create(user=student3_user)
        
        self.stdout.write('  ✓ Created 2 teachers and 3 students')
        
        return {
            'teachers': [teacher1, teacher2],
            'students': [student1, student2, student3]
        }

    def create_llm_config(self):
        """Create LLM configuration for testing."""
        self.stdout.write('Creating LLM configuration...')
        
        llm_config = LLMConfig.objects.create(
            name='Test GPT-4 Config',
            model_name='gpt-4',
            api_key='test-api-key-placeholder',
            base_prompt='''You are an AI tutor helping students learn programming.

Be encouraging, ask guiding questions, and help students discover solutions rather than giving direct answers.

Students don't like long answers and to read too much.

But we cannot allow any misconduct - so if you know the answer to a question or to a point of a question you should never offer it. Not even if asked by the student.

Be patient and supportive.

Never give the correct answer directly. Never give to students a direct answer.

For instance, if you were asked help in crating a list of at least 5 tests scores in python and the student ask how to create a list, then you DO NOT answer with:

```
test_scores = [98, 85, 78, 90, 94, 85]
```

But with something generic of lists. Like

```
list_name = [1, 2, 3]
```

And explain the syntaz and how to add values.''',
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=True,
            is_active=True
        )
        
        self.stdout.write('  ✓ Created LLM configuration')
        return llm_config

    def create_homeworks(self, teachers, llm_config):
        """Create sample homeworks with sections."""
        self.stdout.write('Creating homeworks and sections...')
        
        homeworks = []
        
        # Homework 1 by Teacher 1
        hw1 = Homework.objects.create(
            title='Python Basics',
            description='Introduction to Python programming fundamentals including variables, data types, and control structures.',
            created_by=teachers[0],
            due_date=timezone.now() + timedelta(days=7),
            llm_config=llm_config
        )
        
        # Sections for Homework 1
        section1_1 = Section.objects.create(
            homework=hw1,
            title='Variables and Data Types',
            content='''# Variables and Data Types

Write a Python program that demonstrates the use of different data types:

1. Create variables of type int, float, string, and boolean
2. Print each variable with its type using the type() function
3. Perform basic operations with these variables

Example output:
```
Number: 42, Type: <class 'int'>
Price: 19.99, Type: <class 'float'>
Name: Alice, Type: <class 'str'>
Is student: True, Type: <class 'bool'>
```''',
            order=1
        )
        
        solution1_1 = SectionSolution.objects.create(
            content='''# Solution: Variables and Data Types

# Create variables of different types
number = 42
price = 19.99
name = "Alice"
is_student = True

# Print each variable with its type
print(f"Number: {number}, Type: {type(number)}")
print(f"Price: {price}, Type: {type(price)}")
print(f"Name: {name}, Type: {type(name)}")
print(f"Is student: {is_student}, Type: {type(is_student)}")

# Basic operations
total = number + price
greeting = f"Hello, {name}!"
print(f"Total: {total}")
print(greeting)'''
        )
        section1_1.solution = solution1_1
        section1_1.save()
        
        section1_2 = Section.objects.create(
            homework=hw1,
            title='Control Structures',
            content='''# Control Structures

Write a Python program that uses if-else statements and loops:

1. Ask the user for their age
2. Use if-else to determine if they can vote (18+)
3. Use a for loop to print numbers 1 to 10
4. Use a while loop to count down from 5 to 1

Make sure to handle user input appropriately.''',
            order=2
        )
        
        solution1_2 = SectionSolution.objects.create(
            content='''# Solution: Control Structures

# Get user age
age = int(input("Enter your age: "))

# Check voting eligibility
if age >= 18:
    print("You can vote!")
else:
    print(f"You can vote in {18 - age} years.")

# For loop: numbers 1 to 10
print("Numbers 1 to 10:")
for i in range(1, 11):
    print(i, end=" ")
print()

# While loop: countdown
print("Countdown:")
count = 5
while count > 0:
    print(count)
    count -= 1
print("Blast off!")'''
        )
        section1_2.solution = solution1_2
        section1_2.save()
        
        section1_3 = Section.objects.create(
            homework=hw1,
            title='Functions and Lists',
            content='''# Functions and Lists

Create a Python program with the following requirements:

1. Define a function called `calculate_average` that takes a list of numbers and returns the average
2. Create a list of at least 5 test scores
3. Use your function to calculate the average score
4. Print whether the average is above or below 70 (passing grade)

Bonus: Add error handling for empty lists.''',
            order=3
        )
        
        solution1_3 = SectionSolution.objects.create(
            content='''# Solution: Functions and Lists

def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    if not numbers:  # Handle empty list
        return 0
    return sum(numbers) / len(numbers)

# Test scores
test_scores = [85, 92, 78, 88, 95]

# Calculate average
average = calculate_average(test_scores)

# Print results
print(f"Test scores: {test_scores}")
print(f"Average score: {average:.2f}")

if average >= 70:
    print("Passing grade! Well done!")
else:
    print("Below passing grade. Keep studying!")'''
        )
        section1_3.solution = solution1_3
        section1_3.save()
        
        homeworks.append(hw1)
        
        # Homework 2 by Teacher 2
        hw2 = Homework.objects.create(
            title='Data Analysis with Python',
            description='Learn to analyze data using Python lists and dictionaries. Practice with real-world data scenarios.',
            created_by=teachers[1],
            due_date=timezone.now() + timedelta(days=10),
            llm_config=llm_config
        )
        
        # Sections for Homework 2
        section2_1 = Section.objects.create(
            homework=hw2,
            title='Working with Dictionaries',
            content='''# Working with Dictionaries

Create a student grade management system:

1. Create a dictionary to store student names as keys and their grades as values
2. Add at least 5 students with their grades
3. Calculate and print the class average
4. Find and print the highest and lowest grades
5. Allow adding a new student grade

Example structure:
```python
students = {"Alice": 85, "Bob": 92, "Carol": 78}
```''',
            order=1
        )
        
        solution2_1 = SectionSolution.objects.create(
            content='''# Solution: Working with Dictionaries

# Student grades dictionary
students = {
    "Alice": 85,
    "Bob": 92,
    "Carol": 78,
    "David": 88,
    "Emma": 95
}

# Calculate class average
total_grades = sum(students.values())
class_average = total_grades / len(students)

# Find highest and lowest grades
highest_grade = max(students.values())
lowest_grade = min(students.values())

# Find students with highest and lowest grades
top_student = [name for name, grade in students.items() if grade == highest_grade][0]
lowest_student = [name for name, grade in students.items() if grade == lowest_grade][0]

# Print results
print(f"Class average: {class_average:.2f}")
print(f"Highest grade: {highest_grade} ({top_student})")
print(f"Lowest grade: {lowest_grade} ({lowest_student})")

# Add new student
students["Frank"] = 89
print(f"Added Frank with grade 89. New class size: {len(students)}")'''
        )
        section2_1.solution = solution2_1
        section2_1.save()
        
        section2_2 = Section.objects.create(
            homework=hw2,
            title='List Comprehensions and Filtering',
            content='''# List Comprehensions and Filtering

Work with a list of product data:

1. Create a list of dictionaries representing products (name, price, category)
2. Use list comprehension to find all products under $50
3. Filter products by category
4. Calculate total value of all products
5. Find the most expensive product in each category

Example product:
```python
{"name": "Laptop", "price": 999.99, "category": "Electronics"}
```''',
            order=2
        )
        
        solution2_2 = SectionSolution.objects.create(
            content='''# Solution: List Comprehensions and Filtering

# Product data
products = [
    {"name": "Laptop", "price": 999.99, "category": "Electronics"},
    {"name": "Book", "price": 15.99, "category": "Education"},
    {"name": "Headphones", "price": 79.99, "category": "Electronics"},
    {"name": "Notebook", "price": 5.99, "category": "Education"},
    {"name": "Mouse", "price": 25.99, "category": "Electronics"},
    {"name": "Pen", "price": 2.99, "category": "Education"}
]

# Products under $50
cheap_products = [p for p in products if p["price"] < 50]
print("Products under $50:")
for product in cheap_products:
    print(f"  {product['name']}: ${product['price']}")

# Filter by category
electronics = [p for p in products if p["category"] == "Electronics"]
print(f"\\nElectronics products: {len(electronics)}")

# Total value
total_value = sum(p["price"] for p in products)
print(f"Total inventory value: ${total_value:.2f}")

# Most expensive in each category
categories = set(p["category"] for p in products)
for category in categories:
    category_products = [p for p in products if p["category"] == category]
    most_expensive = max(category_products, key=lambda x: x["price"])
    print(f"Most expensive {category}: {most_expensive['name']} (${most_expensive['price']})") '''
        )
        section2_2.solution = solution2_2
        section2_2.save()
        
        homeworks.append(hw2)
        
        self.stdout.write(f'  ✓ Created {len(homeworks)} homeworks with sections and solutions')
        return homeworks

    def create_conversations_and_messages(self, students, homeworks):
        """Create sample conversations and messages."""
        self.stdout.write('Creating conversations and messages...')
        
        conversation_count = 0
        message_count = 0
        submission_count = 0
        
        # Sample conversation templates
        conversation_templates = [
            {
                'student_messages': [
                    "I'm having trouble understanding how to create variables in Python. Can you help?",
                    "I tried creating a variable like this: my_variable = 42, but I'm not sure if that's correct.",
                    "Thank you! That makes sense. How do I check what type a variable is?"
                ],
                'ai_responses': [
                    "I'd be happy to help you with Python variables! Variables are like containers that store data. You're on the right track. Can you tell me what specific part is confusing you?",
                    "That's exactly right! `my_variable = 42` is perfect syntax for creating a variable. The variable name is on the left, the equals sign assigns the value, and 42 is the value being stored. What would you like to try next?",
                    "Great question! You can use the `type()` function. Try this: `print(type(my_variable))`. This will show you that 42 is an integer. Want to try creating variables with different data types?"
                ]
            },
            {
                'student_messages': [
                    "I'm confused about if-else statements. When do I use them?",
                    "So if I want to check if someone can vote, I would write: if age >= 18: print('Can vote')?",
                    "What about checking multiple conditions?"
                ],
                'ai_responses': [
                    "If-else statements are used when you want your program to make decisions! They let you execute different code based on whether a condition is true or false. What kind of decision do you want your program to make?",
                    "Exactly! That's perfect syntax. Don't forget you can add an else clause: `else: print('Cannot vote yet')`. This handles the case when the condition is false. Try writing the complete if-else block!",
                    "For multiple conditions, you can use `elif` (else if). For example: `if age >= 65: print('Senior')` then `elif age >= 18: print('Adult')` then `else: print('Minor')`. Each condition is checked in order!"
                ]
            },
            {
                'student_messages': [
                    "How do I work with lists in Python? I need to store multiple grades.",
                    "I created grades = [85, 90, 78] but how do I add more grades?",
                    "Perfect! How do I calculate the average of all grades in the list?"
                ],
                'ai_responses': [
                    "Lists are perfect for storing multiple items like grades! You create them with square brackets: `grades = [85, 90, 78]`. What operations do you want to perform with your grades?",
                    "Great start! To add more grades, you can use `grades.append(92)` to add one grade, or `grades.extend([88, 95])` to add multiple grades at once. Try adding a few more grades to your list!",
                    "To calculate the average, you can use: `average = sum(grades) / len(grades)`. The `sum()` function adds all numbers in the list, and `len()` gives you how many items are in the list. Try it out!"
                ]
            }
        ]
        
        # Create conversations for each student on various sections
        for student in students:
            # Each student has conversations on 2-3 sections
            sections_to_work_on = []
            for homework in homeworks:
                sections_to_work_on.extend(list(homework.sections.all())[:2])  # First 2 sections of each homework
            
            for i, section in enumerate(sections_to_work_on[:3]):  # Limit to 3 conversations per student
                conversation = Conversation.objects.create(
                    user=student.user,
                    section=section
                )
                conversation_count += 1
                
                # Use conversation template
                template = conversation_templates[i % len(conversation_templates)]
                
                # Create alternating messages
                for j in range(min(len(template['student_messages']), len(template['ai_responses']))):
                    # Student message
                    Message.objects.create(
                        conversation=conversation,
                        content=template['student_messages'][j],
                        message_type='student'
                    )
                    message_count += 1
                    
                    # AI response
                    Message.objects.create(
                        conversation=conversation,
                        content=template['ai_responses'][j],
                        message_type='ai'
                    )
                    message_count += 1
                
                # 60% chance of having a submission
                if i % 5 < 3:  # Creates submissions for 3 out of 5 conversations
                    Submission.objects.create(conversation=conversation)
                    submission_count += 1
        
        self.stdout.write(f'  ✓ Created {conversation_count} conversations with {message_count} messages')
        self.stdout.write(f'  ✓ Created {submission_count} submissions')

    def print_summary(self):
        """Print summary of created data."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('DATABASE POPULATION COMPLETE!')
        self.stdout.write('='*60)
        
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Teachers: {Teacher.objects.count()}')
        self.stdout.write(f'Students: {Student.objects.count()}')
        self.stdout.write(f'LLM Configs: {LLMConfig.objects.count()}')
        self.stdout.write(f'Homeworks: {Homework.objects.count()}')
        self.stdout.write(f'Sections: {Section.objects.count()}')
        self.stdout.write(f'Section Solutions: {SectionSolution.objects.count()}')
        self.stdout.write(f'Conversations: {Conversation.objects.count()}')
        self.stdout.write(f'Messages: {Message.objects.count()}')
        self.stdout.write(f'Submissions: {Submission.objects.count()}')
        
        self.stdout.write('\nTEST CREDENTIALS:')
        self.stdout.write('All users have password: testpass123')
        self.stdout.write('\nTeachers: teacher1, teacher2')
        self.stdout.write('Students: student1, student2, student3')
        
        self.stdout.write('\nYour database is now ready for manual testing!')
        self.stdout.write('='*60)
