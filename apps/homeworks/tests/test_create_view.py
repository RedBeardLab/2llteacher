"""
Tests for the HomeworkCreateView.

This module tests the functionality of the HomeworkCreateView, including
form handling, validation, and service interactions.
"""
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from unittest.mock import patch
import uuid

from homeworks.views import HomeworkCreateView, HomeworkFormData
from homeworks.services import HomeworkCreateResult
from accounts.models import Teacher

User = get_user_model()

class HomeworkCreateViewTests(TestCase):
    """Tests for the HomeworkCreateView."""
    
    def setUp(self):
        """Set up test data."""
        # Create a teacher user
        self.teacher_user = User.objects.create_user(
            username='testteacher',
            email='teacher@example.com',
            password='password123'
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        
        # Create a student user (who shouldn't be able to access the view)
        self.student_user = User.objects.create_user(
            username='teststudent',
            email='student@example.com',
            password='password123'
        )
        
        # Create the request factory
        self.factory = RequestFactory()
        
    def test_get_view_data_teacher(self):
        """Test the _get_view_data method for a teacher user."""
        request = self.factory.get('/homeworks/create/')
        request.user = self.teacher_user
        
        view = HomeworkCreateView()
        data = view._get_view_data(request)
        
        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkFormData)
        
        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, 'teacher')
        
        # Check if action is set to create
        self.assertEqual(data.action, 'create')
        
        # Check that form objects exist
        self.assertIsNotNone(data.form)
        self.assertIsNotNone(data.section_forms)
    
    def test_get_request_teacher(self):
        """Test handling a GET request as a teacher."""
        # Login as teacher
        self.client.login(username='testteacher', password='password123')
        
        # Get the response
        response = self.client.get(reverse('homeworks:create'))
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'homeworks/form.html')
        
        # Check context data
        self.assertIn('data', response.context)
        data = response.context['data']
        self.assertEqual(data.action, 'create')
    
    def test_get_request_unauthenticated(self):
        """Test handling a GET request when user is not authenticated."""
        # Get the response (without logging in)
        response = self.client.get(reverse('homeworks:create'))
        
        # Check that user is redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
    
    def test_get_request_not_teacher(self):
        """Test handling a GET request when user is not a teacher."""
        # Login as student
        self.client.login(username='teststudent', password='password123')
        
        # Get the response
        response = self.client.get(reverse('homeworks:create'))
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
    
    @patch('homeworks.services.HomeworkService.create_homework_with_sections')
    def test_post_request_success(self, mock_create_homework):
        """Test handling a successful POST request."""
        # Mock the service response
        result_id = uuid.uuid4()
        mock_create_homework.return_value = HomeworkCreateResult(
            success=True,
            homework_id=result_id,
            section_ids=[uuid.uuid4(), uuid.uuid4()]
        )
        
        # Login as teacher
        self.client.login(username='testteacher', password='password123')
        
        # Create POST data
        post_data = {
            'title': 'Test Homework',
            'description': 'Test Description',
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
            'sections-TOTAL_FORMS': '1',
            'sections-INITIAL_FORMS': '0',
            'sections-MIN_NUM_FORMS': '0',
            'sections-MAX_NUM_FORMS': '1000',
            'sections-0-title': 'Test Section',
            'sections-0-content': 'Test Content',
            'sections-0-order': '1',
            'sections-0-solution': 'Test Solution'
        }
        
        # Submit the form
        response = self.client.post(reverse('homeworks:create'), post_data)
        
        # Check service was called
        mock_create_homework.assert_called_once()
        
        # Check redirection to detail view
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('homeworks:detail', args=[result_id]))
    
    @patch('homeworks.services.HomeworkService.create_homework_with_sections')
    def test_post_request_service_error(self, mock_create_homework):
        """Test handling a POST request when service returns an error."""
        # Mock the service response
        mock_create_homework.return_value = HomeworkCreateResult(
            success=False,
            homework_id=None,  # type: ignore
            section_ids=[],
            error="Service error"
        )
        
        # Login as teacher
        self.client.login(username='testteacher', password='password123')
        
        # Create POST data
        post_data = {
            'title': 'Test Homework',
            'description': 'Test Description',
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
            'sections-TOTAL_FORMS': '1',
            'sections-INITIAL_FORMS': '0',
            'sections-MIN_NUM_FORMS': '0',
            'sections-MAX_NUM_FORMS': '1000',
            'sections-0-title': 'Test Section',
            'sections-0-content': 'Test Content',
            'sections-0-order': '1',
            'sections-0-solution': 'Test Solution'
        }
        
        # Submit the form
        response = self.client.post(reverse('homeworks:create'), post_data)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'homeworks/form.html')
        
        # Check context data
        self.assertIn('data', response.context)
        data = response.context['data']
        self.assertFalse(data.is_submitted)
        
    def test_post_request_form_validation_error(self):
        """Test handling a POST request with form validation errors."""
        # Login as teacher
        self.client.login(username='testteacher', password='password123')
        
        # Create invalid POST data (missing required fields)
        post_data = {
            'title': '',  # Empty title (required)
            'description': 'Test Description',
            'sections-TOTAL_FORMS': '1',
            'sections-INITIAL_FORMS': '0',
            'sections-MIN_NUM_FORMS': '0',
            'sections-MAX_NUM_FORMS': '1000',
            'sections-0-title': 'Test Section',
            'sections-0-content': 'Test Content',
            'sections-0-order': '1'
        }
        
        # Submit the form
        response = self.client.post(reverse('homeworks:create'), post_data)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'homeworks/form.html')
        
        # Check context data
        self.assertIn('data', response.context)
        data = response.context['data']
        self.assertFalse(data.is_submitted)
        self.assertIsNotNone(data.errors)
        
    def test_post_request_formset_validation_error(self):
        """Test handling a POST request with formset validation errors."""
        # Login as teacher
        self.client.login(username='testteacher', password='password123')
        
        # Create invalid POST data (duplicate section orders)
        post_data = {
            'title': 'Test Homework',
            'description': 'Test Description',
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
            'sections-TOTAL_FORMS': '2',
            'sections-INITIAL_FORMS': '0',
            'sections-MIN_NUM_FORMS': '0',
            'sections-MAX_NUM_FORMS': '1000',
            'sections-0-title': 'Test Section 1',
            'sections-0-content': 'Test Content 1',
            'sections-0-order': '1',  # Same order as section 1
            'sections-1-title': 'Test Section 2',
            'sections-1-content': 'Test Content 2',
            'sections-1-order': '1'  # Same order as section 0
        }
        
        # Submit the form
        response = self.client.post(reverse('homeworks:create'), post_data)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'homeworks/form.html')
        
        # Check context data
        self.assertIn('data', response.context)
        data = response.context['data']
        self.assertFalse(data.is_submitted)
        self.assertIsNotNone(data.errors)
    
    def test_process_form_submission_creates_single_homework(self):
        """Test that _process_form_submission creates only one homework, not two.
        
        This is an integration test that verifies the bug where homework creation
        was happening twice - once directly in the view and once in the service.
        """
        from homeworks.models import Homework
        
        # Count homeworks before
        initial_count = Homework.objects.count()
        
        # Create a request with valid form data
        post_data = {
            'title': 'Integration Test Homework',
            'description': 'Test Description for Integration',
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
            'sections-TOTAL_FORMS': '2',
            'sections-INITIAL_FORMS': '0',
            'sections-MIN_NUM_FORMS': '0',
            'sections-MAX_NUM_FORMS': '1000',
            'sections-0-title': 'Test Section 1',
            'sections-0-content': 'Test Content 1',
            'sections-0-order': '1',
            'sections-0-solution': 'Test Solution 1',
            'sections-1-title': 'Test Section 2',
            'sections-1-content': 'Test Content 2',
            'sections-1-order': '2',
            'sections-1-solution': 'Test Solution 2'
        }
        
        request = self.factory.post('/homeworks/create/', post_data)
        request.user = self.teacher_user
        
        # Create view instance and process form submission
        view = HomeworkCreateView()
        result = view._process_form_submission(request)
        
        # Verify only one homework was created
        final_count = Homework.objects.count()
        self.assertEqual(final_count, initial_count + 1, 
                        f"Should create exactly one homework, but created {final_count - initial_count}")
        
        # Verify the homework has the correct properties
        if result.is_submitted:
            homework = Homework.objects.latest('created_at')
            self.assertEqual(homework.title, 'Integration Test Homework')
            self.assertEqual(homework.description, 'Test Description for Integration')
            self.assertEqual(homework.created_by, self.teacher)
            
            # Verify the homework has sections
            sections = homework.sections.all().order_by('order')
            self.assertEqual(sections.count(), 2, "Homework should have exactly 2 sections")
            
            # Verify section details
            self.assertEqual(sections[0].title, 'Test Section 1')
            self.assertEqual(sections[0].content, 'Test Content 1')
            self.assertEqual(sections[0].order, 1)
            self.assertIsNotNone(sections[0].solution)
            self.assertEqual(sections[0].solution.content, 'Test Solution 1')
            
            self.assertEqual(sections[1].title, 'Test Section 2')
            self.assertEqual(sections[1].content, 'Test Content 2')
            self.assertEqual(sections[1].order, 2)
            self.assertIsNotNone(sections[1].solution)
            self.assertEqual(sections[1].solution.content, 'Test Solution 2')
