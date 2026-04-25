"""
Views for the homeworks app.

This module provides views for managing homework assignments and their sections,
following the testable-first architecture with typed data contracts.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any, assert_type, cast
from uuid import UUID
from django.forms import formset_factory

if TYPE_CHECKING:
    from django.forms.utils import ErrorDict, ErrorList
    from .services import HomeworkProgressData

from django.views import View
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
import logging

from django.utils import timezone
from django.contrib import messages

from llteacher.permissions.decorators import teacher_required, TeacherRequest

from .models import Homework, Section
from .services import (
    HomeworkService,
    HomeworkUpdateData,
    SectionCreateData,
    SectionStatus,
    SectionData,
)
from .forms import (
    HomeworkCreateForm,
    HomeworkEditForm,
    SectionForm,
    SectionFormSet,
    normalize_section_formset_orders,
)

logger = logging.getLogger(__name__)


def _mark_invalid_fields(form) -> None:
    """Add Bootstrap is-invalid CSS class to any form widget that has errors."""
    for field_name in form.errors:
        if field_name in form.fields:
            widget = form.fields[field_name].widget
            css = widget.attrs.get("class", "")
            if "is-invalid" not in css:
                widget.attrs["class"] = f"{css} is-invalid".strip()


@dataclass
class HomeworkListItem:
    """Data structure for a single homework item in the list view."""

    id: UUID
    title: str
    description: str
    due_date: datetime
    section_count: int
    created_at: datetime
    is_overdue: bool
    roles: list[str]  # ['teacher', 'student', 'teacher_assistant']
    expires_at: datetime | None = None
    is_hidden: bool = False
    is_accessible_to_students: bool = True
    is_draft: bool = False
    is_scheduled: bool = False
    publish_at: datetime | None = None
    sections: list[SectionData] | None = None
    completed_percentage: int = 0
    in_progress_percentage: int = 0
    is_submitted: bool = False


@dataclass
class HomeworkListData:
    """Data structure for the homework list view."""

    homeworks: list[HomeworkListItem]
    user_types: list[
        str
    ]  # All roles this user has: ['teacher', 'student', 'teacher_assistant']
    total_count: int
    has_progress_data: bool


@dataclass
class HomeworkListEntry:
    """Internal typed accumulator for homework list assembly."""

    homework: Homework
    roles: list[str]
    progress: "HomeworkProgressData | None" = None


class HomeworkListView(View):
    """
    View for listing homework assignments.

    For teachers: Shows homeworks they have created
    For students: Shows homeworks assigned to them with progress
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display homework list."""
        # Get the appropriate data based on user type
        data = self._get_view_data(request.user)

        # Render the template with the data
        return render(request, "homeworks/list.html", {"data": data})

    def _get_view_data(self, user) -> HomeworkListData:
        """
        Prepare data for the homework list view based on user type.

        Args:
            user: The current user

        Returns:
            HomeworkListData with homeworks and user type information
        """
        from django.db.models import Q

        # Auto-publish any scheduled homework before building the list
        try:
            HomeworkService.auto_publish_due_scheduled()
        except Exception:
            pass  # Never break the page load

        # Determine user type
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)
        teacher_assistant_profile = getattr(user, "teacher_assistant_profile", None)

        # Track which user types this user has
        user_types = []
        if teacher_profile:
            user_types.append("teacher")
        if student_profile:
            user_types.append("student")
        if teacher_assistant_profile:
            user_types.append("teacher_assistant")

        # Use dict to track homeworks and their roles
        homework_dict: dict[UUID, HomeworkListEntry] = {}

        # Add teacher homeworks
        if teacher_profile:
            teacher_courses = teacher_profile.courses.all()
            teacher_homework_objects = (
                Homework.objects.filter(
                    Q(course__in=teacher_courses) | Q(created_by=teacher_profile)
                )
                .distinct()
                .prefetch_related("sections")
            )

            for hw in teacher_homework_objects:
                if hw.id not in homework_dict:
                    homework_dict[hw.id] = HomeworkListEntry(homework=hw, roles=[])
                homework_dict[hw.id].roles.append("teacher")

        # Add student homeworks
        if student_profile:
            enrolled_courses = student_profile.enrolled_courses.filter(
                courseenrollment__is_active=True
            )
            student_homework_objects = (
                Homework.objects.filter(course__in=enrolled_courses)
                .filter(is_hidden=False)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                .prefetch_related("sections")
            )

            for hw in student_homework_objects:
                if hw.id not in homework_dict:
                    homework_dict[hw.id] = HomeworkListEntry(homework=hw, roles=[])
                homework_dict[hw.id].roles.append("student")
                # Calculate progress for student view
                homework_dict[
                    hw.id
                ].progress = HomeworkService.get_student_homework_progress(
                    student_profile, hw
                )

        # Add TA homeworks
        if teacher_assistant_profile:
            ta_courses = teacher_assistant_profile.courses.all()
            ta_homework_objects = (
                Homework.objects.filter(course__in=ta_courses)
                .distinct()
                .prefetch_related("sections")
            )

            for hw in ta_homework_objects:
                if hw.id not in homework_dict:
                    homework_dict[hw.id] = HomeworkListEntry(homework=hw, roles=[])
                homework_dict[hw.id].roles.append("teacher_assistant")

        # Convert to HomeworkListItem
        homeworks: list[HomeworkListItem] = []
        has_progress_data = "student" in user_types

        for hw_data in sorted(
            homework_dict.values(), key=lambda x: x.homework.created_at, reverse=True
        ):
            hw = hw_data.homework
            progress_data = hw_data.progress

            # Prepare section data and progress if available
            sections = None
            completed_percentage = 0
            in_progress_percentage = 0
            is_submitted = False

            if progress_data:
                # Format section data for the view using SectionData objects
                sections = []
                for section_progress in progress_data.sections_progress:
                    sections.append(
                        SectionData(
                            id=section_progress.id,
                            title=section_progress.title,
                            content=section_progress.content,
                            order=section_progress.order,
                            solution_content=section_progress.solution_content,
                            created_at=section_progress.created_at,
                            updated_at=section_progress.updated_at,
                            status=section_progress.status,
                            conversation_id=section_progress.conversation_id,
                        )
                    )

                # Calculate percentages
                total_sections = len(progress_data.sections_progress)
                completed_sections = sum(
                    1
                    for s in progress_data.sections_progress
                    if s.status == SectionStatus.SUBMITTED
                )
                in_progress_sections = sum(
                    1
                    for s in progress_data.sections_progress
                    if s.status
                    in [SectionStatus.IN_PROGRESS, SectionStatus.IN_PROGRESS_OVERDUE]
                )

                completed_percentage = (
                    round((completed_sections / total_sections) * 100)
                    if total_sections > 0
                    else 0
                )
                in_progress_percentage = (
                    round((in_progress_sections / total_sections) * 100)
                    if total_sections > 0
                    else 0
                )

                is_submitted = (
                    total_sections > 0 and completed_sections == total_sections
                )

            homeworks.append(
                HomeworkListItem(
                    id=hw.id,
                    title=hw.title,
                    description=hw.description,
                    due_date=hw.due_date,  # type: ignore[assignment]
                    section_count=hw.section_count,
                    created_at=hw.created_at,  # type: ignore[assignment]
                    is_overdue=hw.is_overdue,
                    roles=hw_data.roles,
                    expires_at=hw.expires_at,  # type: ignore[assignment]
                    is_hidden=hw.is_hidden,
                    is_accessible_to_students=hw.is_accessible_to_students,
                    is_draft=hw.is_draft,
                    is_scheduled=hw.is_scheduled,
                    publish_at=hw.publish_at,  # type: ignore[assignment]
                    sections=sections,
                    completed_percentage=completed_percentage,
                    in_progress_percentage=in_progress_percentage,
                    is_submitted=is_submitted,
                )
            )

        # Create and return the view data
        return HomeworkListData(
            homeworks=homeworks,
            user_types=user_types,
            total_count=len(homeworks),
            has_progress_data=has_progress_data,
        )


@dataclass
class HomeworkDetailData:
    """Data structure for the homework detail view."""

    id: UUID
    title: str
    description: str
    due_date: datetime | None
    created_by: UUID
    created_by_name: str
    created_at: datetime
    sections: list[SectionData]
    is_overdue: bool
    user_roles: list[
        str
    ]  # All roles this user has for this homework: ['teacher', 'student', 'teacher_assistant']
    can_edit: bool
    expires_at: datetime | None = None
    is_hidden: bool = False
    is_accessible_to_students: bool = True
    is_draft: bool = False
    is_scheduled: bool = False
    publish_at: datetime | None = None
    llm_config: Dict[str, Any] | None = None


@dataclass
class HomeworkFormData:
    """Data structure for the homework form view (create and edit)."""

    form: HomeworkCreateForm | HomeworkEditForm
    section_forms: "SectionFormSet"
    user_type: str
    action: str  # 'create' or 'edit'
    is_submitted: bool = False
    errors: Dict[str, Any] | None = None
    course_name: str = ""
    course_id: UUID | None = None
    publish_now_checked: bool = True


class HomeworkEditView(View):
    """View for editing an existing homework."""

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)

    def _can_teacher_edit_homework(self, teacher_profile, homework: Homework) -> bool:
        """
        Check if teacher can edit the homework.

        Teacher can edit if:
        1. They created the homework, OR
        2. They teach a course that has this homework assigned

        Args:
            teacher_profile: Teacher object
            homework: Homework object

        Returns:
            True if teacher can edit, False otherwise
        """
        # Check if teacher created it
        if homework.created_by == teacher_profile:
            return True

        # Check if teacher teaches the course that has this homework (direct FK now)
        if homework.course:
            teacher_courses = teacher_profile.courses.all()
            return homework.course in teacher_courses

        return False

    def get(self, request: TeacherRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display the edit form with existing data."""
        # Get the homework and check permissions
        try:
            homework = Homework.objects.get(id=homework_id)
            if not self._can_teacher_edit_homework(
                request.user.teacher_profile, homework
            ):
                return HttpResponseForbidden(
                    "You don't have permission to edit this homework."
                )
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect("homeworks:list")

        # Get view data with existing homework
        data = self._get_view_data(request, homework)
        return render(request, "homeworks/form.html", {"data": data})

    def post(self, request: TeacherRequest, homework_id: UUID) -> HttpResponse:
        """Handle POST requests to process the form submission."""
        # Get the homework and check permissions
        try:
            homework = Homework.objects.get(id=homework_id)
            if not self._can_teacher_edit_homework(
                request.user.teacher_profile, homework
            ):
                return HttpResponseForbidden(
                    "You don't have permission to edit this homework."
                )
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect("homeworks:list")

        # Process the form submission
        data = self._process_form_submission(request, homework)

        if data.is_submitted:
            messages.success(request, "Homework updated successfully!")
            if getattr(data.form, "expires_at_adjusted", False):
                messages.warning(
                    request,
                    "Note: the expiry date is set before the due date. Students will lose access before the homework is officially due.",
                )
            return redirect("homeworks:detail", homework_id=homework_id)

        return render(request, "homeworks/form.html", {"data": data})

    def _get_view_data(
        self, request: TeacherRequest, homework: Homework
    ) -> HomeworkFormData:
        """Prepare data for the form view with existing homework data."""
        # Create homework form with instance
        form = HomeworkEditForm(instance=homework)

        # Get existing sections for this homework
        sections = homework.sections.all().order_by("order")
        initial_section_data = []

        # Prepare initial data for section formset
        for section in sections:
            section_data = {
                "id": section.id,
                "title": section.title,
                "content": section.content,
                "order": section.order,
                "solution": section.solution.content if section.solution else "",
                "section_type": section.section_type,
            }
            initial_section_data.append(section_data)

        # Create section formset with initial data
        SectionFormset = cast(
            type[SectionFormSet],
            formset_factory(SectionForm, extra=0, formset=SectionFormSet),
        )
        section_formset = SectionFormset(
            prefix="sections", initial=initial_section_data
        )
        assert_type(section_formset, SectionFormSet)

        # Return form data
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type="teacher",
            action="edit",
            is_submitted=False,
            publish_now_checked=homework.publish_at is None,
        )

    def _process_form_submission(
        self, request: TeacherRequest, homework: Homework
    ) -> HomeworkFormData:
        """Process the form submission for updating a homework.

        The submit button name determines the publish action:
          name="save_draft"  → keep/set as draft
          name="publish"     → publish immediately or on schedule
        """
        is_draft_save = "save_draft" in request.POST

        # Draft save: bypass all validation, update only the raw text fields
        if is_draft_save:
            from .models import HomeworkType
            from django.utils.dateparse import parse_datetime

            homework.title = request.POST.get("title") or homework.title
            homework.description = request.POST.get("description") or homework.description
            update_fields = [
                "title",
                "description",
                "homework_type",
                "is_hidden",
                "updated_at",
            ]
            if "publish_now" in request.POST:
                homework.publish_at = None
                update_fields.append("publish_at")
            elif "publish_at" in request.POST:
                publish_at_value = request.POST.get("publish_at")
                publish_at = parse_datetime(publish_at_value) if publish_at_value else None
                if publish_at and timezone.is_naive(publish_at):
                    publish_at = timezone.make_aware(publish_at)
                homework.publish_at = publish_at
                update_fields.append("publish_at")
            homework.homework_type = HomeworkType.DRAFT
            homework.is_hidden = True
            homework.save(update_fields=update_fields)
            return HomeworkFormData(
                form=HomeworkEditForm(instance=homework),
                section_forms=None,  # type: ignore[arg-type]
                user_type="teacher",
                action="edit",
                is_submitted=True,
            )

        # Publish path: run full validation
        form = HomeworkEditForm(request.POST, instance=homework)

        # Create formset for sections
        SectionFormset = cast(
            type[SectionFormSet],
            formset_factory(SectionForm, extra=0, formset=SectionFormSet),
        )
        section_formset = SectionFormset(request.POST, prefix="sections")
        assert_type(section_formset, SectionFormSet)

        # Check form validity
        if form.is_valid() and section_formset.is_valid():
            from .models import HomeworkType

            publish_now = "publish_now" in request.POST
            homework_instance = form.save(commit=False)

            if publish_now:
                homework_instance.homework_type = HomeworkType.PUBLISHED
                homework_instance.is_hidden = False
                homework_instance.publish_at = None
            elif form.cleaned_data.get("publish_at"):
                homework_instance.homework_type = HomeworkType.SCHEDULED
                homework_instance.is_hidden = True
                homework_instance.publish_at = form.cleaned_data["publish_at"]
            # else: preserve existing homework_type / is_hidden / publish_at

            homework_instance.save()
            homework = homework_instance

            # Process sections
            sections_to_update = []
            sections_to_create = []
            sections_to_delete = []

            for section_form in section_formset:
                if not section_form.cleaned_data:
                    continue

                if section_form.cleaned_data.get("DELETE", False):
                    # Section marked for deletion
                    if section_form.cleaned_data.get("id"):
                        sections_to_delete.append(section_form.cleaned_data["id"])

            for section_form in normalize_section_formset_orders(section_formset):
                # Get section data
                section_data = {
                    "title": section_form.cleaned_data["title"],
                    "content": section_form.cleaned_data["content"],
                    "order": section_form.cleaned_data["order"],
                    "solution": section_form.cleaned_data["solution"],
                    "section_type": section_form.cleaned_data.get(
                        "section_type", "conversation"
                    ),
                }

                if section_form.cleaned_data.get("id"):
                    # Existing section to update
                    section_data["id"] = section_form.cleaned_data["id"]
                    sections_to_update.append(section_data)
                else:
                    # New section to create
                    sections_to_create.append(
                        SectionCreateData(
                            title=section_data["title"],
                            content=section_data["content"],
                            order=section_data["order"],
                            solution=section_data["solution"],
                            section_type=section_data["section_type"],
                        )
                    )

            # Create update data
            update_data = HomeworkUpdateData(
                title=homework.title,
                description=homework.description,
                due_date=homework.due_date,  # type: ignore[assignment]
                llm_config=homework.llm_config.id if homework.llm_config else None,
                sections_to_update=sections_to_update,
                sections_to_create=sections_to_create,
                sections_to_delete=sections_to_delete,
            )

            # Update homework using service
            result = HomeworkService.update_homework(homework.id, update_data)

            if result.success:
                # Return success data
                return HomeworkFormData(
                    form=form,
                    section_forms=section_formset,
                    user_type="teacher",
                    action="edit",
                    is_submitted=True,
                )
            else:
                # Service error
                messages.error(request, f"Error updating homework: {result.error}")

        # Form validation error or service error
        errors: dict[str, ErrorDict | list[ErrorList]] = {}
        if form.errors:
            errors["homework"] = form.errors
        if section_formset.errors:
            errors["sections"] = section_formset.errors
        if section_formset.non_form_errors():
            errors["formset"] = [section_formset.non_form_errors()]

        # Return form data with errors
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            user_type="teacher",
            action="edit",
            is_submitted=False,
            errors=errors,
        )


class HomeworkDetailView(View):
    """
    View for displaying and editing a homework assignment.

    For teachers: Shows the homework with editing capabilities
    For students: Shows the homework with links to start working
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display homework detail."""
        # Get the appropriate data based on user type
        data = self._get_view_data(request.user, homework_id)

        # If homework not found, redirect to list view
        if data is None:
            return redirect("homeworks:list")

        # Render the template with the data
        return render(request, "homeworks/detail.html", {"data": data})

    def post(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle POST requests for homework actions (like deletion or publishing)."""
        action = request.POST.get("action")

        if action == "delete":
            return self._handle_delete(request, homework_id)

        if action == "publish_now":
            return self._handle_publish_now(request, homework_id)

        # If no valid action, redirect to detail view
        return redirect("homeworks:detail", homework_id=homework_id)

    def _handle_publish_now(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Immediately publish a draft homework from the detail page."""
        teacher_profile = getattr(request.user, "teacher_profile", None)
        if not teacher_profile:
            return HttpResponseForbidden("Only teachers can publish homeworks.")

        try:
            homework = Homework.objects.get(id=homework_id)
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect("homeworks:list")

        # Check permission — must own or teach the course
        can_edit = homework.created_by == teacher_profile
        if not can_edit and homework.course:
            teacher_courses = teacher_profile.courses.all()
            can_edit = homework.course in teacher_courses

        if not can_edit:
            return HttpResponseForbidden("You don't have permission to publish this homework.")

        HomeworkService.publish_homework(homework_id)
        messages.success(request, f"'{homework.title}' has been published.")
        return redirect("homeworks:detail", homework_id=homework_id)

    def _handle_delete(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle homework deletion."""
        # Check if user is a teacher
        teacher_profile = getattr(request.user, "teacher_profile", None)
        if not teacher_profile:
            return HttpResponseForbidden("Only teachers can delete homeworks.")

        # Get the homework and check permissions
        try:
            from .models import Homework

            homework = Homework.objects.get(id=homework_id)

            # Check if teacher can delete (created it OR teaches the course that has it)
            created_by_teacher = homework.created_by == teacher_profile
            teaches_course_with_homework = False
            if homework.course:
                teacher_courses = teacher_profile.courses.all()
                teaches_course_with_homework = homework.course in teacher_courses

            if not (created_by_teacher or teaches_course_with_homework):
                return HttpResponseForbidden(
                    "You can only delete homeworks from courses you teach."
                )
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect("homeworks:list")

        # Delete the homework using the service
        success = HomeworkService.delete_homework(homework_id)

        if success:
            messages.success(
                request, f"Homework '{homework.title}' has been deleted successfully."
            )
        else:
            messages.error(request, "Failed to delete homework. Please try again.")

        return redirect("homeworks:list")

    def _get_view_data(self, user, homework_id: UUID) -> HomeworkDetailData | None:
        """
        Prepare data for the homework detail view based on user type.

        Args:
            user: The current user
            homework_id: The UUID of the homework to display

        Returns:
            HomeworkDetailData with homework details, or None if not found or access denied
        """
        # Determine user type
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)
        teacher_assistant_profile = getattr(user, "teacher_assistant_profile", None)

        # Get homework first
        homework = Homework.objects.filter(id=homework_id).first()
        if not homework:
            return None

        # Check access through any role
        user_roles = []

        # Teacher access
        if teacher_profile:
            if homework.created_by == teacher_profile:
                user_roles.append("teacher")
            elif homework.course:
                teacher_courses = teacher_profile.courses.all()
                if homework.course in teacher_courses:
                    user_roles.append("teacher")

        # Student access (must be enrolled)
        if student_profile and homework.course:
            enrolled_courses = student_profile.enrolled_courses.filter(
                courseenrollment__is_active=True
            )
            if homework.course in enrolled_courses:
                user_roles.append("student")

        # TA access (must be assigned to course)
        if teacher_assistant_profile and homework.course:
            if homework.course.is_teacher_assistant(teacher_assistant_profile):
                user_roles.append("teacher_assistant")

        if not user_roles:
            return None

        # Get homework details using service
        homework_detail = HomeworkService.get_homework_with_sections(homework_id)

        if homework_detail is None:
            return None

        # Only teachers can edit
        can_edit = "teacher" in user_roles

        # Format sections data
        sections = []

        # Get section progress for students
        section_progress_map = {}
        if "student" in user_roles:
            # Get the homework object for progress calculation
            try:
                homework_obj = Homework.objects.get(id=homework_id)
                progress_data = HomeworkService.get_student_homework_progress(
                    student_profile, homework_obj
                )
                # Create a map of section_id -> progress data for easy lookup
                for section_progress in progress_data.sections_progress:
                    section_progress_map[section_progress.id] = section_progress
            except Homework.DoesNotExist:
                pass

        if homework_detail.sections:
            for section_data in homework_detail.sections:
                # Get progress data for this section if available
                progress: SectionData | None = section_progress_map.get(section_data.id)

                sections.append(
                    SectionData(
                        id=section_data.id,
                        title=section_data.title,
                        content=section_data.content,
                        order=section_data.order,
                        solution_content=section_data.solution_content,
                        created_at=section_data.created_at,
                        updated_at=section_data.updated_at,
                        section_type=section_data.section_type,
                        status=progress.status if progress else None,
                        conversation_id=progress.conversation_id if progress else None,
                        answer_count=progress.answer_count if progress else 0,
                    )
                )

        # Get teacher name
        from accounts.models import Teacher

        teacher = Teacher.objects.filter(id=homework_detail.created_by).first()
        created_by_name = (
            f"{teacher.user.first_name} {teacher.user.last_name}".strip()
            if teacher
            else "Unknown Teacher"
        )

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
            is_overdue=homework_detail.due_date is not None and homework_detail.due_date < timezone.now(),
            user_roles=user_roles,
            can_edit=can_edit,
            expires_at=homework.expires_at,  # type: ignore[assignment]
            is_hidden=homework.is_hidden,
            is_accessible_to_students=homework.is_accessible_to_students,
            is_draft=homework.is_draft,
            is_scheduled=homework.is_scheduled,
            publish_at=homework.publish_at,  # type: ignore[assignment]
            llm_config={"id": homework_detail.llm_config}
            if homework_detail.llm_config
            else None,
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
    user_roles: list[
        str
    ]  # All roles this user has for this section: ['teacher', 'student', 'teacher_assistant']
    section_type: str = "conversation"
    conversations: list[Dict[str, Any]] | None = None
    submission: Dict[str, Any] | None = None
    existing_answers: list[Dict[str, Any]] | None = (
        None  # student's prior answers, newest first
    )


class SectionDetailView(View):
    """
    View for displaying individual sections with their conversations.

    For teachers: Shows the section with solution and test conversations
    For students: Shows the section with their conversations and submission
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(
        self, request: HttpRequest, homework_id: UUID, section_id: UUID
    ) -> HttpResponse:
        """Handle GET requests to display section detail."""
        # Get the homework and section
        try:
            homework = Homework.objects.get(id=homework_id)
            _section = Section.objects.get(id=section_id, homework=homework)
        except (Homework.DoesNotExist, Section.DoesNotExist):
            return redirect("homeworks:detail", homework_id=homework_id)

        # Check user access permissions
        teacher_profile = getattr(request.user, "teacher_profile", None)
        student_profile = getattr(request.user, "student_profile", None)
        teacher_assistant_profile = getattr(
            request.user, "teacher_assistant_profile", None
        )

        # Teacher must either own the homework OR teach the course that has it
        if teacher_profile:
            created_by_teacher = homework.created_by == teacher_profile

            # Check if teacher teaches the course that has this homework (direct FK now)
            teaches_course_with_homework = False
            if homework.course:
                teacher_courses = teacher_profile.courses.all()
                teaches_course_with_homework = homework.course in teacher_courses

            if not (created_by_teacher or teaches_course_with_homework):
                return HttpResponseForbidden("Access denied.")

        # For students, check if they're enrolled in the course that has this homework
        elif student_profile:
            if homework.course:
                is_enrolled = homework.course.is_student_enrolled(student_profile)
                if not is_enrolled:
                    return HttpResponseForbidden(
                        "Access denied. You are not enrolled in the course that has this homework."
                    )
            else:
                return HttpResponseForbidden(
                    "Access denied. This homework is not assigned to a course."
                )

        # For TAs, check if they're assigned to the course that has this homework
        elif teacher_assistant_profile:
            if homework.course:
                if not homework.course.is_teacher_assistant(teacher_assistant_profile):
                    return HttpResponseForbidden(
                        "Access denied. You are not assigned to this course as TA."
                    )
            else:
                return HttpResponseForbidden(
                    "Access denied. This homework is not assigned to a course."
                )

        # If user is neither teacher nor student nor TA, deny access
        else:
            return HttpResponseForbidden("Access denied.")

        # Get the appropriate data for the view
        data = self._get_view_data(request.user, homework_id, section_id)

        # If there was a problem getting the data, redirect to homework detail
        if data is None:
            return redirect("homeworks:detail", homework_id=homework_id)

        # Render the template with the data
        return render(request, "homeworks/section_detail.html", {"data": data})

    def _get_view_data(
        self, user, homework_id: UUID, section_id: UUID
    ) -> SectionDetailViewData | None:
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
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)
        teacher_assistant_profile = getattr(user, "teacher_assistant_profile", None)

        # Get homework and section
        try:
            homework = Homework.objects.get(id=homework_id)
            section = Section.objects.select_related("solution").get(
                id=section_id, homework=homework
            )
        except (Homework.DoesNotExist, Section.DoesNotExist):
            return None

        # Check access and determine roles
        user_roles = []

        if teacher_profile:
            if homework.created_by == teacher_profile:
                user_roles.append("teacher")
            elif homework.course:
                teacher_courses = teacher_profile.courses.all()
                if homework.course in teacher_courses:
                    user_roles.append("teacher")

        if student_profile and homework.course:
            enrolled_courses = student_profile.enrolled_courses.filter(
                courseenrollment__is_active=True
            )
            if homework.course in enrolled_courses:
                user_roles.append("student")

        if teacher_assistant_profile and homework.course:
            if homework.course.is_teacher_assistant(teacher_assistant_profile):
                user_roles.append("teacher_assistant")

        if not user_roles:
            return None

        # Gather conversations based on roles
        conversations = []
        submission = None

        if "teacher" in user_roles:
            # Teachers see test conversations they created
            teacher_conversations = (
                Conversation.objects.filter(
                    user=user, section=section, is_deleted=False
                )
                .select_related("user")
                .prefetch_related("messages")
            )

            for conv in teacher_conversations:
                conversations.append(
                    {
                        "id": conv.id,
                        "created_at": conv.created_at,
                        "updated_at": conv.updated_at,
                        "message_count": conv.message_count,
                        "is_test": True,
                        "role": "teacher",
                        "label": f"Test conversation {conv.created_at.strftime('%Y-%m-%d %H:%M')}",
                    }
                )

        existing_answers = None

        if "student" in user_roles:
            if section.section_type == Section.SECTION_TYPE_NON_INTERACTIVE:
                from conversations.models import SectionAnswer

                answers = SectionAnswer.objects.filter(user=user, section=section)
                existing_answers = [
                    {"answer": a.answer, "submitted_at": a.submitted_at}
                    for a in answers
                ]
            else:
                # Students see their active conversation and submission
                student_conversations = (
                    Conversation.objects.filter(
                        user=user, section=section, is_deleted=False
                    )
                    .select_related("user")
                    .prefetch_related("messages")
                )

                for conv in student_conversations:
                    conversations.append(
                        {
                            "id": conv.id,
                            "created_at": conv.created_at,
                            "updated_at": conv.updated_at,
                            "message_count": conv.message_count,
                            "is_test": False,
                            "role": "student",
                            "label": f"Conversation {conv.created_at.strftime('%Y-%m-%d %H:%M')}",
                        }
                    )

                # Get submission if exists
                student_submission = (
                    Submission.objects.filter(
                        conversation__user=user, conversation__section=section
                    )
                    .select_related("conversation")
                    .first()
                )

                if student_submission:
                    submission = {
                        "id": student_submission.id,
                        "conversation_id": student_submission.conversation.id,
                        "submitted_at": student_submission.submitted_at,
                    }

        if "teacher_assistant" in user_roles:
            # TAs see test conversations they created
            ta_conversations = (
                Conversation.objects.filter(
                    user=user, section=section, is_deleted=False
                )
                .select_related("user")
                .prefetch_related("messages")
            )

            for conv in ta_conversations:
                conversations.append(
                    {
                        "id": conv.id,
                        "created_at": conv.created_at,
                        "updated_at": conv.updated_at,
                        "message_count": conv.message_count,
                        "is_test": True,
                        "role": "teacher_assistant",
                        "label": f"Test conversation {conv.created_at.strftime('%Y-%m-%d %H:%M')}",
                    }
                )

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
            user_roles=user_roles,
            section_type=section.section_type,
            conversations=conversations if conversations else None,
            submission=submission,
            existing_answers=existing_answers,
        )


class HomeworkSubmissionsView(View):
    """
    View for displaying all student submissions for a homework assignment.

    Teacher or TA view that shows:
    - All students in the system (including those with no interactions)
    - For each student: all conversations in reverse chronological order
    - Submission status and warning indicators for non-participating students
    - Includes soft-deleted conversations
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest, homework_id: UUID) -> HttpResponse:
        """Handle GET requests to display homework submissions."""
        teacher_profile = getattr(request.user, "teacher_profile", None)
        teacher_assistant_profile = getattr(
            request.user, "teacher_assistant_profile", None
        )

        # Get the homework and check permissions
        try:
            homework = Homework.objects.get(id=homework_id)

            # Check if teacher can view submissions (created it OR teaches the course that has it)
            if teacher_profile:
                created_by_teacher = homework.created_by == teacher_profile
                teaches_course_with_homework = False
                if homework.course:
                    teacher_courses = teacher_profile.courses.all()
                    teaches_course_with_homework = homework.course in teacher_courses

                if not (created_by_teacher or teaches_course_with_homework):
                    return HttpResponseForbidden(
                        "You can only view submissions for homeworks from courses you teach."
                    )
            elif teacher_assistant_profile:
                # TA check - must be assigned to the course
                if homework.course:
                    if not homework.course.is_teacher_assistant(
                        teacher_assistant_profile
                    ):
                        return HttpResponseForbidden(
                            "You can only view submissions for courses you are assigned to as TA."
                        )
                else:
                    return HttpResponseForbidden(
                        "This homework is not assigned to a course."
                    )
            else:
                return HttpResponseForbidden("Access denied.")
        except Homework.DoesNotExist:
            messages.error(request, "Homework not found.")
            return redirect("homeworks:list")

        # Get submissions data using service
        submissions_data = HomeworkService.get_homework_submissions(homework_id)

        if submissions_data is None:
            logger.error(
                "get_homework_submissions returned None for homework %s", homework_id
            )
            messages.error(request, "Unable to load submissions data.")
            return redirect("homeworks:detail", homework_id=homework_id)

        # Render the template with the data
        return render(request, "homeworks/submissions.html", {"data": submissions_data})


@dataclass
class NonInteractiveSectionData:
    """Data for the non-interactive section answer page."""

    homework_id: UUID
    homework_title: str
    section_id: UUID
    section_title: str
    section_content: str
    section_order: int
    existing_answers: list[Dict[str, Any]]


class NonInteractiveSectionAnswerView(View):
    """
    Dedicated answer page for non-interactive sections.

    Students see the question and can submit written answers.
    No LLM or conversation involved.
    """

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(
        self, request: HttpRequest, homework_id: UUID, section_id: UUID
    ) -> HttpResponse:
        data = self._get_data(request, homework_id, section_id)
        if isinstance(data, HttpResponse):
            return data
        return render(request, "homeworks/non_interactive_answer.html", {"data": data})

    def _get_data(self, request: HttpRequest, homework_id: UUID, section_id: UUID):
        from conversations.models import SectionAnswer

        student_profile = getattr(request.user, "student_profile", None)
        if not student_profile:
            return HttpResponseForbidden("Only students can answer sections.")

        try:
            homework = Homework.objects.get(id=homework_id)
            section = Section.objects.get(id=section_id, homework=homework)
        except (Homework.DoesNotExist, Section.DoesNotExist):
            return redirect("homeworks:detail", homework_id=homework_id)

        if section.section_type != Section.SECTION_TYPE_NON_INTERACTIVE:
            return redirect(
                "homeworks:section_detail",
                homework_id=homework_id,
                section_id=section_id,
            )

        if not homework.course or not homework.course.is_student_enrolled(
            student_profile
        ):
            return HttpResponseForbidden("You are not enrolled in this course.")

        answers: list[dict[str, Any]] = [
            {"answer": answer["answer"], "submitted_at": answer["submitted_at"]}
            for answer in SectionAnswer.objects.filter(
                section=section, user=student_profile.user
            )
            .order_by("-submitted_at")
            .values("answer", "submitted_at")
        ]

        return NonInteractiveSectionData(
            homework_id=homework.id,
            homework_title=homework.title,
            section_id=section.id,
            section_title=section.title,
            section_content=section.content,
            section_order=section.order,
            existing_answers=answers,
        )
