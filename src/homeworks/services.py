"""
Homework Service

This module provides services for managing homework assignments and their sections.
Following a testable-first approach with typed data contracts.
"""

from dataclasses import dataclass
from typing import Any, List
from uuid import UUID
from enum import Enum, StrEnum
from datetime import datetime
import logging

from django.db import transaction
from llteacher.tracing import traced, record_exception

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accounts.models import Teacher, Student
    from .models import Homework

logger = logging.getLogger(__name__)


class SectionStatus(str, Enum):
    """Enumeration of possible section status values."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IN_PROGRESS_OVERDUE = "in_progress_overdue"
    SUBMITTED = "submitted"
    OVERDUE = "overdue"


class ParticipationStatus(StrEnum):
    """Enumeration of possible student participation status values."""

    NO_INTERACTION = "no_interaction"
    PARTIAL = "partial"
    ACTIVE = "active"


# Data Contracts
@dataclass
class SectionCreateData:
    title: str
    content: str
    order: int
    solution: str | None = None


@dataclass
class HomeworkCreateData:
    title: str
    sections: list[SectionCreateData]
    course_id: UUID  # Required - every homework belongs to a course
    description: str = ""
    due_date: Any | None = None  # datetime; None allowed for drafts
    llm_config: UUID | None = None
    homework_type: str = "published"
    publish_at: Any | None = None  # datetime


@dataclass
class HomeworkCreateResult:
    homework_id: UUID
    section_ids: list[UUID]
    success: bool = True
    error: str | None = None


@dataclass
class SectionData:
    """Unified data structure for section information used across services and views."""

    id: UUID
    title: str
    content: str
    order: int
    solution_content: str | None
    created_at: datetime
    updated_at: datetime
    # Progress tracking fields (available when progress is calculated)
    status: SectionStatus | None = None
    conversation_id: UUID | None = None

    @property
    def has_solution(self) -> bool:
        """Check if section has a solution."""
        return self.solution_content is not None


@dataclass
class HomeworkProgressData:
    homework_id: UUID
    sections_progress: list[SectionData]


# Missing data contracts that need to be defined
@dataclass
class HomeworkDetailData:
    """Data contract for detailed homework information including sections"""

    id: UUID
    title: str
    description: str
    due_date: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    llm_config: UUID | None = None
    sections: list[SectionData] | None = None


@dataclass
class HomeworkUpdateData:
    """Data contract for updating homework"""

    title: str | None = None
    description: str | None = None
    due_date: Any | None = None  # datetime
    llm_config: UUID | None = None
    sections_to_update: list[Any] | None = None  # Will be defined with proper type
    sections_to_create: list[SectionCreateData] | None = None
    sections_to_delete: list[UUID] | None = None
    homework_type: str | None = None
    publish_at: Any | None = None  # datetime


@dataclass
class HomeworkUpdateResult:
    """Result of updating a homework assignment"""

    success: bool = True
    error: str | None = None
    homework_id: UUID | None = None
    updated_section_ids: list[UUID] | None = None
    created_section_ids: list[UUID] | None = None
    deleted_section_ids: list[UUID] | None = None


# New data contracts for submissions view
@dataclass
class StudentConversationData:
    """Data structure for a student's conversation in the submissions view."""

    conversation_id: UUID
    section_title: str
    section_order: int
    created_at: datetime
    updated_at: datetime
    message_count: int
    is_submitted: bool
    is_deleted: bool
    submission_date: datetime | None
    paste_event_count: int = 0


@dataclass
class StudentSectionStatus:
    """Data structure for a student's status on a specific section."""

    section_id: UUID
    section_title: str
    section_order: int
    has_conversation: bool
    conversations: list[
        StudentConversationData
    ]  # All conversations for this section, sorted chronologically
    is_missing: bool  # True if student has no conversations for this section
    latest_conversation_date: datetime | None
    submission_count: int  # Number of submitted conversations for this section


@dataclass
class StudentSubmissionSummary:
    """Data structure for a student's overall submission summary."""

    student_id: UUID
    student_name: str
    student_username: str
    student_email: str
    has_interactions: bool
    section_statuses: list[
        StudentSectionStatus
    ]  # All sections, ordered by section number
    total_conversations: int
    submitted_count: int
    sections_started: int
    missing_sections: int  # Number of sections with no conversations
    last_activity: datetime | None
    participation_status: ParticipationStatus


@dataclass
class HomeworkSubmissionsData:
    """Data structure for the homework submissions view."""

    homework_id: UUID
    homework_title: str
    homework_due_date: datetime | None
    total_sections: int
    students: list[StudentSubmissionSummary]
    total_students: int
    active_students: int
    inactive_students: int
    total_submissions: int


# Data contracts for matrix view
@dataclass
class HomeworkMatrixCell:
    """Represents a cell in the matrix (student x homework intersection)."""

    homework_id: UUID
    student_id: UUID
    status: SectionStatus
    submitted_sections: int
    total_sections: int
    completion_percentage: int
    last_activity: datetime | None
    total_conversations: int


@dataclass
class StudentMatrixRow:
    """Represents a student row in the matrix."""

    student_id: UUID
    student_name: str
    student_first_name: str
    student_last_name: str
    student_email: str
    homework_cells: list[HomeworkMatrixCell]
    total_submissions: int
    total_homeworks: int
    overall_completion_percentage: int

    @property
    def student_name_csv_format(self) -> str:
        """Return student name in 'LastName, FirstName' format for CSV export."""
        if self.student_last_name and self.student_first_name:
            return f"{self.student_last_name}, {self.student_first_name}"
        elif self.student_last_name:
            return self.student_last_name
        elif self.student_first_name:
            return self.student_first_name
        else:
            return self.student_name  # Fallback to display name


@dataclass
class HomeworkMatrixData:
    """Complete matrix data structure."""

    homeworks: list[tuple[UUID, str, datetime]]  # (id, title, due_date)
    student_rows: list[StudentMatrixRow]
    total_students: int
    total_homeworks: int
    total_submissions: int


class HomeworkService:
    """
    Service class for homework-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """

    @staticmethod
    @traced
    def create_homework_with_sections(
        data: HomeworkCreateData, teacher: "Teacher"
    ) -> HomeworkCreateResult:
        """
        Create a new homework assignment with multiple sections.

        Args:
            data: Typed data object containing homework details
            teacher: Teacher object who is creating the homework

        Returns:
            HomeworkCreateResult object with operation results
        """
        from .models import Homework, Section, SectionSolution

        # Validate data
        if not data.title.strip():
            return HomeworkCreateResult(
                homework_id=None,  # type: ignore
                section_ids=[],
                success=False,
                error="Title cannot be empty",
            )

        try:
            with transaction.atomic():
                # Create homework — draft type implies is_hidden=True
                is_draft = data.homework_type == "draft"
                homework = Homework.objects.create(
                    title=data.title,
                    description=data.description,
                    due_date=data.due_date,
                    created_by=teacher,
                    course_id=data.course_id,
                    llm_config_id=data.llm_config,
                    homework_type=data.homework_type,
                    publish_at=data.publish_at,
                    is_hidden=is_draft,
                )

                # Create sections
                section_ids: list[UUID] = []
                for section_data in data.sections:
                    # Create section
                    section = Section.objects.create(
                        homework=homework,
                        title=section_data.title,
                        content=section_data.content,
                        order=section_data.order,
                    )

                    # Create solution if provided
                    if section_data.solution:
                        solution = SectionSolution.objects.create(
                            content=section_data.solution
                        )
                        section.solution = solution
                        section.save()

                    section_ids.append(section.id)

                return HomeworkCreateResult(
                    homework_id=homework.id, section_ids=section_ids
                )
        except Exception as e:
            record_exception(e)
            return HomeworkCreateResult(
                homework_id=None,  # type: ignore
                section_ids=[],
                success=False,
                error=str(e),
            )

    @staticmethod
    def publish_homework(homework_id: UUID) -> HomeworkUpdateResult:
        """Immediately publish a draft homework.

        Sets is_hidden=False, homework_type='published', publish_at=None.
        is_hidden is the access-control source of truth.
        """
        from .models import Homework, HomeworkType

        try:
            homework = Homework.objects.get(id=homework_id)
            homework.is_hidden = False
            homework.homework_type = HomeworkType.PUBLISHED
            homework.publish_at = None
            homework.save(
                update_fields=["is_hidden", "homework_type", "publish_at", "updated_at"]
            )
            return HomeworkUpdateResult(success=True, homework_id=homework_id)
        except Homework.DoesNotExist:
            return HomeworkUpdateResult(success=False, error="Homework not found")
        except Exception as e:
            record_exception(e)
            return HomeworkUpdateResult(success=False, error=str(e))

    @staticmethod
    def auto_publish_due_drafts() -> int:
        """Bulk-publish all drafts whose publish_at has passed.

        Updates is_hidden=False, homework_type='published', publish_at=None.
        Returns the count of homeworks published.
        Called lazily on page load — no background worker required.
        """
        from django.utils import timezone
        from .models import Homework, HomeworkType

        try:
            count = Homework.objects.filter(
                homework_type=HomeworkType.DRAFT,
                publish_at__lte=timezone.now(),
            ).update(
                is_hidden=False,
                homework_type=HomeworkType.PUBLISHED,
                publish_at=None,
            )
            if count:
                logger.info("Auto-published %d draft homework(s)", count)
            return count
        except Exception as e:
            record_exception(e)
            logger.error("auto_publish_due_drafts failed: %s", e)
            return 0

    @staticmethod
    @traced
    def get_student_homework_progress(
        student: "Student", homework: "Homework"
    ) -> HomeworkProgressData:
        """
        Get a student's progress on a specific homework assignment.

        Args:
            student: Student object
            homework: Homework object

        Returns:
            HomeworkProgressData with progress information
        """
        # Import here to avoid circular imports
        from conversations.models import Submission, Conversation

        sections = homework.sections.select_related("solution").order_by("order")
        progress_items: list[SectionData] = []

        for section in sections:
            try:
                # Check if student has submitted this section
                submission = Submission.objects.filter(
                    conversation__user=student.user,
                    conversation__section=section,
                    conversation__is_deleted=False,
                ).first()

                if submission:
                    status: SectionStatus = SectionStatus.SUBMITTED
                    conversation_id: UUID | None = submission.conversation.id
                else:
                    # Check if student has started working (has conversations)
                    conversation = Conversation.objects.filter(
                        user=student.user, section=section, is_deleted=False
                    ).first()

                    if conversation:
                        # Student has started working
                        if homework.is_overdue:
                            status = (
                                SectionStatus.IN_PROGRESS_OVERDUE
                            )  # Started but overdue
                        else:
                            status = SectionStatus.IN_PROGRESS  # Started and on time
                        conversation_id = conversation.id
                    else:
                        # Student hasn't started
                        if homework.is_overdue:
                            status = SectionStatus.OVERDUE  # Never started and overdue
                        else:
                            status = (
                                SectionStatus.NOT_STARTED
                            )  # Never started, still time
                        conversation_id = None
            except Exception as e:
                logger.exception("Error determining section status")
                record_exception(e)
                status = SectionStatus.NOT_STARTED
                conversation_id = None

            # Create progress data for this section with complete section information
            progress_items.append(
                SectionData(
                    id=section.id,
                    title=section.title,
                    content=section.content,
                    order=section.order,
                    solution_content=section.solution.content
                    if section.solution
                    else None,
                    created_at=section.created_at,
                    updated_at=section.updated_at,
                    status=status,
                    conversation_id=conversation_id,
                )
            )

        # Create and return the overall progress data
        return HomeworkProgressData(
            homework_id=homework.id, sections_progress=progress_items
        )

    @staticmethod
    @traced
    def get_homework_with_sections(homework_id: UUID) -> HomeworkDetailData | None:
        """
        Get detailed homework data with all its sections.

        Args:
            homework_id: UUID of the homework to retrieve

        Returns:
            HomeworkDetailData if found, None otherwise
        """
        from .models import Homework

        try:
            # Get homework with optimized query using select_related and prefetch_related
            homework = (
                Homework.objects.select_related("created_by", "llm_config")
                .prefetch_related("sections__solution")
                .get(id=homework_id)
            )

            # Prepare sections data
            sections: List[SectionData] = []
            for section in homework.sections.order_by("order"):
                section_data = SectionData(
                    id=section.id,
                    title=section.title,
                    content=section.content,
                    order=section.order,
                    solution_content=section.solution.content
                    if section.solution
                    else None,
                    created_at=section.created_at,
                    updated_at=section.updated_at,
                )
                sections.append(section_data)

            # Create and return the detailed data
            return HomeworkDetailData(
                id=homework.id,
                title=homework.title,
                description=homework.description,
                due_date=homework.due_date,
                created_by=homework.created_by.id,
                created_at=homework.created_at,
                updated_at=homework.updated_at,
                llm_config=homework.llm_config.id if homework.llm_config else None,
                sections=sections,
            )
        except Homework.DoesNotExist:
            return None
        except Exception:
            return None

    @staticmethod
    @traced
    def get_all_homework_matrix(teacher_id: UUID) -> HomeworkMatrixData | None:
        """
        Get a matrix view of all students and all homeworks created by a teacher.

        Args:
            teacher_id: UUID of the teacher

        Returns:
            HomeworkMatrixData with complete matrix information, or None if error
        """
        from .models import Homework
        from accounts.models import Student, Teacher
        from conversations.models import Conversation, Submission

        try:
            # Get the teacher
            teacher = Teacher.objects.get(id=teacher_id)

            # Get all homeworks created by this teacher (oldest to newest)
            homeworks = (
                Homework.objects.filter(created_by=teacher)
                .order_by("created_at")
                .prefetch_related("sections")
            )

            # Get students enrolled in courses that have any of the teacher's homeworks assigned
            # Homework now has a direct FK to Course
            # Include students from inactive courses to show historical submissions
            enrolled_students = (
                Student.objects.filter(
                    enrolled_courses__homeworks__in=homeworks,
                )
                .select_related("user")
                .order_by("user__first_name", "user__last_name", "user__username")
                .distinct()
            )

            # Prepare homework list for matrix header
            homework_list: list[tuple[UUID, str, datetime]] = [
                (hw.id, hw.title, hw.due_date) for hw in homeworks
            ]

            # Get all conversations for these homeworks (excluding soft-deleted)
            conversations = (
                Conversation.objects.filter(
                    section__homework__in=homeworks, is_deleted=False
                )
                .select_related("user__student_profile", "section__homework")
                .prefetch_related("messages")
            )

            # Get all submissions
            submissions = Submission.objects.filter(
                conversation__section__homework__in=homeworks
            ).select_related("conversation__section__homework")

            # Create maps for quick lookup
            # Map: (student_id, homework_id) -> list of conversations
            student_homework_conversations: dict[
                tuple[UUID, UUID], list[Conversation]
            ] = {}
            # Map: conversation_id -> submission
            submission_map = {sub.conversation.id: sub for sub in submissions}

            # Populate conversation map
            for conv in conversations:
                student_id = conv.user.student_profile.id
                homework_id = conv.section.homework.id
                key = (student_id, homework_id)

                if key not in student_homework_conversations:
                    student_homework_conversations[key] = []
                student_homework_conversations[key].append(conv)

            # Build student rows
            student_rows = []
            total_submissions = 0

            for student in enrolled_students:
                homework_cells = []
                student_total_submissions = 0

                for homework in homeworks:
                    # Get conversations for this student-homework pair
                    convs = student_homework_conversations.get(
                        (student.id, homework.id), []
                    )

                    # Count submitted sections
                    submitted_sections = 0
                    total_conversations = len(convs)
                    last_activity = None

                    for conv in convs:
                        if conv.id in submission_map:
                            submitted_sections += 1
                            student_total_submissions += 1

                        # Track last activity
                        if last_activity is None or conv.updated_at > last_activity:
                            last_activity = conv.updated_at

                    # Get total sections for this homework
                    total_sections = homework.section_count

                    # Calculate completion percentage
                    completion_percentage = (
                        round((submitted_sections / total_sections) * 100)
                        if total_sections > 0
                        else 0
                    )

                    # Determine overall status for this homework
                    if submitted_sections == total_sections and total_sections > 0:
                        status = SectionStatus.SUBMITTED
                    elif submitted_sections > 0:
                        if homework.is_overdue:
                            status = SectionStatus.IN_PROGRESS_OVERDUE
                        else:
                            status = SectionStatus.IN_PROGRESS
                    elif total_conversations > 0:
                        if homework.is_overdue:
                            status = SectionStatus.IN_PROGRESS_OVERDUE
                        else:
                            status = SectionStatus.IN_PROGRESS
                    else:
                        if homework.is_overdue:
                            status = SectionStatus.OVERDUE
                        else:
                            status = SectionStatus.NOT_STARTED

                    # Create cell
                    homework_cells.append(
                        HomeworkMatrixCell(
                            homework_id=homework.id,
                            student_id=student.id,
                            status=status,
                            submitted_sections=submitted_sections,
                            total_sections=total_sections,
                            completion_percentage=completion_percentage,
                            last_activity=last_activity,
                            total_conversations=total_conversations,
                        )
                    )

                # Calculate overall completion percentage for student
                total_homeworks = len(homeworks)
                total_sections_all_homeworks = sum(hw.section_count for hw in homeworks)
                overall_completion = (
                    round(
                        (student_total_submissions / total_sections_all_homeworks) * 100
                    )
                    if total_sections_all_homeworks > 0
                    else 0
                )

                # Create student name
                student_name = (
                    f"{student.user.first_name} {student.user.last_name}".strip()
                )
                if not student_name:
                    student_name = student.user.username

                # Create student row
                student_rows.append(
                    StudentMatrixRow(
                        student_id=student.id,
                        student_name=student_name,
                        student_first_name=student.user.first_name,
                        student_last_name=student.user.last_name,
                        student_email=student.user.email,
                        homework_cells=homework_cells,
                        total_submissions=student_total_submissions,
                        total_homeworks=total_homeworks,
                        overall_completion_percentage=overall_completion,
                    )
                )

                total_submissions += student_total_submissions

            return HomeworkMatrixData(
                homeworks=homework_list,
                student_rows=student_rows,
                total_students=len(enrolled_students),
                total_homeworks=len(homeworks),
                total_submissions=total_submissions,
            )

        except Teacher.DoesNotExist:
            return None
        except Exception as e:
            logger.exception("Error getting homework matrix")
            record_exception(e)
            return None

    @staticmethod
    @traced
    def update_homework(
        homework_id: UUID, data: HomeworkUpdateData
    ) -> HomeworkUpdateResult:
        """
        Update a homework assignment and its sections.

        Args:
            homework_id: UUID of the homework to update
            data: Typed data object containing update information

        Returns:
            HomeworkUpdateResult with operation results
        """
        from .models import Homework, Section, SectionSolution

        try:
            with transaction.atomic():
                # Get the homework
                homework = Homework.objects.get(id=homework_id)

                # Update basic fields if provided
                if data.title is not None:
                    homework.title = data.title
                if data.description is not None:
                    homework.description = data.description
                if data.due_date is not None:
                    homework.due_date = data.due_date
                if data.llm_config is not None:
                    homework.llm_config_id = data.llm_config

                # Save homework changes
                homework.save()

                # Initialize tracking lists for sections
                updated_section_ids: List[UUID] = []
                created_section_ids: List[UUID] = []
                deleted_section_ids: List[UUID] = []

                # Delete sections if requested
                if data.sections_to_delete:
                    for section_id in data.sections_to_delete:
                        try:
                            section = Section.objects.get(
                                id=section_id, homework=homework
                            )
                            section.delete()
                            deleted_section_ids.append(section_id)
                        except Section.DoesNotExist:
                            pass  # Skip if section doesn't exist

                # Create new sections if requested
                if data.sections_to_create:
                    for section_data in data.sections_to_create:
                        # Create section
                        section = Section.objects.create(
                            homework=homework,
                            title=section_data.title,
                            content=section_data.content,
                            order=section_data.order,
                        )

                        # Create solution if provided
                        if section_data.solution:
                            solution = SectionSolution.objects.create(
                                content=section_data.solution
                            )
                            section.solution = solution
                            section.save()

                        created_section_ids.append(section.id)

                # Update existing sections if requested
                if data.sections_to_update:
                    for section_update in data.sections_to_update:
                        try:
                            section = Section.objects.get(
                                id=section_update.get("id"), homework=homework
                            )

                            # Update section fields
                            if "title" in section_update:
                                section.title = section_update["title"]
                            if "content" in section_update:
                                section.content = section_update["content"]
                            if "order" in section_update:
                                section.order = section_update["order"]

                            # Update solution if provided
                            if "solution" in section_update:
                                solution_content = section_update["solution"]
                                if solution_content:
                                    # Create or update solution
                                    if section.solution:
                                        section.solution.content = solution_content
                                        section.solution.save()
                                    else:
                                        solution = SectionSolution.objects.create(
                                            content=solution_content
                                        )
                                        section.solution = solution
                                else:
                                    # Remove solution
                                    if section.solution:
                                        section.solution.delete()
                                        section.solution = None

                            section.save()
                            updated_section_ids.append(section.id)
                        except Section.DoesNotExist:
                            pass  # Skip if section doesn't exist

                # Return success result with tracking information
                return HomeworkUpdateResult(
                    success=True,
                    homework_id=homework.id,
                    updated_section_ids=updated_section_ids,
                    created_section_ids=created_section_ids,
                    deleted_section_ids=deleted_section_ids,
                )
        except Homework.DoesNotExist:
            return HomeworkUpdateResult(
                success=False, error=f"Homework with id {homework_id} not found"
            )
        except Exception as e:
            record_exception(e)
            return HomeworkUpdateResult(success=False, error=str(e))

    @staticmethod
    @traced
    def delete_homework(homework_id: UUID) -> bool:
        """
        Delete a homework and all related sections.

        Args:
            homework_id: UUID of the homework to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        from .models import Homework

        try:
            homework = Homework.objects.get(id=homework_id)
            homework.delete()  # This will cascade delete all sections and solutions
            return True
        except Homework.DoesNotExist:
            return False
        except Exception as e:
            logger.exception("Error deleting homework %s", homework_id)
            record_exception(e)
            return False

    @staticmethod
    @traced
    def get_homework_submissions(homework_id: UUID) -> HomeworkSubmissionsData | None:
        """
        Get all student submissions for a homework, including students with no interactions.
        Shows section-by-section breakdown with conversations sorted by section order first, then chronologically.

        Args:
            homework_id: UUID of the homework to get submissions for

        Returns:
            HomeworkSubmissionsData with all students and their section-by-section interactions, or None if homework not found
        """
        from .models import Homework
        from accounts.models import Student
        from conversations.models import Conversation, Submission, PasteEvent

        try:
            # Get the homework with sections ordered by section order
            homework = (
                Homework.objects.select_related("created_by")
                .prefetch_related("sections")
                .get(id=homework_id)
            )

            # Get all sections for this homework, ordered by section order
            homework_sections = list(homework.sections.order_by("order"))

            # Get students enrolled in the course that has this homework assigned
            # Homework now has a direct FK to Course
            # Include students from inactive enrollments to show historical submissions
            enrolled_students = (
                Student.objects.filter(
                    enrolled_courses=homework.course,
                )
                .select_related("user")
                .distinct()
            )

            # Get all conversations for this homework (including soft-deleted ones)
            conversations = (
                Conversation.objects.filter(section__homework=homework)
                .select_related("user__student_profile", "section")
                .prefetch_related("messages")
            )

            # Get all submissions for this homework
            submissions = Submission.objects.filter(
                conversation__section__homework=homework
            ).select_related("conversation")

            # Create a map of conversation_id -> submission for quick lookup
            submission_map = {sub.conversation.id: sub for sub in submissions}

            # Get all paste events for conversations in this homework
            paste_events = PasteEvent.objects.filter(
                last_message_before_paste__conversation__section__homework=homework
            ).select_related("last_message_before_paste__conversation")

            # Create a map of conversation_id -> paste event count for quick lookup
            from collections import defaultdict

            paste_event_count_map: defaultdict[UUID, int] = defaultdict(int)
            for paste_event in paste_events:
                if paste_event.last_message_before_paste:
                    conv_id = paste_event.last_message_before_paste.conversation.id
                    paste_event_count_map[conv_id] += 1

            # Group conversations by student and section
            student_section_conversations_map: dict[
                UUID, dict[UUID, list[Conversation]]
            ] = {}
            for conv in conversations:
                student_profile = getattr(conv.user, "student_profile", None)
                if student_profile is None:
                    logger.warning(
                        "Skipping conversation %s: user %s has no student_profile (homework %s)",
                        conv.id,
                        conv.user.id,
                        homework_id,
                    )
                    continue
                student_id = student_profile.id
                section_id = conv.section.id

                if student_id not in student_section_conversations_map:
                    student_section_conversations_map[student_id] = {}
                if section_id not in student_section_conversations_map[student_id]:
                    student_section_conversations_map[student_id][section_id] = []

                student_section_conversations_map[student_id][section_id].append(conv)

            # Create student summaries
            student_summaries = []
            total_submissions = 0
            active_students = 0

            for student in enrolled_students:
                student_conversations = student_section_conversations_map.get(
                    student.id, {}
                )

                # Create section statuses for all sections
                section_statuses = []
                total_conversations = 0
                submitted_count = 0
                sections_started = 0
                missing_sections = 0
                last_activity = None

                for section in homework_sections:
                    section_conversations = student_conversations.get(section.id, [])
                    has_conversation = len(section_conversations) > 0

                    if not has_conversation:
                        missing_sections += 1
                    else:
                        sections_started += 1

                    # Process conversations for this section
                    conversation_data = []
                    section_submissions = 0
                    latest_conversation_date = None

                    for conv in section_conversations:
                        total_conversations += 1

                        # Check if this conversation has a submission
                        submission = submission_map.get(conv.id)
                        is_submitted = submission is not None
                        if is_submitted:
                            section_submissions += 1
                            submitted_count += 1
                            total_submissions += 1

                        # Track latest conversation date for this section
                        if (
                            latest_conversation_date is None
                            or conv.updated_at > latest_conversation_date
                        ):
                            latest_conversation_date = conv.updated_at

                        # Track overall last activity
                        if last_activity is None or conv.updated_at > last_activity:
                            last_activity = conv.updated_at

                        conversation_data.append(
                            StudentConversationData(
                                conversation_id=conv.id,
                                section_title=conv.section.title,
                                section_order=conv.section.order,
                                created_at=conv.created_at,
                                updated_at=conv.updated_at,
                                message_count=conv.message_count,
                                is_submitted=is_submitted,
                                is_deleted=conv.is_deleted,
                                submission_date=submission.submitted_at
                                if submission
                                else None,
                                paste_event_count=paste_event_count_map.get(conv.id, 0),
                            )
                        )

                    # Sort conversations within this section chronologically (newest first)
                    conversation_data.sort(key=lambda x: x.created_at, reverse=True)

                    # Create section status
                    section_statuses.append(
                        StudentSectionStatus(
                            section_id=section.id,
                            section_title=section.title,
                            section_order=section.order,
                            has_conversation=has_conversation,
                            conversations=conversation_data,
                            is_missing=not has_conversation,
                            latest_conversation_date=latest_conversation_date,
                            submission_count=section_submissions,
                        )
                    )

                # Determine participation status
                has_interactions = total_conversations > 0
                if not has_interactions:
                    participation_status = ParticipationStatus.NO_INTERACTION
                elif submitted_count > 0:
                    participation_status = ParticipationStatus.ACTIVE
                    active_students += 1
                else:
                    participation_status = ParticipationStatus.PARTIAL
                    active_students += 1

                # Create student summary
                student_name = (
                    f"{student.user.first_name} {student.user.last_name}".strip()
                )
                if not student_name:
                    student_name = student.user.username

                student_summaries.append(
                    StudentSubmissionSummary(
                        student_id=student.id,
                        student_name=student_name,
                        student_username=student.user.username,
                        student_email=student.user.email,
                        has_interactions=has_interactions,
                        section_statuses=section_statuses,
                        total_conversations=total_conversations,
                        submitted_count=submitted_count,
                        sections_started=sections_started,
                        missing_sections=missing_sections,
                        last_activity=last_activity,
                        participation_status=participation_status,
                    )
                )

            # Sort students: no_interaction first (with warnings), then by last activity (newest first)
            student_summaries.sort(
                key=lambda s: (
                    s.participation_status
                    != ParticipationStatus.NO_INTERACTION,  # False sorts first
                    -(s.last_activity or datetime.min).timestamp()
                    if s.last_activity
                    else 0,  # Negative for reverse order
                )
            )

            # Calculate statistics
            total_students = len(enrolled_students)
            inactive_students = total_students - active_students
            total_sections = len(homework_sections)

            return HomeworkSubmissionsData(
                homework_id=homework.id,
                homework_title=homework.title,
                homework_due_date=homework.due_date,
                total_sections=total_sections,
                students=student_summaries,
                total_students=total_students,
                active_students=active_students,
                inactive_students=inactive_students,
                total_submissions=total_submissions,
            )

        except Homework.DoesNotExist:
            logger.warning("Homework not found for submissions: %s", homework_id)
            record_exception(
                Homework.DoesNotExist(f"Homework {homework_id} not found"),
                "Homework not found",
            )
            return None
        except Exception as e:
            logger.exception("Failed to load submissions for homework %s", homework_id)
            record_exception(e)
            return None
