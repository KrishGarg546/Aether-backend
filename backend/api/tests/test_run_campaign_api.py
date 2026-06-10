from rest_framework import status
from rest_framework.test import APITestCase

from api.models import CampaignExecution


class TestRunCampaignAPI(APITestCase):
    """Integration tests for POST /api/run-campaign/."""

    def test_run_campaign_success(self):
        response = self.client.post(
            "/api/run-campaign/",
            {"goal": "bring back inactive customers"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("goal", response.data)
        self.assertIn("campaign_name", response.data)
        self.assertIn("objective", response.data)
        self.assertIn("communications_generated", response.data)
        self.assertIn("receipt_events_processed", response.data)
        self.assertIn("recommendations", response.data)

        self.assertEqual(
            CampaignExecution.objects.count(),
            1,
        )

    def test_run_campaign_missing_goal(self):
        response = self.client.post(
            "/api/run-campaign/",
            {},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ],
        )
