# MISJA AED
# Generated manually (Django 2.2.9 style) on 2026-11-22

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0075_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="contains_aed_list",
            field=models.BooleanField(default=False, verbose_name="Zasób zawiera wykaz AED (Misja AED)"),
        ),
        migrations.CreateModel(
            name="AggregatedAEDInfo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_run_date", models.DateTimeField(blank=True, null=True)),
                ("source_resources_count", models.PositiveIntegerField(default=0)),
                ("aggregated_resources_count", models.PositiveIntegerField(default=0)),
                ("rows_count", models.PositiveIntegerField(default=0)),
                ("invalid_rows_count", models.PositiveIntegerField(default=0)),
                ("geo_rows_count", models.PositiveIntegerField(default=0)),
                (
                    "validation_report",
                    django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=list),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="resources.Resource",
                    ),
                ),
                (
                    "xlsx_resource",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="resources.Resource",
                    ),
                ),
                (
                    "geojson_resource",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="resources.Resource",
                    ),
                ),
            ],
        ),
    ]
