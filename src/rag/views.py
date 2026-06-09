import hashlib
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotModified,
)
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.http import content_disposition_header
from django.views import View

from courses.models import Course, CourseTeacher
from llteacher.permissions.decorators import TeacherRequest, teacher_required

from .forms import (
    CourseMaterialTitleForm,
    CourseMaterialUploadForm,
    title_from_filename,
)
from .models import CourseMaterial, CourseMaterialBlob
from .tasks import index_course_material


def teacher_can_manage_course_materials(teacher, course: Course) -> bool:
    return CourseTeacher.objects.filter(course=course, teacher=teacher).exists()


class CourseMaterialUploadView(View):
    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request: TeacherRequest, course_id: UUID) -> HttpResponse:
        course = get_object_or_404(Course, id=course_id)
        teacher = request.user.teacher_profile

        if not teacher_can_manage_course_materials(teacher, course):
            return HttpResponseForbidden(
                "You can only upload materials for courses you teach."
            )

        form = CourseMaterialUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("courses:detail", course_id=course.id)

        created_count = 0
        for uploaded_file in form.cleaned_data["files"]:
            uploaded_file.seek(0)
            pdf_data = uploaded_file.read()
            checksum = hashlib.sha256(pdf_data).hexdigest()

            material = CourseMaterial.objects.create(
                course=course,
                title=title_from_filename(uploaded_file.name),
                original_filename=uploaded_file.name or "material.pdf",
                content_type=uploaded_file.content_type or "application/pdf",
                size=len(pdf_data),
                checksum=checksum,
                uploaded_by=teacher,
            )
            CourseMaterialBlob.objects.create(material=material, data=pdf_data)
            index_course_material(
                material_id=str(material.id),
                course_id=str(course.id),
            )
            created_count += 1

        messages.success(
            request,
            f"Uploaded {created_count} course material"
            f"{'' if created_count == 1 else 's'}.",
        )
        return redirect("courses:detail", course_id=course.id)

    def get(self, request: HttpRequest, course_id: UUID) -> HttpResponse:
        return HttpResponseNotAllowed(["POST"])


class CourseMaterialEditView(View):
    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(
        self, request: TeacherRequest, course_id: UUID, material_id: UUID
    ) -> HttpResponse:
        course = get_object_or_404(Course, id=course_id)
        teacher = request.user.teacher_profile

        if not teacher_can_manage_course_materials(teacher, course):
            return HttpResponseForbidden(
                "You can only edit materials for courses you teach."
            )

        material = get_object_or_404(CourseMaterial, id=material_id, course=course)
        form = CourseMaterialTitleForm(request.POST)

        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("courses:detail", course_id=course.id)

        material.title = form.cleaned_data["title"]
        material.save(update_fields=["title", "updated_at"])
        messages.success(request, "Course material updated.")
        return redirect("courses:detail", course_id=course.id)

    def get(
        self, request: HttpRequest, course_id: UUID, material_id: UUID
    ) -> HttpResponse:
        return HttpResponseNotAllowed(["POST"])


class CourseMaterialDeleteView(View):
    @method_decorator(login_required, name="dispatch")
    @method_decorator(teacher_required, name="dispatch")
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(
        self, request: TeacherRequest, course_id: UUID, material_id: UUID
    ) -> HttpResponse:
        course = get_object_or_404(Course, id=course_id)
        teacher = request.user.teacher_profile

        if not teacher_can_manage_course_materials(teacher, course):
            return HttpResponseForbidden(
                "You can only delete materials for courses you teach."
            )

        material = get_object_or_404(CourseMaterial, id=material_id, course=course)
        material.delete()

        messages.success(request, "Course material deleted.")
        return redirect("courses:detail", course_id=course.id)

    def get(
        self, request: HttpRequest, course_id: UUID, material_id: UUID
    ) -> HttpResponse:
        return HttpResponseNotAllowed(["POST"])


class CourseMaterialPdfView(View):
    def get(
        self, request: HttpRequest, material_id: UUID, checksum: str
    ) -> HttpResponse:
        try:
            material = CourseMaterial.objects.only(
                "id", "checksum", "original_filename", "content_type"
            ).get(id=material_id, checksum=checksum)
        except CourseMaterial.DoesNotExist as exc:
            raise Http404 from exc

        etag = f'"{material.checksum}"'
        if request.headers.get("If-None-Match") == etag:
            response = HttpResponseNotModified()
        else:
            blob = get_object_or_404(CourseMaterialBlob, material=material)
            response = HttpResponse(blob.data, content_type="application/pdf")

        filename = material.original_filename or "material.pdf"
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = content_disposition_header(
            False, filename
        )
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
