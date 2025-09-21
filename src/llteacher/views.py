"""
Main views for the llteacher project.
"""

from django.shortcuts import render


def homepage(request):
    """
    Display the homepage with login form for unauthenticated users
    and welcome message for authenticated users.
    """
    return render(request, "homepage.html")
