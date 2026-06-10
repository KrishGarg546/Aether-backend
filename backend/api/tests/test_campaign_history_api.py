

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import CampaignExecution


class TestCampaignHistoryAPI(APITestCase):
    def setUp(self):
        CampaignExecution.objects.create(
            goal="bring back inactive customers",
            objective="reactivation",
            campaign_name="Aether WIN_BACK Campaign",
            audience_size=500,
            communications_generated=500,
            receipt_events_processed=1250,
            recommendations=["Recommendation 1"],
            status="SUCCESS",
        )

        CampaignExecution.objects.create(
            goal="reward loyal customers",
            objective="loyalty",
            campaign_name="Aether REWARDS Campaign",
            audience_size=500,
            communications_generated=500,
            receipt_events_processed=1145,
            recommendations=["Recommendation 2"],
            status="SUCCESS",
        )

    def test_get_campaign_history(self):
        response = self.client.get("/api/campaigns/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_campaign_history_contains_expected_fields(self):
        response = self.client.get("/api/campaigns/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        campaign = response.data[0]

        self.assertIn("id", campaign)
        self.assertIn("goal", campaign)
        self.assertIn("objective", campaign)
        self.assertIn("campaign_name", campaign)
        self.assertIn("status", campaign)