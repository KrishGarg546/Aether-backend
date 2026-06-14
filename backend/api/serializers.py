from rest_framework import serializers


class CampaignRequestSerializer(serializers.Serializer):
    """Validate incoming campaign execution requests."""

    goal = serializers.CharField(max_length=500)
    audience_strategy = serializers.ChoiceField(
        choices=["AUTO", "CUSTOM"],
        required=False,
        default="AUTO",
    )
    audience_size = serializers.IntegerField(
        required=False,
        min_value=1,
    )