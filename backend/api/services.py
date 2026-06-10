import os
import sys
from django.utils import timezone
from .models import CampaignExecution

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aether import run_pipeline, build_api_response


def execute_campaign(goal: str) -> dict:
    started_at = timezone.now()

    try:
        results = run_pipeline(goal)
        response = build_api_response(results)

        stage_status = response.get("stage_status", {})

        if any(
            status == "ERROR"
            for status in stage_status.values()
        ):
            execution_status = "FAILED"
        elif any(
            status == "SKIPPED"
            for status in stage_status.values()
        ):
            execution_status = "PARTIAL_SUCCESS"
        else:
            execution_status = "SUCCESS"

    except Exception:
        completed_at = timezone.now()

        CampaignExecution.objects.create(
            goal=goal,
            status="FAILED",
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(
                completed_at - started_at
            ).total_seconds(),
        )

        raise

    completed_at = timezone.now()

    CampaignExecution.objects.create(
        goal=response.get("goal") or "",
        objective=response.get("objective"),
        campaign_name=response.get("campaign_name"),
        audience_size=response.get("audience_size") or 0,
        communications_generated=(
            response.get("communications_generated") or 0
        ),
        receipt_events_processed=(
            response.get("receipt_events_processed") or 0
        ),
        recommendations=(
            response.get("recommendations") or []
        ),
        status=execution_status,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=(
            completed_at - started_at
        ).total_seconds(),
    )

    return response