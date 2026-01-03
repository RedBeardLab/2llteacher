"""
Forms for the courses app.

This module provides forms for creating and editing courses,
following the testable-first architecture.
"""

from django import forms

from .models import Course


class CourseForm(forms.ModelForm):
    """Form for creating or editing a course."""

    class Meta:
        model = Course
        fields = ["name", "code", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Course Name",
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Course Code (e.g., CS101)",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Course description (optional)...",
                }
            ),
        }
        help_texts = {
            "code": "A unique identifier for this course (e.g., CS101, MATH201)",
        }
