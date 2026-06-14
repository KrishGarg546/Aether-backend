from django.db import models

# Create your models here.
class CampaignExecution(models.Model):
    STATUS_CHOICES = [
    ("SUCCESS", "Success"),
    ("PARTIAL_SUCCESS", "Partial Success"),
    ("FAILED", "Failed"),
]
    started_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(null=True, blank=True)

    duration_seconds = models.FloatField(null=True, blank=True)

    status = models.CharField(
    max_length=20,
    choices=STATUS_CHOICES,
    default="SUCCESS",
)
    goal = models.TextField()

    objective = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    campaign_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    audience_size = models.IntegerField(default=0)

    communications_generated = models.IntegerField(default=0)

    receipt_events_processed = models.IntegerField(default=0)

    recommendations = models.JSONField(default=list)
    raw_result = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.campaign_name or 'Campaign'} "
            f"({self.created_at:%Y-%m-%d %H:%M})"
        )