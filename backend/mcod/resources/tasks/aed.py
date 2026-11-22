# MISJA AED
# Zadanie Celery tworzące "Wykaz zbiorczy AED" - wzorowane na `tasks/dga.py`.
import logging
from typing import Any, Dict

from django.apps import apps

from mcod.core.tasks import extended_shared_task
from mcod.resources.aed_utils import (
    check_aed_resource_validations_status,
    acquire_main_aed_task_lock,
    clean_up_after_main_aed_resource_creation,
    create_main_aed_files,
    create_main_aed_resources_with_dataset,
    release_main_aed_task_lock,
    update_or_create_aggr_aed_info_and_delete_old_main_aed,
)
from mcod.resources.dga_utils import (
    FailedValidationException,
    PendingValidationException,
    check_all_resource_validations_status,  # noqa: F401
)

logger = logging.getLogger("mcod")


@extended_shared_task(
    max_retries=5,
    atomic=False,
    retry_countdown=20,
    retry_on_errors=(PendingValidationException,),
    bind=True,
    name="mcod.resources.tasks.create_main_aed_resource_task",
)
def create_main_aed_resource_task(self) -> None:
    """
    Creates the main AED Resources ("Wykaz zbiorczy AED") in several steps:

    1. Reading all published resources marked as AED lists
       (`contains_aed_list`), validating them against the AED tableschema and
       creating CSV, XLSX and GeoJSON files of the aggregated list.
    2. Creation of Resources and ResourceFiles for the aggregated list (and
       of the main AED Dataset if it does not exist yet).
    3. Verification that all validation stages of the main (CSV) Resource
       have been completed. If any validation is pending, the task is retried.
    4. Updating AggregatedAEDInfo (statistics, validation report) and
       removing the old main AED Resources.

    Cleanup process (as in the main DGA task): if the task fails or the
    resource is still not validated on the last retry, created objects are
    deleted. Temporary files and the task cache are always cleaned at the end.
    A cache lock prevents concurrent runs of the task.
    """
    if not acquire_main_aed_task_lock():
        logger.warning("Main AED resource creation is already running - skipping.")
        return

    logger.info("Starting main AED resource creation.")
    Resource = apps.get_model("resources", "Resource")

    try:
        # Step 1: Main AED files creation
        logger.info("Step 1/4: Creating Main AED files (csv, xlsx, geojson).")
        files_info: Dict[str, Any] = create_main_aed_files()

        # Step 2: Main AED Resources creation (also Dataset if needed).
        logger.info("Step 2/4: Creating Main AED resources with files.")
        new_resources_pks: Dict[str, int]
        new_resources_pks, _ = create_main_aed_resources_with_dataset(files_info=files_info)
        new_resources: Dict[str, Resource] = {
            file_format: Resource.objects.get(pk=pk) for file_format, pk in new_resources_pks.items()
        }

        # Step 3: Check main (CSV) resource validations
        logger.info("Step 3/4: Checking resource validations.")
        check_aed_resource_validations_status(new_resources["csv"])

        # Step 4: Update Aggregated AED Info and delete old main AED Resources
        logger.info("Step 4/4: Updating AggregatedAEDInfo and deleting old Resources.")
        update_or_create_aggr_aed_info_and_delete_old_main_aed(new_resources, files_info)

        logger.info("Main AED Resources successfully created.")
        clean_up_after_main_aed_resource_creation(exception_occurred=False)

    except PendingValidationException:
        if self.request.retries == self.max_retries:
            logger.info("Cleaning after main AED resource creation task due to still pending resource validation(s).")
            clean_up_after_main_aed_resource_creation(exception_occurred=True)
        raise

    except FailedValidationException:
        clean_up_after_main_aed_resource_creation(exception_occurred=True)
        raise

    except Exception as exc:
        logger.error(f"Cleaning after main AED resource creation task due to unexpected error: {exc}")
        clean_up_after_main_aed_resource_creation(exception_occurred=True)
        raise

    finally:
        release_main_aed_task_lock()
