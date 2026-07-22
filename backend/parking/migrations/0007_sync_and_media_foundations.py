# Additive sync / media foundations — safe for existing DBs (nullable UUIDs + new tables).

import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_uuids(apps, schema_editor):
    GateEvent = apps.get_model('parking', 'GateEvent')
    ParkingSession = apps.get_model('parking', 'ParkingSession')
    for pk in GateEvent.objects.filter(event_uuid__isnull=True).values_list('pk', flat=True).iterator():
        GateEvent.objects.filter(pk=pk, event_uuid__isnull=True).update(event_uuid=uuid.uuid4())
    for pk in ParkingSession.objects.filter(session_uuid__isnull=True).values_list('pk', flat=True).iterator():
        ParkingSession.objects.filter(pk=pk, session_uuid__isnull=True).update(
            session_uuid=uuid.uuid4()
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0006_detectionfail_scene_b'),
    ]

    operations = [
        # Step 1: nullable, non-unique — avoids SQLite single-default collision
        migrations.AddField(
            model_name='gateevent',
            name='event_uuid',
            field=models.UUIDField(
                blank=True,
                help_text='Stable UUID for cloud sync / outbox idempotency',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='parkingsession',
            name='session_uuid',
            field=models.UUIDField(
                blank=True,
                help_text='Stable UUID for cloud sync / outbox idempotency',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_uuids, noop_reverse),
        # Step 2: unique + index after per-row backfill
        migrations.AlterField(
            model_name='gateevent',
            name='event_uuid',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                default=uuid.uuid4,
                help_text='Stable UUID for cloud sync / outbox idempotency',
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='parkingsession',
            name='session_uuid',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                default=uuid.uuid4,
                help_text='Stable UUID for cloud sync / outbox idempotency',
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name='EventMedia',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('event_uuid', models.UUIDField(db_index=True)),
                ('session_uuid', models.UUIDField(blank=True, db_index=True, null=True)),
                ('image_type', models.CharField(
                    choices=[
                        ('scene_a', 'Scene A'),
                        ('scene_b', 'Scene B'),
                        ('crop', 'Plate crop'),
                        ('thumbnail', 'Thumbnail'),
                    ],
                    max_length=20,
                )),
                ('local_path', models.CharField(blank=True, default='', max_length=1024)),
                ('content_hash', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('size_bytes', models.PositiveIntegerField(default=0)),
                ('upload_status', models.CharField(
                    choices=[
                        ('local_only', 'Local only'),
                        ('pending', 'Pending upload'),
                        ('uploaded', 'Uploaded'),
                        ('failed', 'Failed'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('captured_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('gate_event', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='event_media',
                    to='parking.gateevent',
                )),
            ],
            options={
                'verbose_name': 'Event media',
                'verbose_name_plural': 'Event media',
                'db_table': 'event_media',
            },
        ),
        migrations.CreateModel(
            name='SyncOutbox',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('payload_type', models.CharField(
                    choices=[
                        ('gate_event', 'Gate event'),
                        ('parking_session', 'Parking session'),
                        ('event_media', 'Event media'),
                        ('detection_fail', 'Detection fail'),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ('payload_uuid', models.UUIDField(db_index=True)),
                ('body_json', models.JSONField(default=dict)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('sending', 'Sending'),
                        ('acked', 'Acked'),
                        ('dead_letter', 'Dead letter'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(
                    db_index=True,
                    default=django.utils.timezone.now,
                )),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('acked_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Sync outbox',
                'verbose_name_plural': 'Sync outbox',
                'db_table': 'sync_outbox',
            },
        ),
        migrations.CreateModel(
            name='SyncState',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('last_error_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True, default='')),
                ('pending_metadata_count', models.PositiveIntegerField(default=0)),
                ('pending_image_count', models.PositiveIntegerField(default=0)),
                ('dead_letter_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Sync state',
                'verbose_name_plural': 'Sync state',
                'db_table': 'sync_state',
            },
        ),
        migrations.AddIndex(
            model_name='eventmedia',
            index=models.Index(fields=['upload_status', '-created_at'], name='event_media_upload__7a3c1a_idx'),
        ),
        migrations.AddConstraint(
            model_name='eventmedia',
            constraint=models.UniqueConstraint(
                fields=('event_uuid', 'image_type'),
                name='event_media_uuid_type_uniq',
            ),
        ),
        migrations.AddIndex(
            model_name='syncoutbox',
            index=models.Index(
                fields=['status', 'next_attempt_at', 'payload_type'],
                name='sync_outbox_status_4e2b1c_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='syncoutbox',
            index=models.Index(
                fields=['payload_type', 'payload_uuid'],
                name='sync_outbox_payload_9f1a2b_idx',
            ),
        ),
    ]
