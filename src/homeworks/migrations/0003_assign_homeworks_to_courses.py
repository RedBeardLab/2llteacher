# Data migration to assign orphaned homeworks to courses

from django.db import migrations


def assign_homeworks_to_courses(apps, schema_editor):
    """Assign all homeworks without a course to a default course."""
    Homework = apps.get_model('homeworks', 'Homework')
    Course = apps.get_model('courses', 'Course')

    # Get all homeworks without a course
    orphaned_homeworks = Homework.objects.filter(course__isnull=True)

    if not orphaned_homeworks.exists():
        # No orphaned homeworks, nothing to do
        return

    # Try to get the STAT302 course first, or any available course
    try:
        default_course = Course.objects.get(code='STAT302-Furfaro-First')
    except Course.DoesNotExist:
        # If STAT302 doesn't exist, use the first available course
        default_course = Course.objects.first()

        if not default_course:
            # No courses exist at all - this is a problem
            # We can't proceed without at least one course
            raise Exception(
                "Cannot assign homeworks to courses: No courses exist in the database. "
                "Please create at least one course before running migrations."
            )

    # Assign all orphaned homeworks to the default course
    count = orphaned_homeworks.update(course=default_course)
    print(f"Assigned {count} orphaned homework(s) to course: {default_course.name}")


def reverse_assignment(apps, schema_editor):
    """Reverse the assignment by setting course to NULL."""
    # Note: This will only work if the field is still nullable
    # Once migration 0004 runs, this reverse won't be possible
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0005_remove_course_homeworks_delete_coursehomework'),
        ('homeworks', '0002_homework_course'),
    ]

    operations = [
        migrations.RunPython(assign_homeworks_to_courses, reverse_assignment),
    ]
