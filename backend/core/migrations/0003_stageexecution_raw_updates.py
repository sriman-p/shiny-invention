from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_agent_model_selection"),
    ]

    operations = [
        migrations.AddField(
            model_name="stageexecution",
            name="raw_updates",
            field=models.JSONField(default=list),
        ),
    ]
