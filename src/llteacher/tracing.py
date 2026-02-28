"""
OpenTelemetry tracing utilities.

Provides a @traced decorator for adding spans to service methods.
When OTel is not configured, the decorator is a no-op.
"""

import functools
import inspect
import logging

from opentelemetry import trace
from opentelemetry.trace import StatusCode

# Max length for attribute values to avoid bloating spans
_MAX_ATTR_LENGTH = 256


def _safe_repr(value) -> str:
    """Convert a value to a string safe for use as a span attribute."""
    try:
        r = repr(value)
    except Exception:
        r = f"<{type(value).__name__}>"
    if len(r) > _MAX_ATTR_LENGTH:
        return r[:_MAX_ATTR_LENGTH] + "..."
    return r


def traced(func):
    """Decorator that wraps a function in an OpenTelemetry span.

    The span name is set to "Module.QualifiedName" (e.g.
    "HomeworkService.get_homework_submissions").

    Function arguments are recorded as span attributes.
    """
    tracer = trace.get_tracer(func.__module__)
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())
    is_generator = inspect.isgeneratorfunction(func)

    def _set_args(span, args, kwargs):
        for i, value in enumerate(args):
            if i < len(param_names):
                span.set_attribute(param_names[i], _safe_repr(value))
        for key, value in kwargs.items():
            span.set_attribute(key, _safe_repr(value))

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(func.__qualname__) as span:
            _set_args(span, args, kwargs)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise

    @functools.wraps(func)
    def generator_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(func.__qualname__) as span:
            _set_args(span, args, kwargs)
            try:
                yield from func(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise

    return generator_wrapper if is_generator else wrapper


logger = logging.getLogger(__name__)


def record_exception(e: Exception, message: str | None = None) -> None:
    """Record an exception on the current span and mark it as error.

    Use this in except blocks that handle exceptions without re-raising,
    so they still appear as errors in Honeycomb.
    """
    span = trace.get_current_span()
    span.record_exception(e)
    span.set_status(StatusCode.ERROR, message or str(e))


def set_span_attributes(attributes: dict) -> None:
    """Set attributes on the current active span.

    Use this inside a @traced function to record computed values
    (e.g. response times, token counts) on the span.

    Values that are not str, bool, int, or float are converted
    via _safe_repr. None values are skipped.
    """
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is None:
            continue
        if not isinstance(value, (str, bool, int, float)):
            value = _safe_repr(value)
        span.set_attribute(key, value)
