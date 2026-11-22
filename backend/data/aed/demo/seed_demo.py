# MISJA AED – dane demonstracyjne dla lokalnego portalu: 5 dysponentów publikuje zasoby z flagą „wykaz AED”.
# Uruchom: docker compose -f docker-compose.local.yml run --rm mcod-local-run python manage.py shell -c "exec(open('data/aed/demo/seed_demo.py').read())"
import datetime
import os

from django.core.files import File

from mcod.categories.models import Category
from mcod.datasets.models import Dataset
from mcod.licenses.models import License
from mcod.organizations.models import Organization
from mcod.resources.models import Resource, ResourceFile
from mcod.tags.models import Tag

KAT = "data/aed/demo"
DYSPONENCI = [
    ("aed_siemianowice.csv", "Urząd Miasta Siemianowice Śląskie", "siemianowice-slaskie"),
    ("aed_legionowo.csv", "Urząd Miasta Legionowo", "legionowo"),
    ("aed_lodz.csv", "Urząd Miasta Łodzi", "lodz"),
    ("aed_slupsk.csv", "Urząd Miejski w Słupsku", "slupsk"),
    ("aed_krakow.csv", "Urząd Miasta Krakowa", "krakow"),
]

kategoria = Category.objects.filter(code="HEAL").first() or Category.objects.first()
licencja = License.objects.first()
tag_aed, _ = Tag.objects.get_or_create(name="misja-aed", language="pl")

for plik, instytucja, slug in DYSPONENCI:
    org, _ = Organization.objects.get_or_create(
        slug=f"aed-{slug}",
        defaults=dict(title=instytucja, institution_type="local", email=f"kontakt@{slug}.example.pl", city=instytucja.split()[-1],
                      postal_code="00-000", street="Rynek", street_number="1", regon="000000000", website="https://example.pl",
                      status="published", description=f"Dysponent danych o AED – {instytucja}"),
    )
    ds, _ = Dataset.objects.get_or_create(
        slug=f"defibrylatory-aed-{slug}",
        defaults=dict(title=f"Defibrylatory AED – {instytucja}", organization=org, category=kategoria, license=licencja,
                      notes="Wykaz automatycznych defibrylatorów zewnętrznych (AED) zgodny ze wzorcowym zakresem danych Misji AED.",
                      update_frequency="monthly", status="published"),
    )
    ds.tags.add(tag_aed)
    istniejacy = Resource.objects.filter(dataset=ds, contains_aed_list=True).first()
    if istniejacy:
        mf = istniejacy.main_file
        if mf and os.path.exists(mf.path):
            print("istnieje:", ds.title)
            continue
        istniejacy.files.all().delete()   # plik utworzony w kontenerze bez wolumenu media – odtwarzamy
        with open(os.path.join(KAT, plik), "rb") as f:
            ResourceFile.objects.create(resource=istniejacy, file=File(f, name=plik), format="csv", mimetype="text/csv", is_main=True, openness_score=3)
        print("odtworzono plik:", ds.title)
        continue
    res = Resource.objects.create(
        dataset=ds, title=f"Wykaz AED – {instytucja}", description="Lokalizacje i dostępność defibrylatorów AED (CSV, wzorzec Misja AED).",
        format="csv", type="file", status="published", contains_aed_list=True, data_date=datetime.date.today(), openness_score=3,
    )
    with open(os.path.join(KAT, plik), "rb") as f:
        ResourceFile.objects.create(resource=res, file=File(f, name=plik), format="csv", mimetype="text/csv", is_main=True, openness_score=3)
    print("utworzono:", ds.title, "-> zasób", res.pk)

print("Zasobów z flagą wykaz AED:", Resource.objects.filter(contains_aed_list=True).count())
