from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CampaignExecution
from .serializers import CampaignRequestSerializer
from .services import execute_campaign


class RunCampaignView(APIView):
    """Execute the complete Aether pipeline for a marketer goal."""

    def post(self, request):
        serializer = CampaignRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        goal: str = serializer.validated_data["goal"]

        try:
            result = execute_campaign(goal)
            return Response(result, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {
                    "error": "Campaign execution failed.",
                    "details": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CampaignHistoryView(APIView):
    """Return a list of previously executed campaigns."""

    def get(self, request):
        campaigns = CampaignExecution.objects.order_by(
            "-started_at"
        ).values(
            "id",
            "goal",
            "objective",
            "campaign_name",
            "status",
            "audience_size",
            "started_at",
        )

        return Response(
            list(campaigns),
            status=status.HTTP_200_OK,
        )


class CampaignDetailView(APIView):
    """Return detailed information for a single campaign."""

    def get(self, request, campaign_id):
        try:
            campaign = CampaignExecution.objects.get(
                id=campaign_id
            )
        except CampaignExecution.DoesNotExist:
            return Response(
                {
                    "error": "Campaign not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "id": campaign.id,
                "goal": campaign.goal,
                "objective": campaign.objective,
                "campaign_name": campaign.campaign_name,
                "audience_size": campaign.audience_size,
                "communications_generated": campaign.communications_generated,
                "receipt_events_processed": campaign.receipt_events_processed,
                "recommendations": campaign.recommendations,
                "status": campaign.status,
                "started_at": campaign.started_at,
                "completed_at": campaign.completed_at,
                "duration_seconds": campaign.duration_seconds,
            },
            status=status.HTTP_200_OK,
        )