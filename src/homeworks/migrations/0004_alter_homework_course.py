# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0005_remove_course_homeworks_delete_coursehomework"),
        ("homeworks", "0003_assign_homeworks_to_courses"),
    ]

    operations = [
        migrations.AlterField(
            model_name="homework",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="homeworks",
                to="courses.course",
            ),
        ),
    ]
