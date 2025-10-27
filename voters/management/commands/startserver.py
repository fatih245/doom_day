import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PID_FILE = Path(settings.BASE_DIR) / "runserver.pid"


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


class Command(BaseCommand):
    help = "Start the Django development server in the background and store its PID."

    def add_arguments(self, parser):
        parser.add_argument(
            "addrport",
            nargs="?",
            default="127.0.0.1:8000",
            help="Optional address:port (default: 127.0.0.1:8000)",
        )

    def handle(self, *args, **options):
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
            except ValueError:
                PID_FILE.unlink(missing_ok=True)
            else:
                if _is_process_running(pid):
                    raise CommandError(
                        f"Server already appears to be running with PID {pid}. "
                        "Run `python manage.py stopserver` first if you want to restart it."
                    )
                PID_FILE.unlink(missing_ok=True)

        addrport = options["addrport"]
        cmd = [
            sys.executable,
            "manage.py",
            "runserver",
            addrport,
            "--noreload",
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=settings.BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
        except OSError as exc:
            raise CommandError(f"Failed to start runserver: {exc}") from exc

        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Server started on {addrport} (PID {proc.pid}). "
                "Use `python manage.py stopserver` to stop it."
            )
        )
