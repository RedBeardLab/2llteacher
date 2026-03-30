"""
Views for the courses app.

This module provides views for browsing and enrolling in courses,
following the testable-first architecture with typed data contracts.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID
from django.views import View
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib import messages

if TYPE_CHECKING:
    from homeworks.forms import HomeworkCreateForm, SectionFormSet

from llteacher.permissions.decorators import (
    student_required,
    StudentRequest,
    teacher_required,
    TeacherRequest,
)

from .models import Course, CourseEnrollment, CourseTeacher, CourseTeacherAssistant
from .forms import CourseForm
from accounts.models import User, TeacherAssistant


@dataclass
class CourseItem:
    """Data structure for a single course item in the list view."""

    id: UUID
    name: str
    code: str
    description: str
    is_enrolled: bool


@dataclass
class CourseListData:
    """Data structure for the course list view."""

    courses: list[CourseItem]
    user_type: str  # 'student', 'teacher', or 'unknown'


class CourseListView(View):
    """
    View for listing available courses.

    For students: Shows all active courses with enrollment status
    For teachers: Shows only courses they are teaching
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display course list."""
        # Get the appropriate data based on user type
        data = self._get_view_data(request.user)

        # Render the template with the data
        return render(request, "courses/list.html", {"data": data})

    def _get_view_data(self, user) -> CourseListData:
        """
        Prepare data for the course list view.

        Args:
            user: The current user (student, teacher, or teacher assistant)

        Returns:
            CourseListData with courses and enrollment/teaching status
        """
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)
        teacher_assistant_profile = getattr(user, "teacher_assistant_profile", None)

        courses = []
        user_type = "unknown"

        if teacher_profile:
            # For teachers, show only courses they are teaching
            user_type = "teacher"
            teacher_courses = teacher_profile.courses.all().order_by("name")

            for course in teacher_courses:
                courses.append(
                    CourseItem(
                        id=course.id,
                        name=course.name,
                        code=course.code,
                        description=course.description,
                        is_enrolled=False,  # Teachers don't enroll
                    )
                )

        elif student_profile:
            # For students, show all active courses
            user_type = "student"
            active_courses = Course.objects.filter(is_active=True).order_by("name")

            for course in active_courses:
                # Check if student is enrolled
                is_enrolled = course.is_student_enrolled(student_profile)

                courses.append(
                    CourseItem(
                        id=course.id,
                        name=course.name,
                        code=course.code,
                        description=course.description,
                        is_enrolled=is_enrolled,
                    )
                )

        elif teacher_assistant_profile:
            # For TAs, show courses they are assigned to
            user_type = "teacher_assistant"
            ta_courses = teacher_assistant_profile.courses.all().order_by("name")

            for course in ta_courses:
                courses.append(
                    CourseItem(
                        id=course.id,
                        name=course.name,
                        code=course.code,
                        description=course.description,
                        is_enrolled=False,  # TAs don't enroll
                    )
                )

        return CourseListData(courses=courses, user_type=user_type)


class CourseEnrollView(View):
    """
    View for enrolling in a course.

    Allows students to enroll in active courses.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(student_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in student."""
        return super().dispatch(*args, **kwargs)

    def post(self, request: StudentRequest, course_id: UUID) -> HttpResponse:
        """Handle POST requests to enroll in a course."""
        # Get the course and check if it's active
        course = get_object_or_404(Course, id=course_id)

        if not course.is_active:
            return HttpResponseForbidden("Cannot enroll in inactive course.")

        # Get student profile
        student_profile = request.user.student_profile

        # Check if enrollment already exists
        enrollment, created = CourseEnrollment.objects.get_or_create(
            course=course,
            student=student_profile,
            defaults={"is_active": True},
        )

        if not created:
            # Enrollment already exists, make sure it's active
            if not enrollment.is_active:
                enrollment.is_active = True
                enrollment.save()
                messages.success(request, f"Re-enrolled in {course.name} successfully!")
            else:
                messages.info(request, f"You are already enrolled in {course.name}.")
        else:
            messages.success(request, f"Enrolled in {course.name} successfully!")

        # Redirect back to course list
        return redirect("courses:list")


@dataclass
class CourseFormData:
    """Data structure for the course form view."""

    form: CourseForm
    action: str  # 'create' or 'edit'


class CourseCreateView(View):
    """
    View for creating a new course.

    Teacher-only view that allows creating courses and automatically
    assigns the teacher as the course owner.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: TeacherRequest) -> HttpResponse:
        """Handle GET requests to display the create form."""
        form = CourseForm()
        data = CourseFormData(form=form, action="create")

        return render(request, "courses/form.html", {"data": data})

    def post(self, request: TeacherRequest) -> HttpResponse:
        """Handle POST requests to process the form submission."""
        form = CourseForm(request.POST)

        if form.is_valid():
            # Save the course
            course = form.save()

            # Add the teacher as the owner
            CourseTeacher.objects.create(
                course=course,
                teacher=request.user.teacher_profile,
                role="owner",
            )

            messages.success(request, f"Course '{course.name}' created successfully!")
            return redirect("courses:list")

        # Form has errors, re-render with errors
        data = CourseFormData(form=form, action="create")
        return render(request, "courses/form.html", {"data": data})


@dataclass
class HomeworkItem:
    """Data structure for a homework item in the course detail view."""

    id: UUID
    title: str
    description: str
    due_date: str  # Formatted due date


@dataclass
class EnrolledStudentItem:
    """Data structure for an enrolled student in the course detail view."""

    id: UUID
    username: str
    email: str
    enrolled_at: str  # Formatted enrollment date


@dataclass
class TAItem:
    """Data structure for a teacher assistant in the course detail view."""

    id: UUID
    username: str
    email: str
    assigned_at: str  # Formatted assignment date


@dataclass
class CourseDetailData:
    """Data structure for the course detail view."""

    course_id: UUID
    course_name: str
    course_code: str
    course_description: str
    homeworks: list[HomeworkItem]
    enrolled_students: list[EnrolledStudentItem] | None
    teacher_assistants: list[TAItem] | None
    user_type: str  # 'student', 'teacher', or 'teacher_assistant'


class CourseDetailView(View):
    """
    View for viewing course details.

    For teachers: Shows course info, homeworks, and enrolled students
    For students: Shows course info and homeworks (only if enrolled)
    """

    @method_decorator(login_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest, course_id: UUID) -> HttpResponse:
        """Handle GET requests to display course detail."""
        # Get the course
        course = get_object_or_404(Course, id=course_id)

        # Check permissions and get data
        teacher_profile = getattr(request.user, "teacher_profile", None)
        student_profile = getattr(request.user, "student_profile", None)
        teacher_assistant_profile = getattr(
            request.user, "teacher_assistant_profile", None
        )

        # Check if user has access to this course
        has_access = False
        user_type = None

        if teacher_profile:
            # Check if teacher teaches this course
            has_access = CourseTeacher.objects.filter(
                course=course, teacher=teacher_profile
            ).exists()
            user_type = "teacher"
        elif student_profile:
            # Check if student is enrolled
            has_access = course.is_student_enrolled(student_profile)
            user_type = "student"
        elif teacher_assistant_profile:
            # Check if TA is assigned to this course
            has_access = course.is_teacher_assistant(teacher_assistant_profile)
            user_type = "teacher_assistant"

        if not has_access:
            return HttpResponseForbidden("You do not have access to this course.")

        # Get the appropriate data based on user type
        data = self._get_view_data(
            course,
            user_type,
            teacher_profile,
            student_profile,
            teacher_assistant_profile,
        )

        # Render the template with the data
        return render(request, "courses/detail.html", {"data": data})

    def _get_view_data(
        self,
        course: Course,
        user_type: str,
        teacher_profile=None,
        student_profile=None,
        teacher_assistant_profile=None,
    ) -> CourseDetailData:
        """
        Prepare data for the course detail view.

        Args:
            course: The course to display
            user_type: 'teacher', 'student', or 'teacher_assistant'
            teacher_profile: Teacher profile if user is a teacher
            student_profile: Student profile if user is a student
            teacher_assistant_profile: Teacher assistant profile if user is a TA

        Returns:
            CourseDetailData with course info, homeworks, and optionally students/TAs
        """
        # Get homeworks for this course (direct FK relationship)
        from homeworks.models import Homework

        course_homeworks = Homework.objects.filter(course=course).order_by("due_date")

        homeworks = []
        for hw in course_homeworks:
            homeworks.append(
                HomeworkItem(
                    id=hw.id,
                    title=hw.title,
                    description=hw.description,
                    due_date=hw.due_date.strftime("%B %d, %Y at %I:%M %p"),
                )
            )

        # Get enrolled students if user is a teacher
        enrolled_students = None
        if user_type == "teacher":
            enrollments = (
                CourseEnrollment.objects.filter(course=course, is_active=True)
                .select_related("student__user")
                .order_by("-enrolled_at")
            )

            enrolled_students = []
            for enrollment in enrollments:
                student = enrollment.student
                enrolled_students.append(
                    EnrolledStudentItem(
                        id=student.id,
                        username=student.user.username,
                        email=student.user.email,
                        enrolled_at=enrollment.enrolled_at.strftime("%B %d, %Y"),
                    )
                )

        # Get teacher assistants if user is a teacher
        teacher_assistants = None
        if user_type == "teacher":
            tas = (
                CourseTeacherAssistant.objects.filter(course=course)
                .select_related("teacher_assistant__user")
                .order_by("-assigned_at")
            )

            teacher_assistants = []
            for ta in tas:
                teacher_assistants.append(
                    TAItem(
                        id=ta.teacher_assistant.id,
                        username=ta.teacher_assistant.user.username,
                        email=ta.teacher_assistant.user.email,
                        assigned_at=ta.assigned_at.strftime("%B %d, %Y"),
                    )
                )

        return CourseDetailData(
            course_id=course.id,
            course_name=course.name,
            course_code=course.code,
            course_description=course.description,
            homeworks=homeworks,
            enrolled_students=enrolled_students,
            teacher_assistants=teacher_assistants,
            user_type=user_type,
        )


@dataclass
class HomeworkFormData:
    """Data structure for homework form view."""

    form: "HomeworkCreateForm"
    section_forms: "SectionFormSet"
    course_name: str
    course_id: UUID
    action: str  # 'create'
    is_submitted: bool


class CourseHomeworkCreateView(View):
    """
    View for creating a new homework for a specific course.

    Teachers can create homeworks that are automatically associated
    with the course they are teaching.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        """Handle GET requests to display the create form."""
        # Get course and check permissions
        course = get_object_or_404(Course, id=course_id)

        # Check if teacher teaches this course
        if not self._can_teacher_create_homework(request.user.teacher_profile, course):
            return HttpResponseForbidden(
                "You can only create homeworks for courses you teach."
            )

        data = self._get_view_data(request, course)
        return render(request, "courses/homework_form.html", {"data": data})

    def post(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        """Handle POST requests to process the form submission."""
        # Get course and check permissions
        course = get_object_or_404(Course, id=course_id)

        if not self._can_teacher_create_homework(request.user.teacher_profile, course):
            return HttpResponseForbidden(
                "You can only create homeworks for courses you teach."
            )

        data = self._process_form_submission(request, course)

        if data.is_submitted:
            messages.success(request, "Homework created successfully!")
            return redirect("courses:detail", course_id=course.id)

        return render(request, "courses/homework_form.html", {"data": data})

    def _can_teacher_create_homework(self, teacher_profile, course: Course) -> bool:
        """Check if teacher can create homework for this course."""
        teacher_courses = teacher_profile.courses.all()
        return course in teacher_courses

    def _get_view_data(
        self, request: TeacherRequest, course: Course
    ) -> HomeworkFormData:
        """Prepare data for the form view."""
        from homeworks.forms import HomeworkCreateForm, SectionForm, SectionFormSet
        from django.forms import formset_factory

        # Create homework form with course pre-populated
        form = HomeworkCreateForm(initial={"course": course})

        # Create empty section form (we'll start with one)
        SectionFormset = formset_factory(SectionForm, extra=1, formset=SectionFormSet)
        section_formset = SectionFormset(prefix="sections")

        # Return form data
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            course_name=course.name,
            course_id=course.id,
            action="create",
            is_submitted=False,
        )

    def _process_form_submission(
        self, request: TeacherRequest, course: Course
    ) -> HomeworkFormData:
        """Process the form submission."""
        from homeworks.forms import HomeworkCreateForm, SectionForm, SectionFormSet
        from homeworks.services import (
            HomeworkService,
            HomeworkCreateData,
            SectionCreateData,
        )
        from django.forms import formset_factory

        # Create a mutable copy of POST data and inject course
        post_data = request.POST.copy()
        post_data["course"] = course.id

        # Create forms from POST data
        form = HomeworkCreateForm(post_data)

        SectionFormset = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
        section_formset = SectionFormset(request.POST, prefix="sections")

        # Check form validity
        if form.is_valid() and section_formset.is_valid():
            # Extract homework data from form
            homework_data = HomeworkCreateData(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                due_date=form.cleaned_data["due_date"],
                course_id=course.id,
                sections=[],
                llm_config=form.cleaned_data["llm_config"].id
                if form.cleaned_data["llm_config"]
                else None,
            )

            # Extract sections data from formset
            section_data = []
            for section_form in section_formset.forms:
                if section_form.cleaned_data and not section_form.cleaned_data.get(
                    "DELETE", False
                ):
                    # Extract data from form
                    section_data.append(
                        SectionCreateData(
                            title=section_form.cleaned_data["title"],
                            content=section_form.cleaned_data["content"],
                            order=section_form.cleaned_data["order"],
                            solution=section_form.cleaned_data["solution"],
                        )
                    )

            # Add sections to homework data
            homework_data.sections = section_data

            # Use service to create homework with sections (course already included in data)
            result = HomeworkService.create_homework_with_sections(
                homework_data, request.user.teacher_profile
            )

            if result.success:
                # Return success data
                return HomeworkFormData(
                    form=form,
                    section_forms=section_formset,
                    course_name=course.name,
                    course_id=course.id,
                    action="create",
                    is_submitted=True,
                )
            else:
                # Service returned error
                messages.error(request, "Failed to create homework. Please try again.")

        # Form has errors, re-render with errors
        return HomeworkFormData(
            form=form,
            section_forms=section_formset,
            course_name=course.name,
            course_id=course.id,
            action="create",
            is_submitted=False,
        )


class CourseTAAssignView(View):
    """
    View for assigning a teacher assistant to a course.

    Teacher-only view that allows assigning existing TeacherAssistant
    profiles to the course.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)

    def post(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        """Handle POST requests to assign a TA to a course."""
        course = get_object_or_404(Course, id=course_id)

        # Check if teacher teaches this course
        if not self._is_course_teacher(request.user.teacher_profile, course):
            return HttpResponseForbidden(
                "You can only assign TAs to courses you teach."
            )

        # Get email from form
        ta_email = request.POST.get("ta_email")
        if not ta_email:
            messages.error(request, "TA email is required.")
            return redirect("courses:detail", course_id=course.id)

        # Find or create TeacherAssistant profile
        try:
            ta_user = User.objects.get(email=ta_email)
        except User.DoesNotExist:
            messages.error(request, f"No user found with email {ta_email}.")
            return redirect("courses:detail", course_id=course.id)

        # Get or create TeacherAssistant profile
        teacher_assistant, created = TeacherAssistant.objects.get_or_create(
            user=ta_user
        )

        # Check if already assigned
        if CourseTeacherAssistant.objects.filter(
            course=course, teacher_assistant=teacher_assistant
        ).exists():
            messages.info(request, f"{ta_email} is already a TA in this course.")
            return redirect("courses:detail", course_id=course.id)

        # Assign TA to course
        CourseTeacherAssistant.objects.create(
            course=course,
            teacher_assistant=teacher_assistant,
        )

        messages.success(request, f"{ta_email} has been assigned as TA!")
        return redirect("courses:detail", course_id=course.id)

    def _is_course_teacher(self, teacher_profile, course: Course) -> bool:
        """Check if teacher is associated with this course."""
        return CourseTeacher.objects.filter(
            course=course, teacher=teacher_profile
        ).exists()


class CourseTARemoveView(View):
    """
    View for removing a teacher assistant from a course.

    Teacher-only view that allows removing TAs from the course.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        """Ensure user is a logged-in teacher."""
        return super().dispatch(*args, **kwargs)

    def post(
        self, request: TeacherRequest, course_id: UUID, ta_id: UUID
    ) -> HttpResponse:
        """Handle POST requests to remove a TA from a course."""
        course = get_object_or_404(Course, id=course_id)

        # Check if teacher teaches this course
        if not self._is_course_teacher(request.user.teacher_profile, course):
            return HttpResponseForbidden(
                "You can only remove TAs from courses you teach."
            )

        # Find and delete the assignment
        try:
            ta_assignment = CourseTeacherAssistant.objects.get(
                course=course,
                teacher_assistant_id=ta_id,
            )
            ta_assignment.delete()
            messages.success(request, "TA has been removed from the course.")
        except CourseTeacherAssistant.DoesNotExist:
            messages.error(request, "TA assignment not found.")

        return redirect("courses:detail", course_id=course.id)

    def _is_course_teacher(self, teacher_profile, course: Course) -> bool:
        """Check if teacher is associated with this course."""
        return CourseTeacher.objects.filter(
            course=course, teacher=teacher_profile
        ).exists()
