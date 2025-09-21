from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from homeworks.models import Homework, Section, SectionSolution
from accounts.models import Teacher
from llm.models import LLMConfig
import uuid
from datetime import timedelta


class HomeworkModelTest(TestCase):
    """Test cases for the Homework model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-4",
            api_key="test-api-key-12345",
            base_prompt="Test prompt",
        )
        self.homework_data = {
            "title": "Test Homework",
            "description": "This is a test homework assignment",
            "created_by": self.teacher,
            "due_date": timezone.now() + timedelta(days=7),
            "llm_config": self.llm_config,
        }

    def test_homework_creation(self):
        """Test basic homework creation."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertEqual(homework.title, "Test Homework")
        self.assertEqual(homework.description, "This is a test homework assignment")
        self.assertEqual(homework.created_by, self.teacher)
        self.assertEqual(homework.llm_config, self.llm_config)
        self.assertIsInstance(homework.id, uuid.UUID)

    def test_homework_uuid_primary_key(self):
        """Test that homework has UUID primary key."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertIsInstance(homework.id, uuid.UUID)

    def test_homework_timestamps(self):
        """Test homework timestamp fields."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertIsNotNone(homework.created_at)
        self.assertIsNotNone(homework.updated_at)
        self.assertIsInstance(homework.created_at, timezone.datetime)
        self.assertIsInstance(homework.updated_at, timezone.datetime)

    def test_homework_str_representation(self):
        """Test homework string representation."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertEqual(str(homework), "Test Homework")

    def test_homework_table_name(self):
        """Test homework table name."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertEqual(homework._meta.db_table, "homeworks_homework")

    def test_homework_ordering(self):
        """Test homework ordering by created_at descending."""
        homework1 = Homework.objects.create(**self.homework_data)
        homework2 = Homework.objects.create(
            title="Test Homework 2",
            description="Second homework",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=14),
        )

        homeworks = list(Homework.objects.all())
        self.assertEqual(homeworks[0], homework2)
        self.assertEqual(homeworks[1], homework1)

    def test_homework_without_llm_config(self):
        """Test homework creation without LLM config."""
        homework_data_no_llm = self.homework_data.copy()
        del homework_data_no_llm["llm_config"]

        homework = Homework.objects.create(**homework_data_no_llm)
        self.assertIsNone(homework.llm_config)

    def test_homework_section_count_property(self):
        """Test homework section_count property."""
        homework = Homework.objects.create(**self.homework_data)
        self.assertEqual(homework.section_count, 0)

        # Create a section
        _section = Section.objects.create(
            homework=homework, title="Test Section", content="Test content", order=1
        )
        self.assertEqual(homework.section_count, 1)

    def test_homework_is_overdue_property(self):
        """Test homework is_overdue property."""
        # Future due date
        future_homework = Homework.objects.create(
            title="Future Homework",
            description="Future homework",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(future_homework.is_overdue)

        # Past due date
        past_homework = Homework.objects.create(
            title="Past Homework",
            description="Past homework",
            created_by=self.teacher,
            due_date=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(past_homework.is_overdue)


class SectionModelTest(TestCase):
    """Test cases for the Section model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section_data = {
            "homework": self.homework,
            "title": "Test Section",
            "content": "This is test section content",
            "order": 1,
        }

    def test_section_creation(self):
        """Test basic section creation."""
        section = Section.objects.create(**self.section_data)
        self.assertEqual(section.homework, self.homework)
        self.assertEqual(section.title, "Test Section")
        self.assertEqual(section.content, "This is test section content")
        self.assertEqual(section.order, 1)
        self.assertIsInstance(section.id, uuid.UUID)

    def test_section_uuid_primary_key(self):
        """Test that section has UUID primary key."""
        section = Section.objects.create(**self.section_data)
        self.assertIsInstance(section.id, uuid.UUID)

    def test_section_timestamps(self):
        """Test section timestamp fields."""
        section = Section.objects.create(**self.section_data)
        self.assertIsNotNone(section.created_at)
        self.assertIsNotNone(section.updated_at)
        self.assertIsInstance(section.created_at, timezone.datetime)
        self.assertIsInstance(section.updated_at, timezone.datetime)

    def test_section_str_representation(self):
        """Test section string representation."""
        section = Section.objects.create(**self.section_data)
        expected_str = (
            f"{self.homework.title} - Section {section.order}: {section.title}"
        )
        self.assertEqual(str(section), expected_str)

    def test_section_table_name(self):
        """Test section table name."""
        section = Section.objects.create(**self.section_data)
        self.assertEqual(section._meta.db_table, "homeworks_section")

    def test_section_ordering(self):
        """Test section ordering by order field."""
        section1 = Section.objects.create(
            homework=self.homework, title="Section 1", content="Content 1", order=1
        )
        section2 = Section.objects.create(
            homework=self.homework, title="Section 2", content="Content 2", order=2
        )

        sections = list(Section.objects.all())
        self.assertEqual(sections[0], section1)
        self.assertEqual(sections[1], section2)

    def test_section_without_solution(self):
        """Test section creation without solution."""
        section = Section.objects.create(**self.section_data)
        self.assertIsNone(section.solution)

    def test_section_with_solution(self):
        """Test section with solution."""
        solution = SectionSolution.objects.create(content="This is the solution")
        section = Section.objects.create(**self.section_data, solution=solution)
        self.assertEqual(section.solution, solution)
        self.assertEqual(solution.section, section)


class SectionValidationTest(TestCase):
    """Test cases for section validation."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

    def test_section_order_min_value(self):
        """Test section order minimum value validation."""
        section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )
        self.assertEqual(section.order, 1)

    def test_section_order_max_value(self):
        """Test section order maximum value validation."""
        section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=20,
        )
        self.assertEqual(section.order, 20)

    def test_section_order_below_minimum(self):
        """Test section order below minimum raises error."""
        with self.assertRaises(ValidationError):
            section = Section(
                homework=self.homework,
                title="Test Section",
                content="Test content",
                order=0,
            )
            section.full_clean()

    def test_section_order_above_maximum(self):
        """Test section order above maximum raises error."""
        with self.assertRaises(ValidationError):
            section = Section(
                homework=self.homework,
                title="Test Section",
                content="Test content",
                order=21,
            )
            section.full_clean()

    def test_section_order_uniqueness(self):
        """Test section order uniqueness within homework."""
        Section.objects.create(
            homework=self.homework, title="Section 1", content="Content 1", order=1
        )

        # Should raise error for duplicate order
        with self.assertRaises(Exception):
            Section.objects.create(
                homework=self.homework, title="Section 2", content="Content 2", order=1
            )

    def test_section_order_different_homeworks(self):
        """Test section order can be same in different homeworks."""
        homework2 = Homework.objects.create(
            title="Test Homework 2",
            description="Test Description 2",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=14),
        )

        section1 = Section.objects.create(
            homework=self.homework, title="Section 1", content="Content 1", order=1
        )

        section2 = Section.objects.create(
            homework=homework2, title="Section 1", content="Content 1", order=1
        )

        self.assertEqual(section1.order, 1)
        self.assertEqual(section2.order, 1)

    def test_section_clean_method(self):
        """Test section clean method validation."""
        section = Section(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=25,  # Above maximum
        )

        with self.assertRaises(ValidationError):
            section.clean()


class SectionSolutionModelTest(TestCase):
    """Test cases for the SectionSolution model."""

    def setUp(self):
        self.solution_data = {"content": "This is the solution to the problem"}

    def test_solution_creation(self):
        """Test basic solution creation."""
        solution = SectionSolution.objects.create(**self.solution_data)
        self.assertEqual(solution.content, "This is the solution to the problem")
        self.assertIsInstance(solution.id, uuid.UUID)

    def test_solution_uuid_primary_key(self):
        """Test that solution has UUID primary key."""
        solution = SectionSolution.objects.create(**self.solution_data)
        self.assertIsInstance(solution.id, uuid.UUID)

    def test_solution_timestamps(self):
        """Test solution timestamp fields."""
        solution = SectionSolution.objects.create(**self.solution_data)
        self.assertIsNotNone(solution.created_at)
        self.assertIsNotNone(solution.updated_at)
        self.assertIsInstance(solution.created_at, timezone.datetime)
        self.assertIsInstance(solution.updated_at, timezone.datetime)

    def test_solution_str_representation(self):
        """Test solution string representation."""
        solution = SectionSolution.objects.create(**self.solution_data)
        # The solution doesn't have a section relationship, so it should show the ID
        self.assertTrue(str(solution).startswith("Solution "))

    def test_solution_table_name(self):
        """Test solution table name."""
        solution = SectionSolution.objects.create(**self.solution_data)
        self.assertEqual(solution._meta.db_table, "homeworks_section_solution")

    def test_solution_with_empty_content(self):
        """Test solution with empty content."""
        solution = SectionSolution.objects.create(content="")
        self.assertEqual(solution.content, "")

    def test_solution_with_long_content(self):
        """Test solution with very long content."""
        long_content = "A" * 10000
        solution = SectionSolution.objects.create(content=long_content)
        self.assertEqual(solution.content, long_content)


class HomeworkSectionRelationshipTest(TestCase):
    """Test cases for homework-section relationships."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

    def test_homework_has_sections(self):
        """Test that homework can have multiple sections."""
        section1 = Section.objects.create(
            homework=self.homework, title="Section 1", content="Content 1", order=1
        )
        section2 = Section.objects.create(
            homework=self.homework, title="Section 2", content="Content 2", order=2
        )

        sections = list(self.homework.sections.all())
        self.assertEqual(len(sections), 2)
        self.assertIn(section1, sections)
        self.assertIn(section2, sections)

    def test_section_belongs_to_homework(self):
        """Test that section belongs to homework."""
        section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )
        self.assertEqual(section.homework, self.homework)

    def test_homework_cascade_delete_sections(self):
        """Test that sections are deleted when homework is deleted."""
        section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )
        section_id = section.id

        self.homework.delete()
        self.assertFalse(Section.objects.filter(id=section_id).exists())

    def test_section_cascade_delete_solution(self):
        """Test that solution is not deleted when section is deleted (SET_NULL relationship)."""
        solution = SectionSolution.objects.create(content="Test solution")
        section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
            solution=solution,
        )
        solution_id = solution.id

        section.delete()
        # The solution should still exist because the relationship is SET_NULL
        self.assertTrue(SectionSolution.objects.filter(id=solution_id).exists())


class ModelEdgeCasesTest(TestCase):
    """Test cases for model edge cases."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)

    def test_homework_with_very_long_title(self):
        """Test homework with very long title."""
        long_title = "A" * 200
        homework = Homework.objects.create(
            title=long_title,
            description="Test description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(homework.title, long_title)

    def test_homework_with_very_long_description(self):
        """Test homework with very long description."""
        long_description = "A" * 10000
        homework = Homework.objects.create(
            title="Test Homework",
            description=long_description,
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(homework.description, long_description)

    def test_section_with_very_long_title(self):
        """Test section with very long title."""
        homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        long_title = "A" * 200
        section = Section.objects.create(
            homework=homework, title=long_title, content="Test content", order=1
        )
        self.assertEqual(section.title, long_title)

    def test_section_with_very_long_content(self):
        """Test section with very long content."""
        homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        long_content = "A" * 10000
        section = Section.objects.create(
            homework=homework, title="Test Section", content=long_content, order=1
        )
        self.assertEqual(section.content, long_content)

    def test_solution_with_very_long_content(self):
        """Test solution with very long content."""
        long_content = "A" * 10000
        solution = SectionSolution.objects.create(content=long_content)
        self.assertEqual(solution.content, long_content)

    def test_homework_with_special_characters(self):
        """Test homework with special characters."""
        special_title = "Homework with @#$%^&*() characters"
        homework = Homework.objects.create(
            title=special_title,
            description="Test description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(homework.title, special_title)

    def test_section_with_special_characters(self):
        """Test section with special characters."""
        homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        special_title = "Section with @#$%^&*() characters"
        section = Section.objects.create(
            homework=homework, title=special_title, content="Test content", order=1
        )
        self.assertEqual(section.title, special_title)
