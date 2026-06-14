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


def execute_campaign(
    goal: str,
    audience_strategy: str = "AUTO",
    audience_size: int | None = None,
) -> dict:
    started_at = timezone.now()

    try:
        results = run_pipeline(
            goal,
            audience_strategy=audience_strategy,
            audience_size=audience_size,
        )
        response = build_api_response(results)

        response["audience_selection_mode"] = (
            "CUSTOM"
            if audience_strategy == "CUSTOM"
            else "AETHER_RECOMMENDED"
        )

        if audience_size is not None:
            response["requested_audience_size"] = audience_size

        audience_size = (
            response.get("audience_size")
            or response.get("customer_count")
            or response.get("communications_generated")
            or len(response.get("receipts", []))
            or 0
        )

        communications_generated = (
            response.get("communications_generated")
            or audience_size
        )

        receipt_events_processed = (
            response.get("receipt_events_processed")
            or communications_generated
        )

        response["audience_size"] = audience_size
        response[
            "communications_generated"
        ] = communications_generated
        response[
            "receipt_events_processed"
        ] = receipt_events_processed

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
        audience_size=audience_size,
        communications_generated=
        communications_generated,
        receipt_events_processed=
        receipt_events_processed,
        recommendations=(
            response.get("recommendations") or []
        ),
        raw_result=response,
        status=execution_status,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=(
            completed_at - started_at
        ).total_seconds(),
    )

    return response