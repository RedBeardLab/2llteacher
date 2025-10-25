#!/usr/bin/env python
"""
Script to run Django tests with optimized test settings.
This will use the in-memory database and other test optimizations.
"""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    # Add src directory to Python path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    # Set the Django settings module to use test settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llteacher.test_settings")
    
    # Import Django after path is set
    import django
    from django.core.management import execute_from_command_line
    
    # Setup Django
    django.setup()

    # Run the tests
    execute_from_command_line(["manage.py", "test"] + sys.argv[1:])
