from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from voters.services.importers import import_voters_from_excel


class Command(BaseCommand):
    help = "Import voters from an Excel workbook. Expects columns: رقم الناخب (voter number), الاسم الثلاثي, المواليد, الاسم الصحيح (optional)."

    def add_arguments(self, parser):
        parser.add_argument("excel_path", type=str, help="Path to the Excel file.")
        parser.add_argument(
            "--sheet",
            type=str,
            default=None,
            help="Specific sheet name to import (defaults to the first sheet).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse without writing any data.",
        )

    def handle(self, *args, **options):
        excel_path = Path(options["excel_path"]).expanduser()
        sheet = options["sheet"]
        dry_run = options["dry_run"]

        if not excel_path.exists():
            raise CommandError(f"Could not find Excel file at {excel_path}")

        result = import_voters_from_excel(excel_path, sheet_name=sheet, dry_run=dry_run)

        message = (
            f"Parsed {result.total_rows} rows. "
            f"Created {result.created}, updated {result.updated}."
        )
        if result.errors:
            message += f" Encountered {len(result.errors)} errors."
            for err in result.errors:
                self.stderr.write(self.style.ERROR(err))

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete. " + message))
        else:
            self.stdout.write(self.style.SUCCESS("Import complete. " + message))
