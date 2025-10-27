import os
import signal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PID_FILE = Path(settings.BASE_DIR) / "runserver.pid"


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        PID_FILE.unlink(missing_ok=True)
        return None


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
    help = "Stop the Django development server started via `startserver`."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force kill the process with SIGKILL if it does not stop with SIGTERM.",
        )

    def handle(self, *args, **options):
        pid = _read_pid()
        if pid is None:
            raise CommandError(
                "No PID file found. Did you start the server with `python manage.py startserver`?"
            )

        if not _is_process_running(pid):
            PID_FILE.unlink(missing_ok=True)
            raise CommandError(f"Process with PID {pid} is not running.")

        os.kill(pid, signal.SIGTERM)
        self.stdout.write(self.style.WARNING(f"Sent SIGTERM to server process {pid}."))

        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            # Process already exited
            pass
        except OSError:
            pass

        if _is_process_running(pid):
            if options["force"]:
                os.kill(pid, signal.SIGKILL)
                self.stdout.write(
                    self.style.WARNING(
                        f"Process {pid} did not exit; sent SIGKILL as requested."
                    )
                )
            else:
                raise CommandError(
                    f"Process {pid} did not exit. Re-run with --force to send SIGKILL."
                )

        PID_FILE.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS("Server stopped successfully."))
