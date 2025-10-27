import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from voters.models import Voter


class Command(BaseCommand):
    help = "Import voters from a CSV file containing voter_number, full_name, and optional email."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the CSV without writing any data.",
        )
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help="Deactivate voters not present in the file.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser()
        dry_run = options["dry_run"]
        deactivate_missing = options["deactivate_missing"]

        if not csv_path.exists():
            raise CommandError(f"Could not find CSV file at {csv_path}")

        created, updated = 0, 0
        seen_numbers: set[str] = set()

        with csv_path.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            expected_columns = {"voter_number", "full_name"}
            missing = expected_columns - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f"CSV is missing required columns: {', '.join(sorted(missing))}"
                )

            for row in reader:
                voter_number = (row.get("voter_number") or "").strip()
                full_name = (row.get("full_name") or "").strip()
                email = (row.get("email") or "").strip()
                national_id = (
                    row.get("national_id_number")
                    or row.get("national_id")
                    or row.get("id_number")
                    or ""
                ).strip()
                birth_year_raw = (
                    row.get("birth_year") or row.get("birthYear") or ""
                ).strip()
                notes = (row.get("notes") or "").strip()

                if not voter_number or not full_name:
                    raise CommandError(
                        "Each row must include both voter_number and full_name values."
                    )

                seen_numbers.add(voter_number)

                birth_year = None
                if birth_year_raw:
                    try:
                        birth_year_int = int(birth_year_raw)
                        if 1900 <= birth_year_int <= 2100:
                            birth_year = birth_year_int
                    except ValueError as exc:
                        raise CommandError(
                            f"Invalid birth year '{birth_year_raw}' for voter {voter_number}"
                        ) from exc

                defaults = {
                    "full_name": full_name,
                    "email": email,
                    "birth_year": birth_year,
                }
                if national_id:
                    defaults["national_id_number"] = national_id
                if notes:
                    defaults["notes"] = notes
                if dry_run:
                    continue
                _, created_flag = Voter.objects.update_or_create(
                    voter_number=voter_number, defaults=defaults
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        if deactivate_missing and not dry_run:
            deactivated = (
                Voter.objects.exclude(voter_number__in=seen_numbers)
                .filter(is_active=True)
                .update(is_active=False)
            )
        else:
            deactivated = 0

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run completed. No changes made."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import complete. Created {created}, updated {updated}, deactivated {deactivated}."
                )
            )
