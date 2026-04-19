"""
Views for the courses app.

This module provides views for browsing and enrolling in courses,
following the testable-first architecture with typed data contracts.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID
from django.views import View
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
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

from .enums import CourseRole
from .models import Course, CourseEnrollment, CourseTeacher, CourseTeacherAssistant
from .forms import CourseForm
from accounts.models import User, TeacherAssistant


@dataclass
class InstructorItem:
    """Data structure for an instructor in the course list."""

    first_name: str
    last_name: str


@dataclass
class CourseItem:
    """Data structure for a single course item in the list view."""

    id: UUID
    name: str
    code: str
    description: str
    roles: list[CourseRole]
    is_enrolled: bool
    instructors: list[InstructorItem]


@dataclass
class CourseListData:
    """Data structure for the course list view."""

    courses: list[CourseItem]
    user_types: list[CourseRole]


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

        # Track which user types this user has
        user_types = []
        if teacher_profile:
            user_types.append(CourseRole.TEACHER)
        if student_profile:
            user_types.append(CourseRole.STUDENT)
        if teacher_assistant_profile:
            user_types.append(CourseRole.TEACHER_ASSISTANT)

        # Aggregate courses from all roles
        course_dict = {}  # Use dict to deduplicate by course.id

        # Add teacher courses
        if teacher_profile:
            for course in teacher_profile.courses.all():
                if course.id not in course_dict:
                    course_dict[course.id] = {
                        "course": course,
                        "roles": [],
                        "is_enrolled": False,
                    }
                    course_dict[course.id]["roles"].append(CourseRole.TEACHER)

        # Add student courses
        if student_profile:
            for course in Course.objects.filter(is_active=True):
                if course.id not in course_dict:
                    course_dict[course.id] = {
                        "course": course,
                        "roles": [],
                        "is_enrolled": False,
                    }
                if course.is_student_enrolled(student_profile):
                    course_dict[course.id]["roles"].append(CourseRole.STUDENT)
                    course_dict[course.id]["is_enrolled"] = True

        # Add TA courses
        if teacher_assistant_profile:
            for course in teacher_assistant_profile.courses.all():
                if course.id not in course_dict:
                    course_dict[course.id] = {
                        "course": course,
                        "roles": [],
                        "is_enrolled": False,
                    }
                course_dict[course.id]["roles"].append(CourseRole.TEACHER_ASSISTANT)

        # Convert to CourseItem list
        courses = []
        for course_data in sorted(course_dict.values(), key=lambda x: x["course"].name):
            course = course_data["course"]

            # Get instructors for this course (sorted alphabetically by last_name, first_name)
            instructors = []
            for course_teacher in CourseTeacher.objects.filter(
                course=course
            ).select_related("teacher__user"):
                user = course_teacher.teacher.user
                instructors.append(
                    InstructorItem(
                        first_name=user.first_name,
                        last_name=user.last_name,
                    )
                )

            # Sort instructors alphabetically by last_name, then first_name
            instructors.sort(key=lambda x: (x.last_name.lower(), x.first_name.lower()))

            courses.append(
                CourseItem(
                    id=course.id,
                    name=course.name,
                    code=course.code,
                    description=course.description,
                    roles=course_data["roles"],
                    is_enrolled=course_data["is_enrolled"],
                    instructors=instructors,
                )
            )

        return CourseListData(courses=courses, user_types=user_types)


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

        # Redirect back to course detail
        return redirect("courses:detail", course_id=course.id)


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
    user_roles: list[CourseRole]
    instructors: list[InstructorItem]
    is_enrolled: bool


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

        # Check access through any role
        user_roles: list[CourseRole] = []

        if (
            teacher_profile
            and CourseTeacher.objects.filter(
                course=course, teacher=teacher_profile
            ).exists()
        ):
            user_roles.append(CourseRole.TEACHER)

        if student_profile:
            user_roles.append(CourseRole.STUDENT)

        if teacher_assistant_profile and course.is_teacher_assistant(
            teacher_assistant_profile
        ):
            user_roles.append(CourseRole.TEACHER_ASSISTANT)

        if (
            not course.is_active
            and CourseRole.TEACHER not in user_roles
            and CourseRole.TEACHER_ASSISTANT not in user_roles
        ):
            raise Http404

        # Get the appropriate data based on user roles
        data = self._get_view_data(
            course,
            user_roles,
            teacher_profile,
            student_profile,
            teacher_assistant_profile,
        )

        # Render the template with the data
        return render(request, "courses/detail.html", {"data": data})

    def _get_view_data(
        self,
        course: Course,
        user_roles: list[CourseRole],
        teacher_profile=None,
        student_profile=None,
        teacher_assistant_profile=None,
    ) -> CourseDetailData:
        """
        Prepare data for the course detail view.

        Args:
            course: The course to display
            user_roles: List of roles this user has for this course
            teacher_profile: Teacher profile if user is a teacher
            student_profile: Student profile if user is a student
            teacher_assistant_profile: Teacher assistant profile if user is a TA

        Returns:
            CourseDetailData with course info, homeworks, and optionally students/TAs
        """
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

        instructors = []
        for ct in CourseTeacher.objects.filter(course=course).select_related(
            "teacher__user"
        ):
            instructors.append(
                InstructorItem(
                    first_name=ct.teacher.user.first_name,
                    last_name=ct.teacher.user.last_name,
                )
            )

        is_enrolled = student_profile is not None and course.is_student_enrolled(
            student_profile
        )

        enrolled_students = None
        if (
            CourseRole.TEACHER in user_roles
            or CourseRole.TEACHER_ASSISTANT in user_roles
        ):
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

        teacher_assistants = None
        if (
            CourseRole.TEACHER in user_roles
            or CourseRole.TEACHER_ASSISTANT in user_roles
        ):
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
            user_roles=user_roles,
            instructors=instructors,
            is_enrolled=is_enrolled,
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
    available_llm_configs: Optional[List[dict]] = None


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

        form = HomeworkCreateForm(initial={"course": course}, course=course)

        SectionFormset = formset_factory(SectionForm, extra=1, formset=SectionFormSet)
        section_formset = SectionFormset(prefix="sections")

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
                            section_type=section_form.cleaned_data.get(
                                "section_type", "conversation"
                            ),
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


class CourseMatrixView(View):
    """
    Teacher-only view showing a matrix of students vs homeworks for a specific course.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        course = get_object_or_404(Course, id=course_id)

        if not CourseTeacher.objects.filter(
            course=course, teacher=request.user.teacher_profile
        ).exists():
            return HttpResponseForbidden("You do not have access to this course.")

        from homeworks.services import HomeworkService

        matrix_data = HomeworkService.get_course_homework_matrix(course_id)

        if matrix_data is None:
            messages.error(request, "Unable to load matrix data.")
            return redirect("courses:detail", course_id=course_id)

        return render(
            request,
            "homeworks/matrix.html",
            {"data": matrix_data, "course": course},
        )


class CourseMatrixExportView(View):
    """
    Teacher-only view that exports the course homework matrix as a CSV file.
    """

    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        import csv

        course = get_object_or_404(Course, id=course_id)

        if not CourseTeacher.objects.filter(
            course=course, teacher=request.user.teacher_profile
        ).exists():
            return HttpResponseForbidden("You do not have access to this course.")

        from homeworks.services import HomeworkService

        matrix_data = HomeworkService.get_course_homework_matrix(course_id)

        if matrix_data is None:
            messages.error(request, "Unable to load matrix data.")
            return redirect("courses:detail", course_id=course_id)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="homework_grades.csv"'

        writer = csv.writer(response)

        header = ["Student Name", "Student ID", "Student Email"]
        for hw_id, hw_title, hw_due_date in matrix_data.homeworks:
            header.append(hw_title)
        writer.writerow(header)

        for student_row in matrix_data.student_rows:
            row = [
                student_row.student_name_csv_format,
                "",
                student_row.student_email,
            ]
            for cell in student_row.homework_cells:
                if cell.total_sections > 0:
                    percentage = (cell.submitted_sections / cell.total_sections) * 100
                else:
                    percentage = 0
                row.append(f"{percentage:.0f}")
            writer.writerow(row)

        return response
