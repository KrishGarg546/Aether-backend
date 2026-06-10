from django.contrib import admin

# Register your models here.
from .models import CampaignExecution
@admin.register(CampaignExecution)
class CampaignExecutionAdmin(admin.ModelAdmin):

    list_display = (
        "campaign_name",
        "objective",
        "status",
        "audience_size",
        "communications_generated",
        "receipt_events_processed",
        "duration_seconds",
        "started_at",
    )

    list_filter = (
        "status",
        "objective",
        "started_at",
    )

    search_fields = (
        "goal",
        "campaign_name",
    )

    readonly_fields = (
        "started_at",
        "completed_at",
        "duration_seconds",
    )