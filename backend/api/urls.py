from django.urls import path

from .views import (
    RunCampaignView,
    CampaignHistoryView,
    CampaignDetailView,
)

urlpatterns = [
    path(
        "run-campaign/",
        RunCampaignView.as_view(),
        name="run-campaign",
    ),

    path(
        "campaigns/",
        CampaignHistoryView.as_view(),
        name="campaign-history",
    ),

    path(
        "campaigns/<int:campaign_id>/",
        CampaignDetailView.as_view(),
        name="campaign-detail",
    ),
]