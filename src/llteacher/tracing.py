"""
OpenTelemetry tracing utilities.

Provides a @traced decorator for adding spans to service methods.
When OTel is not configured, the decorator is a no-op.
"""

import functools

from opentelemetry import trace


def traced(func):
    """Decorator that wraps a function in an OpenTelemetry span.

    The span name is set to "Module.QualifiedName" (e.g.
    "HomeworkService.get_homework_submissions").
    """
    tracer = trace.get_tracer(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(func.__qualname__):
            return func(*args, **kwargs)

    return wrapper
