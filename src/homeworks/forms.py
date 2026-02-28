"""
Forms for the homeworks app.

This module provides forms for creating and editing homeworks and sections,
following the testable-first architecture.
"""

from typing import TYPE_CHECKING

from django import forms
from django.utils import timezone

from .models import Homework


class SectionForm(forms.Form):
    """Form for creating or editing a section."""

    id = forms.UUIDField(required=False, widget=forms.HiddenInput())
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Section Title"}
        ),
    )
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Section content...",
            }
        )
    )
    order = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Order (1-20)"}
        ),
    )
    solution = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional solution...",
            }
        ),
    )


class HomeworkCreateForm(forms.ModelForm):
    """Form for creating a new homework assignment."""

    class Meta:
        model = Homework
        fields = ["title", "description", "course", "due_date", "llm_config"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Homework Title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Homework description...",
                }
            ),
            "course": forms.Select(
                attrs={"class": "form-select", "placeholder": "Select Course"}
            ),
            "due_date": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                    "placeholder": "Due Date",
                }
            ),
            "llm_config": forms.Select(
                attrs={"class": "form-select", "placeholder": "LLM Configuration"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False

        # Convert datetime to format expected by datetime-local input
        if self.instance and self.instance.due_date:
            self.initial["due_date"] = self.instance.due_date.strftime("%Y-%m-%dT%H:%M")

    def clean_due_date(self):
        """Validate due date is in the future."""
        due_date = self.cleaned_data.get("due_date")

        if due_date and due_date <= timezone.now():
            raise forms.ValidationError("Due date must be in the future.")

        return due_date


class HomeworkEditForm(forms.ModelForm):
    """Form for editing an existing homework assignment."""

    class Meta:
        model = Homework
        fields = ["title", "description", "due_date", "llm_config"]  # Note: course is excluded
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Homework Title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Homework description...",
                }
            ),
            "due_date": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                    "placeholder": "Due Date",
                }
            ),
            "llm_config": forms.Select(
                attrs={"class": "form-select", "placeholder": "LLM Configuration"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False

        # Convert datetime to format expected by datetime-local input
        if self.instance and self.instance.due_date:
            self.initial["due_date"] = self.instance.due_date.strftime("%Y-%m-%dT%H:%M")

    def clean_due_date(self):
        """Validate due date is in the future."""
        due_date = self.cleaned_data.get("due_date")

        if due_date and due_date <= timezone.now():
            raise forms.ValidationError("Due date must be in the future.")

        return due_date


if TYPE_CHECKING:
    BaseSectionFormSet = forms.BaseFormSet[SectionForm]
else:
    BaseSectionFormSet = forms.BaseFormSet


class SectionFormSet(BaseSectionFormSet):
    """Formset for managing multiple sections in a homework."""

    def clean(self):
        """Validate the formset as a whole.

        Checks that:
        1. At least one section exists
        2. No duplicate orders
        3. Orders are sequential
        """
        if any(self.errors):
            return

        if not any(
            form.cleaned_data
            for form in self.forms
            if not form.cleaned_data.get("DELETE", False)
        ):
            raise forms.ValidationError("At least one section is required.")

        orders = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                order = form.cleaned_data.get("order")
                if order in orders:
                    raise forms.ValidationError(
                        f"Section {order} appears multiple times."
                    )
                orders.append(order)

        # Check for gaps in order
        if orders:
            orders.sort()
            if orders[0] != 1:
                raise forms.ValidationError("Sections must start with order 1.")

            for i in range(len(orders) - 1):
                if orders[i + 1] - orders[i] > 1:
                    raise forms.ValidationError(
                        f"Section order is not sequential. Missing section after {orders[i]}."
                    )
