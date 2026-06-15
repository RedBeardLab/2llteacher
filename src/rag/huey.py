import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llteacher.settings")

import django
from django.conf import settings
from huey import Huey, SqliteHuey

django.setup()


def _get_huey() -> Huey:
    cfg = settings.HUEY.copy()

    name = cfg.pop("name", "llteacher")
    immediate = cfg.pop("immediate", False)
    filename = cfg.pop("filename", None)

    if immediate:
        return Huey(name=name, immediate=True)

    if filename and filename != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

    return SqliteHuey(name=name, filename=filename, immediate=immediate)


huey = _get_huey()

import rag.tasks  # noqa: E402, F401 — register Huey tasks
