import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('parking', '0003_seed_default_rateconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperationalState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('season_started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_reset_at', models.DateTimeField(blank=True, null=True)),
                ('reset_count', models.PositiveIntegerField(default=0)),
                (
                    'last_reset_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='season_resets',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Operational state',
                'verbose_name_plural': 'Operational state',
                'db_table': 'operational_state',
            },
        ),
    ]
