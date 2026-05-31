from django.core.management.base import BaseCommand

from rag.models import CourseMaterial, ProcessingStatus
from rag.tasks import index_course_material


class Command(BaseCommand):
    help = "Process pending course materials for RAG indexing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--material-id",
            type=str,
            help="Process a single material by ID.",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            help="Re-index already completed or failed materials.",
        )

    def handle(self, *args, **options):
        if options["material_id"]:
            materials = CourseMaterial.objects.filter(id=options["material_id"])
            if not materials.exists():
                self.stdout.write(
                    self.style.ERROR(f"Material {options['material_id']} not found.")
                )
                return
        elif options["reindex"]:
            materials = CourseMaterial.objects.exclude(
                processing_status=ProcessingStatus.PROCESSING
            )
        else:
            materials = CourseMaterial.objects.filter(
                processing_status=ProcessingStatus.PENDING
            )

        count = materials.count()
        if count == 0:
            self.stdout.write("No materials to process.")
            return

        self.stdout.write(f"Enqueuing {count} material(s) for indexing...")
        for material in materials:
            index_course_material(
                material_id=str(material.id),
                course_id=str(material.course_id),
            )
            self.stdout.write(f"  Enqueued: {material.title} ({material.id})")

        self.stdout.write(self.style.SUCCESS(f"Done. Enqueued {count} material(s)."))
