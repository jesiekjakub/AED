# MISJA AED – instytucja-właściciel zbioru „Wykaz zbiorczy defibrylatorów AED” (jak MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK)
from django.conf import settings
from mcod.organizations.models import Organization
pk = int(settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK)
org = Organization.objects.filter(pk=pk).first()
if not org:
    org = Organization.objects.create(pk=pk, title="Ministerstwo Cyfryzacji", slug="ministerstwo-cyfryzacji", institution_type="state",
                                      email="kontakt@cyfra.gov.pl", city="Warszawa", postal_code="00-060", street="Królewska",
                                      street_number="27", regon="525189465", website="https://www.gov.pl/web/cyfryzacja", status="published")
print("Właściciel wykazu:", org.pk, org.title)
