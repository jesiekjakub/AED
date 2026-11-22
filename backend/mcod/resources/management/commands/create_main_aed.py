# MISJA AED
from django.core.management.base import BaseCommand

from mcod.resources.tasks import create_main_aed_resource_task


class Command(BaseCommand):
    help = (
        'Zleca utworzenie (lub aktualizację) "Wykazu zbiorczego AED" na podstawie wszystkich '
        "opublikowanych zasobów oznaczonych jako wykaz AED (Misja AED)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            dest="run_sync",
            default=False,
            help=(
                "Uruchom zadanie synchronicznie w bieżącym procesie (sensowne tylko przy "
                "CELERY_TASK_ALWAYS_EAGER=True, bo walidacja nowych zasobów działa w workerach)."
            ),
        )

    def handle(self, *args, **options):
        if options["run_sync"]:
            create_main_aed_resource_task.apply()
            self.stdout.write("Zakończono zadanie create_main_aed_resource_task.")
            return

        result = create_main_aed_resource_task.delay()
        self.stdout.write(f"Zlecono zadanie create_main_aed_resource_task: {result.id}")
