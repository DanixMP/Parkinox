import uuid

from django.db import models
from django.utils import timezone


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Site(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sites')
    site_id = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200, default='Main parking')
    capacity = models.PositiveIntegerField(default=100)
    last_ingest_at = models.DateTimeField(null=True, blank=True)
    season_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.site_id})'


class Gate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='gates')
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=100, blank=True, default='')
    direction = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        unique_together = [('site', 'code')]

    def __str__(self):
        return f'{self.site.site_id}:{self.code}'


class Camera(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='cameras')
    camera_id = models.CharField(max_length=64)
    gate = models.ForeignKey(Gate, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        unique_together = [('site', 'camera_id')]

    def __str__(self):
        return f'{self.site.site_id}:{self.camera_id}'


class ReplicaGateEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='gate_events')
    event_uuid = models.UUIDField()
    occurred_at = models.DateTimeField(null=True, blank=True, db_index=True)
    direction = models.CharField(max_length=10)
    camera_id = models.CharField(max_length=64, blank=True, default='')
    plate_raw = models.CharField(max_length=32, blank=True, default='')
    plate_confirmed = models.CharField(max_length=32, blank=True, default='', db_index=True)
    confidence = models.FloatField(null=True, blank=True)
    was_edited = models.BooleanField(default=False)
    was_auto_approved = models.BooleanField(default=False)
    was_rejected = models.BooleanField(default=False)
    session_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    operator_name = models.CharField(max_length=200, blank=True, default='')
    matched_user_name = models.CharField(max_length=200, blank=True, default='')
    local_gate_event_id = models.IntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'event_uuid'], name='replica_gate_site_uuid_uniq'),
        ]
        indexes = [
            models.Index(fields=['site', '-occurred_at']),
            models.Index(fields=['site', 'direction', '-occurred_at']),
        ]

    def __str__(self):
        return f'{self.direction} {self.plate_confirmed} {self.event_uuid}'


class ReplicaParkingSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='sessions')
    session_uuid = models.UUIDField()
    plate_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
    user_name = models.CharField(max_length=200, blank=True, default='')
    entry_time = models.DateTimeField(null=True, blank=True, db_index=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    fee_charged = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, default='parked', db_index=True)
    payment_method = models.CharField(max_length=20, blank=True, default='')
    entry_event_uuid = models.UUIDField(null=True, blank=True)
    exit_event_uuid = models.UUIDField(null=True, blank=True)
    entry_camera_id = models.CharField(max_length=64, blank=True, default='')
    exit_camera_id = models.CharField(max_length=64, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    local_session_id = models.IntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'session_uuid'], name='replica_session_site_uuid_uniq'),
        ]
        indexes = [
            models.Index(fields=['site', 'status', '-entry_time']),
        ]

    def __str__(self):
        return f'{self.plate_number} [{self.status}]'


class ReplicaDetectionFail(models.Model):
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='detection_fails')
    fail_uuid = models.UUIDField()
    fail_type = models.CharField(max_length=64, blank=True, default='')
    review_status = models.CharField(max_length=32, blank=True, default='pending')
    camera_id = models.CharField(max_length=64, blank=True, default='')
    direction = models.CharField(max_length=10, blank=True, default='')
    raw_ocr = models.CharField(max_length=64, blank=True, default='')
    was_corrected = models.BooleanField(default=False)
    captured_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'fail_uuid'], name='replica_fail_site_uuid_uniq'),
        ]


class ReplicaEventMedia(models.Model):
    IMAGE_TYPES = [
        ('scene_a', 'Scene A'),
        ('scene_b', 'Scene B'),
        ('crop', 'Crop'),
        ('thumbnail', 'Thumbnail'),
        ('fail_full', 'Fail full'),
        ('fail_crop', 'Fail crop'),
        ('fail_scene_b', 'Fail scene B'),
    ]

    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='event_media')
    event_uuid = models.UUIDField(db_index=True)
    session_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPES)
    object_key = models.CharField(max_length=1024, blank=True, default='')
    content_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    size_bytes = models.PositiveIntegerField(default=0)
    upload_status = models.CharField(max_length=20, default='uploaded')
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'event_uuid', 'image_type'],
                name='replica_media_site_event_type_uniq',
            ),
        ]


class SiteSyncCursor(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='sync_cursor')
    last_event_at = models.DateTimeField(null=True, blank=True)
    last_reconcile_at = models.DateTimeField(null=True, blank=True)
    events_received = models.PositiveIntegerField(default=0)
    images_received = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
