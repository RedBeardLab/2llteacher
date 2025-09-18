"""
Views for the homeworks app.

This module provides views for managing homework assignments and their sections,
following the testable-first architecture with typed data contracts.
"""
from dataclasses import dataclass
from typing import Dict, Any
from uuid import UUID
from django.forms import formset_factory

from django.views import View
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages

from llteacher.permissions.decorators import teacher_required

from .models import Homework, Section
from .services import HomeworkService, HomeworkCreateData, HomeworkUpdateData, SectionCreateData, SectionStatus, SectionData
from .forms import HomeworkForm, SectionForm, SectionFormSet


@dataclass
class HomeworkListItem:
    """Data structure for a single homework item in the list view."""
    id: UUID
    title: str
    description: str
    due_date: Any  # datetime
    section_count: int
    created_at: Any  # datetime
    is_overdue: bool
    sections: list[SectionData] | None = None
    completed_percentage: int = 0
    in_progress_percentage: int = 0


@dataclass
class HomeworkListData:
    """Data structure for the homework list view."""
    homeworks: list[HomeworkListItem]
    user_type: str  # 'teacher', 'student', or 'unknown'
    total_count: int
    has_progress_data: bool


class HomeworkListView(View):
    """
    View for listing homework assignments.
    
    For teachers: Shows homeworks they have created
    For students: Shows homeworks assigned to them with progress
    """
    
    @method_decorator(login_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display homework list."""
        # Get the appropriate data based on user type
        data = self._get_view_data(request.user)
        
        # Render the template with the data
        return render(request, 'homeworks/list.html', {'data': data})
    
    def _get_view_data(self, user) -> HomeworkListData:
        """
        Prepare data for the homework list view based on user type.
        
        Args:
            user: The current user
            
        Returns:
            HomeworkListData with homeworks and user type information
        """
        # Determine user type
        teacher_profile = getattr(user, 'teacher_profile', None)
        student_profile = getattr(user, 'student_profile', None)
        
        homeworks = []
        has_progress_data = False
        
        if teacher_profile:
            # Teacher view - show homeworks created by this teacher
            user_type = 'teacher'
            
            # Query homeworks created by this teacher
            homework_objects = Homework.objects.filter(
                created_by=teacher_profile
            ).order_by('-created_at').prefetch_related('sections')
            
            # Transform to view-specific data
            for homework in homework_objects:
                homeworks.append(HomeworkListItem(
                    id=homework.id,
                    title=homework.title,
                    description=homework.description,
                    due_date=homework.due_date,
                    section_count=homework.section_count,
                    created_at=homework.created_at,
                    is_overdue=homework.is_overdue,
                    sections=None  # No section data needed for teacher view
                ))
            
        elif student_profile:
            # Student view - show homeworks with progress
            user_type = 'student'
            has_progress_data = True
            
            # For now, show all homeworks (in a real app, would filter by assignments)
            homework_objects = Homework.objects.all().order_by('-created_at').prefetch_related('sections')
            
            # Transform to view-specific data with progress
            for homework in homework_objects:
                # Get student's progress for this homework
                progress_data = HomeworkService.get_student_homework_progress(
                    student_profile,
                    homework
                )
                
                # Format section data for the view using SectionData objects
                sections = []
                for section_progress in progress_data.sections_progress:
                    sections.append(SectionData(
                        id=section_progress.id,
                        title=section_progress.title,
                        content=section_progress.content,
                        order=section_progress.order,
                        solution_content=section_progress.solution_content,
                        created_at=section_progress.created_at,
                        updated_at=section_progress.updated_at,
                        status=section_progress.status,
                        conversation_id=section_progress.conversation_id
                    ))
                
                # Calculate percentages directly in the view
                total_sections = len(progress_data.sections_progress)
                completed_sections = sum(1 for s in progress_data.sections_progress if s.status == SectionStatus.SUBMITTED)
                in_progress_sections = sum(1 for s in progress_data.sections_progress if s.status in [SectionStatus.IN_PROGRESS, SectionStatus.IN_PROGRESS_OVERDUE])
                
                completed_percentage = round((completed_sections / total_sections) * 100) if total_sections > 0 else 0
                in_progress_percentage = round((in_progress_sections / total_sections) * 100) if total_sections > 0 else 0
                
                homeworks.append(HomeworkListItem(
                    id=homework.id,
                    title=homework.title,
                    description=homework.description,
                    due_date=homework.due_date,
                    section_count=homework.section_count,
                    created_at=homework.created_at,
                    is_overdue=homework.is_overdue,
                    sections=sections,
                    completed_percentage=completed_percentage,
                    in_progress_percentage=in_progress_percentage
                ))
                
        else:
            # Unknown user type
            user_type = 'unknown'
        
        # Create and return the view data
        return HomeworkListData(
            homeworks=homeworks,
            user_type=user_type,
            total_count=len(homeworks),
            has_progress_data=has_progress_data
        )


@dataclass
class HomeworkDetailData:
    """Data structure for the homework detail view."""
    id: UUID
    title: str
    description: str
    due_date: Any  # datetime
    created_by: UUID
    created_by_name: str
    created_at: Any  # datetime
    sections: list[SectionData]
    is_overdue: bool
    user_type: str  # 'teacher', 'student', or 'unknown'
    can_edit: bool
    llm_config: Dict[str, Any] | None = None


@dataclass
class HomeworkFormData:
    """Data structure for the homework form view."""
    form: Any  # HomeworkForm
    section_forms: Any  # FormSet
    user_type: str
    action: str  # 'create' or 'edit'
    is_submitted: bool = False
    errors: Dict[str, Any] = None


class HomeworkCreateView(View):
    """View for creating a new homework."""
    
    @method_decorator(login_required, name='dispatch')
    @method_decorator(teacher_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display the create form."""
        data = self._get_view_data(request)
        return render(request, 'homeworks/form.html', {'data': data})
    
    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST requests to process the form submission."""
        data = self._process_form_submission(request)
        
        if data.is_submitted:
            messages.success(request, "Homework created successfully!")
            return redirect('homeworks:detail', homework_id=data.form.instance.id)
        
        return render(request, 'homeworks/form.html', {'data': data})
    
    def _get_view_data(self, request: HttpRequest) -> HomeworkFormData:
        """Prepare data for the form view."""
        # Create an empty homework form
        form = HomeworkForm()
        
        # Create empty section form (we'll start with one)
        SectionFormset = formset_factory(SectionForm, extra=1, formset=SectionFormSet)
        section_formset = SectionFormset(prefix='sections')
        
        # Return form data
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type='teacher',
            action='create',
            is_submitted=False
        )
    
    def _process_form_submission(self, request: HttpRequest) -> HomeworkFormData:
        """Process the form submission."""
        # Create forms from POST data
        form = HomeworkForm(request.POST)
        
        SectionFormset = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
        section_formset = SectionFormset(request.POST, prefix='sections')
        
        # Check form validity
        if form.is_valid() and section_formset.is_valid():
            # Extract homework data from form
            homework_data = HomeworkCreateData(
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                due_date=form.cleaned_data['due_date'],
                sections=[],
                llm_config=form.cleaned_data['llm_config'].id if form.cleaned_data['llm_config'] else None
            )
            
            # Extract sections data from formset
            section_data = []
            for section_form in section_formset.forms:
                if section_form.cleaned_data and not section_form.cleaned_data.get('DELETE', False):
                    # Extract data from form
                    section_data.append(SectionCreateData(
                        title=section_form.cleaned_data['title'],
                        content=section_form.cleaned_data['content'],
                        order=section_form.cleaned_data['order'],
                        solution=section_form.cleaned_data['solution']
                    ))
            
            # Add sections to homework data
            homework_data.sections = section_data
            
            # Use service to create homework with sections (single creation point)
            result = HomeworkService.create_homework_with_sections(
                homework_data,
                request.user.teacher_profile
            )
            
            if result.success:
                # Success - set created homework on form for redirect
                form.instance.id = result.homework_id
                
                # Return success data
                return HomeworkFormData(
                    form=form,
                    section_forms=section_formset,
                    user_type='teacher',
                    action='create',
                    is_submitted=True
                )
            else:
                # Service error
                messages.error(request, f"Error creating homework: {result.error}")
        
        # Form validation error or service error
        errors = {}
        if form.errors:
            errors['homework'] = form.errors
        if section_formset.errors:
            errors['sections'] = section_formset.errors
        if section_formset.non_form_errors():
            errors['formset'] = section_formset.non_form_errors()
        
        # Return form data with errors
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type='teacher',
            action='create',
            is_submitted=False,
            errors=errors
        )


class HomeworkEditView(View):
    """View for editing an existing homework."""
    
    @method_decorator(login_required, name='dispatch')
    @method_decorator(teacher_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display the edit form with existing data."""
        # Get the homework and check ownership
        try:
            homework = Homework.objects.get(id=homework_id)
            if homework.created_by != request.user.teacher_profile:
                return HttpResponseForbidden("You don't have permission to edit this homework.")
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect('homeworks:list')
            
        # Get view data with existing homework
        data = self._get_view_data(request, homework)
        return render(request, 'homeworks/form.html', {'data': data})
    
    def post(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle POST requests to process the form submission."""
        # Get the homework and check ownership
        try:
            homework = Homework.objects.get(id=homework_id)
            if homework.created_by != request.user.teacher_profile:
                return HttpResponseForbidden("You don't have permission to edit this homework.")
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect('homeworks:list')
            
        # Process the form submission
        data = self._process_form_submission(request, homework)
        
        if data.is_submitted:
            messages.success(request, "Homework updated successfully!")
            return redirect('homeworks:detail', homework_id=homework_id)
        
        return render(request, 'homeworks/form.html', {'data': data})
    
    def _get_view_data(self, request: HttpRequest, homework: Homework) -> HomeworkFormData:
        """Prepare data for the form view with existing homework data."""
        # Create homework form with instance
        form = HomeworkForm(instance=homework)
        
        # Get existing sections for this homework
        sections = homework.sections.all().order_by('order')
        initial_section_data = []
        
        # Prepare initial data for section formset
        for section in sections:
            section_data = {
                'id': section.id,
                'title': section.title,
                'content': section.content,
                'order': section.order,
                'solution': section.solution.content if section.solution else ''
            }
            initial_section_data.append(section_data)
        
        # Create section formset with initial data
        SectionFormset = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
        section_formset = SectionFormset(
            prefix='sections',
            initial=initial_section_data
        )
        
        # Return form data
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type='teacher',
            action='edit',
            is_submitted=False
        )
    
    def _process_form_submission(self, request: HttpRequest, homework: Homework) -> HomeworkFormData:
        """Process the form submission for updating a homework."""
        # Create forms from POST data with homework instance
        form = HomeworkForm(request.POST, instance=homework)
        
        # Create formset for sections
        SectionFormset = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
        section_formset = SectionFormset(request.POST, prefix='sections')
        
        # Check form validity
        if form.is_valid() and section_formset.is_valid():
            # Save basic homework data
            homework = form.save()
            
            # Process sections
            sections_to_update = []
            sections_to_create = []
            sections_to_delete = []
            
            for section_form in section_formset:
                if not section_form.cleaned_data:
                    continue
                    
                if section_form.cleaned_data.get('DELETE', False):
                    # Section marked for deletion
                    if section_form.cleaned_data.get('id'):
                        sections_to_delete.append(section_form.cleaned_data['id'])
                else:
                    # Get section data
                    section_data = {
                        'title': section_form.cleaned_data['title'],
                        'content': section_form.cleaned_data['content'],
                        'order': section_form.cleaned_data['order'],
                        'solution': section_form.cleaned_data['solution']
                    }
                    
                    if section_form.cleaned_data.get('id'):
                        # Existing section to update
                        section_data['id'] = section_form.cleaned_data['id']
                        sections_to_update.append(section_data)
                    else:
                        # New section to create
                        sections_to_create.append(SectionCreateData(
                            title=section_data['title'],
                            content=section_data['content'],
                            order=section_data['order'],
                            solution=section_data['solution']
                        ))
            
            # Create update data
            update_data = HomeworkUpdateData(
                title=homework.title,
                description=homework.description,
                due_date=homework.due_date,
                llm_config=homework.llm_config.id if homework.llm_config else None,
                sections_to_update=sections_to_update,
                sections_to_create=sections_to_create,
                sections_to_delete=sections_to_delete
            )
            
            # Update homework using service
            result = HomeworkService.update_homework(homework.id, update_data)
            
            if result.success:
                # Return success data
                return HomeworkFormData(
                    form=form,
                    section_forms=section_formset,
                    user_type='teacher',
                    action='edit',
                    is_submitted=True
                )
            else:
                # Service error
                messages.error(request, f"Error updating homework: {result.error}")
        
        # Form validation error or service error
        errors = {}
        if form.errors:
            errors['homework'] = form.errors
        if section_formset.errors:
            errors['sections'] = section_formset.errors
        if section_formset.non_form_errors():
            errors['formset'] = section_formset.non_form_errors()
        
        # Return form data with errors
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type='teacher',
            action='edit',
            is_submitted=False,
            errors=errors
        )


class HomeworkDetailView(View):
    """
    View for displaying and editing a homework assignment.
    
    For teachers: Shows the homework with editing capabilities
    For students: Shows the homework with links to start working
    """
    
    @method_decorator(login_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display homework detail."""
        # Get the appropriate data based on user type
        data = self._get_view_data(request.user, homework_id)
        
        # If homework not found, redirect to list view
        if data is None:
            return redirect('homeworks:list')
        
        # Render the template with the data
        return render(request, 'homeworks/detail.html', {'data': data})
    
    def post(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle POST requests for homework actions (like deletion)."""
        # Check if this is a delete action
        action = request.POST.get('action')
        
        if action == 'delete':
            return self._handle_delete(request, homework_id)
        
        # If no valid action, redirect to detail view
        return redirect('homeworks:detail', homework_id=homework_id)
    
    def _handle_delete(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle homework deletion."""
        # Check if user is a teacher
        teacher_profile = getattr(request.user, 'teacher_profile', None)
        if not teacher_profile:
            return HttpResponseForbidden("Only teachers can delete homeworks.")
        
        # Get the homework and check ownership
        try:
            from .models import Homework
            homework = Homework.objects.get(id=homework_id)
            if homework.created_by != teacher_profile:
                return HttpResponseForbidden("You can only delete homeworks you created.")
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect('homeworks:list')
        
        # Delete the homework using the service
        success = HomeworkService.delete_homework(homework_id)
        
        if success:
            messages.success(request, f"Homework '{homework.title}' has been deleted successfully.")
        else:
            messages.error(request, "Failed to delete homework. Please try again.")
        
        return redirect('homeworks:list')
    
    def _get_view_data(self, user, homework_id: UUID) -> HomeworkDetailData | None:
        """
        Prepare data for the homework detail view based on user type.
        
        Args:
            user: The current user
            homework_id: The UUID of the homework to display
            
        Returns:
            HomeworkDetailData with homework details, or None if not found
        """
        # Determine user type
        teacher_profile = getattr(user, 'teacher_profile', None)
        student_profile = getattr(user, 'student_profile', None)
        
        # Get homework details using service
        homework_detail = HomeworkService.get_homework_with_sections(homework_id)
        
        if homework_detail is None:
            return None
            
        # Determine user type and permissions
        user_type = 'unknown'
        can_edit = False
        
        if teacher_profile:
            user_type = 'teacher'
            # Teacher can edit if they are the owner
            can_edit = str(teacher_profile.id) == str(homework_detail.created_by)
            
        elif student_profile:
            user_type = 'student'
            # Students can't edit homeworks
            can_edit = False
        
        # Format sections data
        sections = []
        
        # Get section progress for students
        section_progress_map = {}
        if student_profile:
            # Get the homework object for progress calculation
            try:
                homework_obj = Homework.objects.get(id=homework_id)
                progress_data = HomeworkService.get_student_homework_progress(student_profile, homework_obj)
                # Create a map of section_id -> progress data for easy lookup
                for progress in progress_data.sections_progress:
                    section_progress_map[progress.id] = progress
            except Homework.DoesNotExist:
                pass
        
        if homework_detail.sections:
            for section_data in homework_detail.sections:
                # Get progress data for this section if available
                progress = section_progress_map.get(section_data.id)
                
                sections.append(SectionData(
                    id=section_data.id,
                    title=section_data.title,
                    content=section_data.content,
                    order=section_data.order,
                    solution_content=section_data.solution_content,
                    created_at=section_data.created_at,
                    updated_at=section_data.updated_at,
                    status=progress.status if progress else None,
                    conversation_id=progress.conversation_id if progress else None
                ))
        
        # Get teacher name
        from accounts.models import Teacher
        teacher = Teacher.objects.filter(id=homework_detail.created_by).first()
        created_by_name = f"{teacher.user.first_name} {teacher.user.last_name}".strip() if teacher else "Unknown Teacher"
        
        # Create and return the view data
        return HomeworkDetailData(
            id=homework_detail.id,
            title=homework_detail.title,
            description=homework_detail.description,
            due_date=homework_detail.due_date,
            created_by=homework_detail.created_by,
            created_by_name=created_by_name,
            created_at=homework_detail.created_at,
            sections=sections,
            is_overdue=homework_detail.due_date < timezone.now(),
            user_type=user_type,
            can_edit=can_edit,
            llm_config={"id": homework_detail.llm_config} if homework_detail.llm_config else None
        )


@dataclass
class SectionDetailViewData:
    """Data structure for the section detail view."""
    homework_id: UUID
    homework_title: str
    section_id: UUID
    section_title: str
    section_content: str
    section_order: int
    has_solution: bool
    solution_content: str | None
    conversations: list[Dict[str, Any]] | None = None
    submission: Dict[str, Any] | None = None
    is_teacher: bool = False
    is_student: bool = False


class SectionDetailView(View):
    """
    View for displaying individual sections with their conversations.
    
    For teachers: Shows the section with solution and test conversations
    For students: Shows the section with their conversations and submission
    """
    
    @method_decorator(login_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest, homework_id: UUID, section_id: UUID) -> HttpResponse:
        """Handle GET requests to display section detail."""
        # Get the homework and section
        try:
            homework = Homework.objects.get(id=homework_id)
            _section = Section.objects.get(id=section_id, homework=homework)
        except (Homework.DoesNotExist, Section.DoesNotExist):
            return redirect('homeworks:detail', homework_id=homework_id)
        
        # Check user access permissions
        teacher_profile = getattr(request.user, 'teacher_profile', None)
        student_profile = getattr(request.user, 'student_profile', None)
        
        # Teacher must own the homework
        if teacher_profile and homework.created_by != teacher_profile:
            return HttpResponseForbidden("Access denied.")
        
        # For now, allow all students access to sections
        # Additional checks can be added here if needed
        
        # If user is neither teacher nor student, deny access
        if not teacher_profile and not student_profile:
            return HttpResponseForbidden("Access denied.")
        
        # Get the appropriate data for the view
        data = self._get_view_data(request.user, homework_id, section_id)
        
        # If there was a problem getting the data, redirect to homework detail
        if data is None:
            return redirect('homeworks:detail', homework_id=homework_id)
        
        # Render the template with the data
        return render(request, 'homeworks/section_detail.html', {'data': data})
    
    def _get_view_data(self, user, homework_id: UUID, section_id: UUID) -> SectionDetailViewData | None:
        """
        Prepare data for the section detail view based on user type.
        
        Args:
            user: The current user
            homework_id: The UUID of the homework
            section_id: The UUID of the section to display
            
        Returns:
            SectionDetailViewData with section details and conversations, or None if not found
        """
        from conversations.models import Conversation, Submission
        
        # Determine user type
        teacher_profile = getattr(user, 'teacher_profile', None)
        student_profile = getattr(user, 'student_profile', None)
        
        # Get homework and section
        try:
            homework = Homework.objects.get(id=homework_id)
            section = Section.objects.select_related('solution').get(id=section_id, homework=homework)
        except (Homework.DoesNotExist, Section.DoesNotExist):
            return None
        
        # Initialize variables
        is_teacher = False
        is_student = False
        conversations = None
        submission = None
        
        # Get conversations and submission data based on user type
        if teacher_profile:
            is_teacher = True
            
            # Get test conversations created by this teacher for this section
            teacher_conversations = Conversation.objects.filter(
                user=user,
                section=section,
                is_deleted=False
            ).select_related('user').prefetch_related('messages')
            
            # Format conversations data
            if teacher_conversations.exists():
                conversations = []
                for conv in teacher_conversations:
                    conversations.append({
                        'id': conv.id,
                        'created_at': conv.created_at,
                        'updated_at': conv.updated_at,
                        'message_count': conv.message_count,
                        'is_teacher_test': True,
                        'label': f"Test conversation {conv.created_at.strftime('%Y-%m-%d %H:%M')}"
                    })
        
        elif student_profile:
            is_student = True
            
            # Get conversations created by this student for this section
            student_conversations = Conversation.objects.filter(
                user=user,
                section=section,
                is_deleted=False
            ).select_related('user').prefetch_related('messages')
            
            # Format conversations data
            if student_conversations.exists():
                conversations = []
                for conv in student_conversations:
                    conversations.append({
                        'id': conv.id,
                        'created_at': conv.created_at,
                        'updated_at': conv.updated_at,
                        'message_count': conv.message_count,
                        'is_teacher_test': False,
                        'label': f"Conversation {conv.created_at.strftime('%Y-%m-%d %H:%M')}"
                    })
                    
            # Get submission for this student and section if it exists
            student_submission = Submission.objects.filter(
                conversation__user=user,
                conversation__section=section
            ).select_related('conversation').first()
            
            if student_submission:
                submission = {
                    'id': student_submission.id,
                    'conversation_id': student_submission.conversation.id,
                    'submitted_at': student_submission.submitted_at
                }
        
        # Create and return the view data
        return SectionDetailViewData(
            homework_id=homework.id,
            homework_title=homework.title,
            section_id=section.id,
            section_title=section.title,
            section_content=section.content,
            section_order=section.order,
            has_solution=section.solution is not None,
            solution_content=section.solution.content if section.solution else None,
            conversations=conversations,
            submission=submission,
            is_teacher=is_teacher,
            is_student=is_student
        )


class HomeworkSubmissionsView(View):
    """
    View for displaying all student submissions for a homework assignment.
    
    Teacher-only view that shows:
    - All students in the system (including those with no interactions)
    - For each student: all conversations in reverse chronological order
    - Submission status and warning indicators for non-participating students
    - Includes soft-deleted conversations
    """
    
    @method_decorator(login_required, name='dispatch')
    @method_decorator(teacher_required, name='dispatch')
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)
    
    def get(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display homework submissions."""
        # Get the homework and check ownership
        try:
            homework = Homework.objects.get(id=homework_id)
            if homework.created_by != request.user.teacher_profile:
                return HttpResponseForbidden("You can only view submissions for homeworks you created.")
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect('homeworks:list')
        
        # Get submissions data using service
        submissions_data = HomeworkService.get_homework_submissions(homework_id)
        
        if submissions_data is None:
            messages.error(request, "Unable to load submissions data.")
            return redirect('homeworks:detail', homework_id=homework_id)
        
        # Render the template with the data
        return render(request, 'homeworks/submissions.html', {'data': submissions_data})
