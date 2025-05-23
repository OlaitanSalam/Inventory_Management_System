# Generated by Django 5.1 on 2025-04-30 16:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("store", "0002_alter_item_options_alter_item_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendor",
            name="store",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="store.store",
                verbose_name="Associated Store",
            ),
        ),
    ]
