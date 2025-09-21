#!/usr/bin/env python
"""
Script to run Django tests with optimized test settings.
This will use the in-memory database and other test optimizations.
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    # Set the Django settings module to use test settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.llteacher.test_settings")

    # Setup Django
    django.setup()

    # Run the tests
    execute_from_command_line(["manage.py", "test"] + sys.argv[1:])
