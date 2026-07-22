from django.contrib import admin

from .models import (
    Camera,
    Gate,
    Organization,
    ReplicaDetectionFail,
    ReplicaEventMedia,
    ReplicaGateEvent,
    ReplicaParkingSession,
    Site,
    SiteSyncCursor,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('site_id', 'name', 'capacity', 'last_ingest_at')


admin.site.register(Gate)
admin.site.register(Camera)
admin.site.register(ReplicaGateEvent)
admin.site.register(ReplicaParkingSession)
admin.site.register(ReplicaDetectionFail)
admin.site.register(ReplicaEventMedia)
admin.site.register(SiteSyncCursor)
