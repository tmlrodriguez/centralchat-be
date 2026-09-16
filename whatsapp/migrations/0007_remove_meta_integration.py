from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("whatsapp", "0006_remove_metaintegration_unique_company_meta_app_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="whatsappbusinessaccount",
            name="meta_integration",
        ),
        migrations.DeleteModel(
            name="MetaIntegration",
        ),
    ]
