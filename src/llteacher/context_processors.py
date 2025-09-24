"""
Context processors for LLTeacher project.

Context processors automatically add variables to every template context.
"""

from django.conf import settings


def analytics(request):
    """
    Add analytics configuration to template context.
    
    This makes ENABLE_ANALYTICS and MICROSOFT_CLARITY_PROJECT_ID
    available in all templates.
    """
    return {
        'ENABLE_ANALYTICS': settings.ENABLE_ANALYTICS,
        'MICROSOFT_CLARITY_PROJECT_ID': settings.MICROSOFT_CLARITY_PROJECT_ID,
    }
