# MISJA AED - testy (z bazą danych) wykazu zbiorczego AED, wzorowane na test_main_dga.py
from typing import List

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from falcon import HTTP_NOT_FOUND, HTTP_OK
from falcon.testing import TestClient

from mcod.categories.factories import CategoryFactory
from mcod.datasets.models import Dataset
from mcod.organizations.factories import OrganizationFactory
from mcod.organizations.models import Organization
from mcod.resources.aed_utils import (
    MAIN_AED_CSV,
    MAIN_AED_GEOJSON,
    MAIN_AED_XLSX,
    create_main_aed_dataset,
    get_all_aed_resources_sorted_by_organizations,
    get_main_aed_resource,
    update_or_create_aggr_aed_info_and_delete_old_main_aed,
)
from mcod.resources.factories import AggregatedAEDInfoFactory, ResourceFactory
from mcod.resources.models import AggregatedAEDInfo, Resource


@pytest.mark.feat_main_aed
def test_resource_contains_aed_list_default_false():
    resource: Resource = ResourceFactory.create()
    assert resource.contains_aed_list is False


@pytest.mark.feat_main_aed
def test_get_all_aed_resources_sorted_by_organizations():
    # GIVEN
    organizations = [OrganizationFactory.create(title=title) for title in ["Powiat B", "Gmina A"]]
    aed_resources = [
        ResourceFactory.create(dataset__organization=org, contains_aed_list=True, status="published")
        for org in organizations
    ]
    # Resources that should not be included
    ResourceFactory.create(contains_aed_list=False, status="published")
    ResourceFactory.create(contains_aed_list=True, status="draft")
    main_aed_resource: Resource = ResourceFactory.create(contains_aed_list=True, status="published")
    AggregatedAEDInfoFactory.create(resource=main_aed_resource)

    # WHEN
    resources: QuerySet = get_all_aed_resources_sorted_by_organizations()

    # THEN
    assert list(resources) == [aed_resources[1], aed_resources[0]]
    assert main_aed_resource not in resources


@pytest.mark.feat_main_aed
def test_create_main_aed_dataset(main_dga_owner_organization: Organization):
    CategoryFactory.create(title="Zdrowie")

    dataset_pk: int = create_main_aed_dataset()

    dataset: Dataset = Dataset.objects.get(pk=dataset_pk)
    assert dataset.title == settings.MAIN_AED_DATASET_DEFAULT_TITLE
    assert dataset.organization.pk == settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK
    assert dataset.update_frequency == "daily"
    assert dataset.status == "published"
    assert set(dataset.categories.values_list("title", flat=True)) == {"Zdrowie"}
    assert set(dataset.tags.values_list("name", flat=True)) == {"AED", "defibrylator", "misja-aed"}


@pytest.mark.feat_main_aed
def test_aggregated_aed_info_is_singleton():
    AggregatedAEDInfoFactory.create()
    with pytest.raises(ValidationError):
        AggregatedAEDInfo.objects.create()


@pytest.mark.feat_main_aed
def test_update_or_create_aggr_aed_info_and_delete_old_main_aed():
    # GIVEN
    old_resources: List[Resource] = ResourceFactory.create_batch(3)
    aed_info: AggregatedAEDInfo = AggregatedAEDInfoFactory.create(
        resource=old_resources[0],
        xlsx_resource=old_resources[1],
        geojson_resource=old_resources[2],
    )
    new_resources = dict(zip((MAIN_AED_CSV, MAIN_AED_XLSX, MAIN_AED_GEOJSON), ResourceFactory.create_batch(3)))
    files_info = {
        "paths": {},
        "stats": {
            "source_resources_count": 2,
            "aggregated_resources_count": 2,
            "rows_count": 5,
            "invalid_rows_count": 2,
            "geo_rows_count": 4,
        },
        "validation_report": [{"resource_id": 1, "status": "ok", "errors": []}],
    }

    # WHEN
    update_or_create_aggr_aed_info_and_delete_old_main_aed(new_resources, files_info)

    # THEN
    aed_info.refresh_from_db()
    assert AggregatedAEDInfo.objects.count() == 1
    assert aed_info.resource == new_resources[MAIN_AED_CSV]
    assert aed_info.xlsx_resource == new_resources[MAIN_AED_XLSX]
    assert aed_info.geojson_resource == new_resources[MAIN_AED_GEOJSON]
    assert aed_info.rows_count == 5
    assert aed_info.source_resources_count == 2
    assert aed_info.invalid_rows_count == 2
    assert aed_info.last_run_date is not None
    assert aed_info.validation_report == files_info["validation_report"]
    assert get_main_aed_resource() == new_resources[MAIN_AED_CSV]
    for old_resource in old_resources:
        assert Resource.raw.get(pk=old_resource.pk).is_removed is True


@pytest.mark.feat_main_aed
def test_api_aggregated_aed_info_not_found(client: TestClient):
    resp = client.simulate_get("/aggregated-aed-info/")
    assert resp.status == HTTP_NOT_FOUND


@pytest.mark.feat_main_aed
def test_api_aggregated_aed_info(client: TestClient):
    resource: Resource = ResourceFactory.create(status="published")
    AggregatedAEDInfoFactory.create(resource=resource, rows_count=5, source_resources_count=2)

    resp = client.simulate_get("/aggregated-aed-info/")

    assert resp.status == HTTP_OK, resp.json
    assert resp.json["resource_id"] == resource.pk
    assert resp.json["dataset_id"] == resource.dataset.pk
    assert resp.json["rows_count"] == 5
    assert resp.json["source_resources_count"] == 2
