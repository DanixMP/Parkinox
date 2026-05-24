from django.db import migrations


def seed_default_rates(apps, schema_editor):
    RateConfig = apps.get_model('parking', 'RateConfig')
    if not RateConfig.objects.exists():
        RateConfig.objects.create(
            name='Standard',
            rate_per_hour=5000,
            daily_cap=40000,
            grace_period_minutes=10,
            student_discount_percent=80,
            is_active=True,
        )


def unseed_default_rates(apps, schema_editor):
    RateConfig = apps.get_model('parking', 'RateConfig')
    RateConfig.objects.filter(name='Standard').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0002_rateconfig'),
    ]

    operations = [
        migrations.RunPython(seed_default_rates, unseed_default_rates),
    ]
