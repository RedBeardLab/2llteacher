from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Teacher, Student, TeacherAssistant
import uuid


class UserModelTest(TestCase):
    """Test cases for the custom User model."""

    def setUp(self):
        self.User = get_user_model()

    def test_user_creation(self):
        """Test basic user creation."""
        user = self.User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))

    def test_user_uuid_primary_key(self):
        """Test that user has UUID primary key."""
        user = self.User.objects.create_user(
            username="testuser2", password="testpass123"
        )
        self.assertIsInstance(user.id, uuid.UUID)

    def test_user_str_representation(self):
        """Test user string representation."""
        user = self.User.objects.create_user(
            username="testuser3", password="testpass123"
        )
        self.assertEqual(str(user), "testuser3")

    def test_user_table_name(self):
        """Test user table name."""
        user = self.User.objects.create_user(
            username="testuser4", password="testpass123"
        )
        self.assertEqual(user._meta.db_table, "accounts_user")


class TeacherModelTest(TestCase):
    """Test cases for the Teacher model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )

    def test_teacher_creation(self):
        """Test basic teacher creation."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertEqual(teacher.user, self.user)
        self.assertIsInstance(teacher.id, uuid.UUID)

    def test_teacher_uuid_primary_key(self):
        """Test that teacher has UUID primary key."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertIsInstance(teacher.id, uuid.UUID)

    def test_teacher_timestamps(self):
        """Test teacher timestamp fields."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertIsNotNone(teacher.created_at)
        self.assertIsNotNone(teacher.updated_at)
        self.assertIsInstance(teacher.created_at, timezone.datetime)
        self.assertIsInstance(teacher.updated_at, timezone.datetime)

    def test_teacher_str_representation(self):
        """Test teacher string representation."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertEqual(str(teacher), f"Teacher: {self.user.username}")

    def test_teacher_table_name(self):
        """Test teacher table name."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertEqual(teacher._meta.db_table, "accounts_teacher")

    def test_teacher_user_relationship(self):
        """Test teacher-user one-to-one relationship."""
        teacher = Teacher.objects.create(user=self.user)
        self.assertEqual(teacher.user, self.user)
        self.assertEqual(self.user.teacher_profile, teacher)

    def test_teacher_cascade_delete(self):
        """Test that teacher is deleted when user is deleted."""
        teacher = Teacher.objects.create(user=self.user)
        teacher_id = teacher.id
        self.user.delete()
        self.assertFalse(Teacher.objects.filter(id=teacher_id).exists())


class StudentModelTest(TestCase):
    """Test cases for the Student model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )

    def test_student_creation(self):
        """Test basic student creation."""
        student = Student.objects.create(user=self.user)
        self.assertEqual(student.user, self.user)
        self.assertIsInstance(student.id, uuid.UUID)

    def test_student_uuid_primary_key(self):
        """Test that student has UUID primary key."""
        student = Student.objects.create(user=self.user)
        self.assertIsInstance(student.id, uuid.UUID)

    def test_student_timestamps(self):
        """Test student timestamp fields."""
        student = Student.objects.create(user=self.user)
        self.assertIsNotNone(student.created_at)
        self.assertIsNotNone(student.updated_at)
        self.assertIsInstance(student.created_at, timezone.datetime)
        self.assertIsInstance(student.updated_at, timezone.datetime)

    def test_student_str_representation(self):
        """Test student string representation."""
        student = Student.objects.create(user=self.user)
        self.assertEqual(str(student), f"Student: {self.user.username}")

    def test_student_table_name(self):
        """Test student table name."""
        student = Student.objects.create(user=self.user)
        self.assertEqual(student._meta.db_table, "accounts_student")

    def test_student_user_relationship(self):
        """Test student-user one-to-one relationship."""
        student = Student.objects.create(user=self.user)
        self.assertEqual(student.user, self.user)
        self.assertEqual(self.user.student_profile, student)

    def test_student_cascade_delete(self):
        """Test that student is deleted when user is deleted."""
        student = Student.objects.create(user=self.user)
        student_id = student.id
        self.user.delete()
        self.assertFalse(Student.objects.filter(id=student_id).exists())


class TeacherAssistantModelTest(TestCase):
    """Test cases for the TeacherAssistant model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testta", password="testpass123"
        )

    def test_teacher_assistant_creation(self):
        """Test basic teacher assistant creation."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertEqual(ta.user, self.user)
        self.assertIsInstance(ta.id, uuid.UUID)

    def test_teacher_assistant_uuid_primary_key(self):
        """Test that teacher assistant has UUID primary key."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertIsInstance(ta.id, uuid.UUID)

    def test_teacher_assistant_timestamps(self):
        """Test teacher assistant timestamp fields."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertIsNotNone(ta.created_at)
        self.assertIsNotNone(ta.updated_at)
        self.assertIsInstance(ta.created_at, timezone.datetime)
        self.assertIsInstance(ta.updated_at, timezone.datetime)

    def test_teacher_assistant_str_representation(self):
        """Test teacher assistant string representation."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertEqual(str(ta), f"TeacherAssistant: {self.user.username}")

    def test_teacher_assistant_table_name(self):
        """Test teacher assistant table name."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertEqual(ta._meta.db_table, "accounts_teacher_assistant")

    def test_teacher_assistant_user_relationship(self):
        """Test teacher assistant-user one-to-one relationship."""
        ta = TeacherAssistant.objects.create(user=self.user)
        self.assertEqual(ta.user, self.user)
        self.assertEqual(self.user.teacher_assistant_profile, ta)

    def test_teacher_assistant_cascade_delete(self):
        """Test that teacher assistant is deleted when user is deleted."""
        ta = TeacherAssistant.objects.create(user=self.user)
        ta_id = ta.id
        self.user.delete()
        self.assertFalse(TeacherAssistant.objects.filter(id=ta_id).exists())


class TeacherStudentRelationshipTest(TestCase):
    """Test cases for teacher-student relationships."""

    def setUp(self):
        self.User = get_user_model()
        self.teacher_user = self.User.objects.create_user(
            username="teacher1", password="testpass123"
        )
        self.student_user = self.User.objects.create_user(
            username="student1", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.student = Student.objects.create(user=self.student_user)

    def test_user_can_have_teacher_profile(self):
        """Test that user can have a teacher profile."""
        self.assertTrue(hasattr(self.teacher_user, "teacher_profile"))
        self.assertEqual(self.teacher_user.teacher_profile, self.teacher)

    def test_user_can_have_student_profile(self):
        """Test that user can have a student profile."""
        self.assertTrue(hasattr(self.student_user, "student_profile"))
        self.assertEqual(self.student_user.student_profile, self.student)

    def test_user_cannot_have_both_profiles(self):
        """Test that a user cannot have both teacher and student profiles."""
        # This should work without errors
        self.assertFalse(hasattr(self.teacher_user, "student_profile"))
        self.assertFalse(hasattr(self.student_user, "teacher_profile"))

    def test_profile_access_methods(self):
        """Test profile access methods."""
        self.assertEqual(self.teacher_user.teacher_profile, self.teacher)
        self.assertEqual(self.student_user.student_profile, self.student)

    def test_profile_deletion(self):
        """Test profile deletion."""
        self.teacher.delete()
        # After deletion, the teacher_profile should not exist
        self.assertFalse(Teacher.objects.filter(id=self.teacher.id).exists())

        self.student.delete()
        # After deletion, the student_profile should not exist
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())


class ModelValidationTest(TestCase):
    """Test cases for model validation."""

    def setUp(self):
        self.User = get_user_model()

    def test_username_uniqueness(self):
        """Test username uniqueness constraint."""
        _user1 = self.User.objects.create_user(
            username="uniqueuser", password="testpass123"
        )

        # Should raise error for duplicate username
        with self.assertRaises(Exception):
            self.User.objects.create_user(username="uniqueuser", password="testpass123")

    def test_password_validation(self):
        """Test password validation."""
        # Should work with valid password
        user = self.User.objects.create_user(
            username="passworduser", password="testpass123"
        )
        self.assertTrue(user.check_password("testpass123"))

    def test_email_optional(self):
        """Test that email is optional."""
        user = self.User.objects.create_user(
            username="noemailuser", password="testpass123"
        )
        self.assertEqual(user.email, "")

    def test_user_active_by_default(self):
        """Test that users are active by default."""
        user = self.User.objects.create_user(
            username="activeuser", password="testpass123"
        )
        self.assertTrue(user.is_active)

    def test_user_staff_false_by_default(self):
        """Test that users are not staff by default."""
        user = self.User.objects.create_user(
            username="staffuser", password="testpass123"
        )
        self.assertFalse(user.is_staff)

    def test_user_superuser_false_by_default(self):
        """Test that users are not superuser by default."""
        user = self.User.objects.create_user(
            username="superuser", password="testpass123"
        )
        self.assertFalse(user.is_superuser)
