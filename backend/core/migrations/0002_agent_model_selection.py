from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentconfig",
            name="model_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="stageexecution",
            name="model_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
