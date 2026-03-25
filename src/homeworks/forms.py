"""
Forms for the homeworks app.

This module provides forms for creating and editing homeworks and sections,
following the testable-first architecture.
"""

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import Homework


def _to_local_str(dt) -> str:
    """Convert a datetime to a local datetime-local input string."""
    if settings.USE_TZ and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    if settings.USE_TZ:
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")
    return dt.strftime("%Y-%m-%dT%H:%M")


def _make_aware_if_naive(dt):
    """Make a naive datetime timezone-aware when USE_TZ is active."""
    if dt is not None and settings.USE_TZ and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


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
        widget=forms.HiddenInput(),
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
        fields = [
            "title",
            "description",
            "course",
            "due_date",
            "expires_at",
            "publish_at",
            "llm_config",
        ]
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
            "expires_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "publish_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "llm_config": forms.Select(
                attrs={"class": "form-select", "placeholder": "LLM Configuration"}
            ),
        }

    def __init__(self, *args, is_draft_save=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False
        self.fields["expires_at"].required = False
        self.fields["publish_at"].required = False
        # due_date is nullable on the model so ModelForm won't auto-require it
        self.fields["due_date"].required = not is_draft_save
        if is_draft_save:
            self.fields["description"].required = False
        self.expires_at_adjusted = False  # flag for view to flash a warning

        # Display stored datetimes in server local time, not raw UTC
        if self.instance and self.instance.due_date:
            self.initial["due_date"] = _to_local_str(self.instance.due_date)
        if self.instance and self.instance.expires_at:
            self.initial["expires_at"] = _to_local_str(self.instance.expires_at)
        if self.instance and self.instance.publish_at:
            self.initial["publish_at"] = _to_local_str(self.instance.publish_at)

    def clean_due_date(self):
        """Make aware. Reject only strictly past dates — today is allowed."""
        due_date = _make_aware_if_naive(self.cleaned_data.get("due_date"))

        if due_date:
            today = (
                timezone.now().date()
                if not settings.USE_TZ
                else timezone.localtime(timezone.now()).date()
            )
            if due_date.date() < today:
                raise forms.ValidationError("Due date cannot be in the past.")

        return due_date

    def clean_expires_at(self):
        """Make aware if naive."""
        return _make_aware_if_naive(self.cleaned_data.get("expires_at"))

    def clean_publish_at(self):
        """Make aware if naive. Required (and future) when publishing without 'Publish now'."""
        publish_at = _make_aware_if_naive(self.cleaned_data.get("publish_at"))
        publishing_scheduled = "publish" in self.data and "publish_now" not in self.data
        if publishing_scheduled and not publish_at:
            raise forms.ValidationError(
                'Set a future publish date, or enable "Publish now".'
            )
        if publish_at and publish_at <= timezone.now():
            raise forms.ValidationError("Scheduled publish time must be in the future.")
        return publish_at

    def clean(self):
        """Warn if expires_at precedes due_date, but allow it."""
        cleaned_data = super().clean()
        due_date = cleaned_data.get("due_date")
        expires_at = cleaned_data.get("expires_at")

        if due_date and expires_at and expires_at < due_date:
            self.expires_at_adjusted = True  # view will warn the teacher

        return cleaned_data


class HomeworkEditForm(forms.ModelForm):
    """Form for editing an existing homework assignment."""

    class Meta:
        model = Homework
        fields = [
            "title",
            "description",
            "due_date",
            "expires_at",
            "publish_at",
            "llm_config",
        ]  # Note: course and is_hidden are excluded (managed automatically)
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
            "expires_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "publish_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "llm_config": forms.Select(
                attrs={"class": "form-select", "placeholder": "LLM Configuration"}
            ),
        }

    def __init__(self, *args, is_draft_save=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False
        self.fields["expires_at"].required = False
        self.fields["publish_at"].required = False
        # due_date is nullable on the model so ModelForm won't auto-require it
        self.fields["due_date"].required = not is_draft_save
        if is_draft_save:
            self.fields["description"].required = False
        self.expires_at_adjusted = False  # flag for view to flash a warning

        # Display stored datetimes in server local time, not raw UTC
        if self.instance and self.instance.due_date:
            self.initial["due_date"] = _to_local_str(self.instance.due_date)
        if self.instance and self.instance.expires_at:
            self.initial["expires_at"] = _to_local_str(self.instance.expires_at)
        if self.instance and self.instance.publish_at:
            self.initial["publish_at"] = _to_local_str(self.instance.publish_at)

    def clean_due_date(self):
        """Make aware. No date restrictions on edit — teacher has full control."""
        return _make_aware_if_naive(self.cleaned_data.get("due_date"))

    def clean_expires_at(self):
        """Make aware if naive."""
        return _make_aware_if_naive(self.cleaned_data.get("expires_at"))

    def clean_publish_at(self):
        """Make aware if naive. Required when publishing without 'Publish now'."""
        publish_at = _make_aware_if_naive(self.cleaned_data.get("publish_at"))
        publishing_scheduled = "publish" in self.data and "publish_now" not in self.data
        if publishing_scheduled and not publish_at:
            raise forms.ValidationError(
                'Set a future publish date, or enable "Publish now".'
            )
        return publish_at

    def clean(self):
        """Warn if expires_at precedes due_date, but allow it."""
        cleaned_data = super().clean()
        due_date = cleaned_data.get("due_date")
        expires_at = cleaned_data.get("expires_at")

        if due_date and expires_at and expires_at < due_date:
            self.expires_at_adjusted = True  # view will warn the teacher

        return cleaned_data


class SectionFormSet(forms.BaseFormSet):
    """Formset for managing multiple sections in a homework."""

    is_draft_save: bool = False

    def clean(self):
        """Validate the formset as a whole.

        Checks that:
        1. At least one section exists (skipped for draft saves)
        2. No duplicate orders
        3. Orders are sequential
        """
        if any(self.errors):
            return

        if self.is_draft_save:
            return  # Sections are optional for drafts

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
