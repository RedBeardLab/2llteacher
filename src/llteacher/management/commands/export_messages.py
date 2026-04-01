import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
from conversations.models import Message


class Command(BaseCommand):
    help = "Export all messages with conversation and user metadata to CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Output CSV file path (default: messages_export_YYYYMMDD_HHMMSS.csv)",
        )
        parser.add_argument(
            "--database",
            type=str,
            help="Path to SQLite database file (default: uses Django settings)",
        )

    def handle(self, *args, **options):
        # Generate default filename with timestamp if not provided
        output_file = options.get("output")
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"messages_export_{timestamp}.csv"

        # Handle custom database path
        database_path = options.get("database")
        original_db_name = None

        if database_path:
            # Store original database name
            original_db_name = settings.DATABASES["default"]["NAME"]
            # Temporarily change to the specified database
            settings.DATABASES["default"]["NAME"] = database_path
            # Close existing connection to force reconnection with new database
            connections["default"].close()
            self.stdout.write(f"Using database: {database_path}")

        try:
            self.stdout.write(f"Exporting messages to {output_file}...")

            # Fetch all messages with related data (optimized query)
            messages = Message.objects.select_related(
                "conversation__user__student_profile",
                "conversation__user__teacher_profile",
                "conversation__section__homework",
            ).order_by("timestamp")

            total_messages = messages.count()
            self.stdout.write(f"Found {total_messages} messages to export")

            # Write to CSV
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                # Define CSV columns
                fieldnames = [
                    "message_id",
                    "message_length",
                    "message_type",
                    "message_timestamp",
                    "conversation_id",
                    "conversation_created_at",
                    "conversation_updated_at",
                    "conversation_deleted_at",
                    "user_id",
                    "user_type",
                    "section_id",
                    "section_title",
                    "homework_id",
                    "homework_title",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Export each message
                exported_count = 0
                for message in messages:
                    conversation = message.conversation
                    user = conversation.user
                    section = conversation.section
                    homework = section.homework

                    # Determine user type
                    if hasattr(user, "student_profile"):
                        user_type = "Student"
                    elif hasattr(user, "teacher_profile"):
                        user_type = "Teacher"
                    else:
                        user_type = "Unknown"

                    # Format conversation_deleted_at (empty if not deleted)
                    conversation_deleted_at = ""
                    if conversation.is_deleted and conversation.deleted_at:
                        conversation_deleted_at = conversation.deleted_at.isoformat()

                    # Write row
                    writer.writerow(
                        {
                            "message_id": str(message.id),
                            "message_length": len(message.content),
                            "message_type": message.message_type,
                            "message_timestamp": message.timestamp.isoformat(),
                            "conversation_id": str(conversation.id),
                            "conversation_created_at": conversation.created_at.isoformat(),
                            "conversation_updated_at": conversation.updated_at.isoformat(),
                            "conversation_deleted_at": conversation_deleted_at,
                            "user_id": str(user.id),
                            "user_type": user_type,
                            "section_id": str(section.id),
                            "section_title": section.title,
                            "homework_id": str(homework.id),
                            "homework_title": homework.title,
                        }
                    )

                    exported_count += 1

                    # Progress indicator for large exports
                    if exported_count % 100 == 0:
                        self.stdout.write(
                            f"  Exported {exported_count}/{total_messages} messages..."
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Successfully exported {exported_count} messages to {output_file}"
                )
            )
        finally:
            # Restore original database setting if it was changed
            if original_db_name:
                settings.DATABASES["default"]["NAME"] = original_db_name
                connections["default"].close()
