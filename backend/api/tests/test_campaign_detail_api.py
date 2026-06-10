

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import CampaignExecution


class TestCampaignDetailAPI(APITestCase):
    def setUp(self):
        self.campaign = CampaignExecution.objects.create(
            goal="bring back inactive customers",
            objective="reactivation",
            campaign_name="Aether WIN_BACK Campaign",
            audience_size=500,
            communications_generated=500,
            receipt_events_processed=1250,
            recommendations=["Recommendation 1"],
            status="SUCCESS",
        )

    def test_get_campaign_detail(self):
        response = self.client.get(
            f"/api/campaigns/{self.campaign.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.campaign.id)
        self.assertEqual(
            response.data["campaign_name"],
            "Aether WIN_BACK Campaign",
        )

    def test_campaign_detail_returns_404_for_invalid_id(self):
        response = self.client.get("/api/campaigns/99999/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )