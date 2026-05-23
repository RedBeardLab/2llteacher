"""Forms for the conversations app."""

from django import forms

from .models import TeacherFeedback


class TeacherFeedbackForm(forms.ModelForm):
    """Form for teachers to submit/update feedback on a student conversation."""

    class Meta:
        model = TeacherFeedback
        fields = ["feedback_type", "feedback"]
        widgets = {
            "feedback": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "form-control",
                    "placeholder": (
                        "Write feedback for the student — what is strong, "
                        "what needs revision, and any next steps."
                    ),
                }
            ),
            "feedback_type": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_feedback(self):
        value = (self.cleaned_data.get("feedback") or "").strip()
        if not value:
            raise forms.ValidationError("Feedback cannot be empty.")
        return value
