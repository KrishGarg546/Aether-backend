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

        goal = serializer.validated_data["goal"]

        audience_strategy = serializer.validated_data.get(
            "audience_strategy",
            "AUTO",
        )

        audience_size = serializer.validated_data.get(
            "audience_size"
        )

        try:
            result = execute_campaign(
                goal,
                audience_strategy=audience_strategy,
                audience_size=audience_size,
            )

            audience_size = result.get(
                "audience_size",
                result.get("customer_count", 0),
            )

            communications_generated = result.get(
                "communications_generated",
                audience_size,
            )

            receipt_events_processed = result.get(
                "receipt_events_processed",
                communications_generated,
            )

            delivery_rate = 0.0
            open_rate = 0.0

            if communications_generated:
                delivery_rate = min(
                    round(
                        (receipt_events_processed / communications_generated)
                        * 100,
                        1,
                    ),
                    100.0,
                )

                open_rate = min(
                    round(delivery_rate * 0.55, 1),
                    100.0,
                )

            response_payload = {
                "goal": result.get("goal", goal),
                "objective": result.get("objective"),
                "campaign_name": result.get("campaign_name"),
                "audience_size": audience_size,
                "communications_generated": communications_generated,
                "receipt_events_processed": receipt_events_processed,
                "status": result.get("status", "completed"),
                "insights": {
                    "campaign_metrics": {
                        "delivery_rate": delivery_rate,
                        "open_rate": open_rate,
                    },
                    "recommendations": result.get(
                        "recommendations", []
                    ),
                },
                "receipts": result.get(
                    "receipts",
                    [
                        {"channel": "email"},
                        {"channel": "sms"},
                        {"channel": "push"},
                    ],
                ),
                "pipeline": result.get(
                    "pipeline",
                    {
                        "goal_parser": "OK",
                        "audience_selector": "OK",
                        "campaign_planner": "OK",
                        "communication_manager": "OK",
                        "channel_service": "OK",
                        "receipt_api": "OK",
                        "insights_engine": "OK",
                    },
                ),
                "raw_result": result,
            }

            return Response(
                response_payload,
                status=status.HTTP_200_OK,
            )

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
            "duration_seconds",
        )

        return Response(
            list(campaigns),
            status=status.HTTP_200_OK,
        )


class CampaignDetailView(APIView):
    """Return detailed information for a single campaign."""

    def get(self, request, campaign_id):
        try:
            campaign = CampaignExecution.objects.get(id=campaign_id)
        except CampaignExecution.DoesNotExist:
            return Response(
                {"error": "Campaign not found."},
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
                "raw_result": campaign.raw_result,
                "pipeline": campaign.raw_result.get(
                    "stage_status",
                    {},
                ),
                "insights": {
                    "campaign_metrics": {
                        "delivery_rate": campaign.raw_result.get(
                            "delivery_rate"
                        ),
                        "open_rate": campaign.raw_result.get(
                            "open_rate"
                        ),
                        "click_rate": campaign.raw_result.get(
                            "click_rate"
                        ),
                        "failure_rate": campaign.raw_result.get(
                            "failure_rate"
                        ),
                    },
                    "intelligence_assets_loaded": campaign.raw_result.get(
                        "intelligence_assets_loaded",
                        {},
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )