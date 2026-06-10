from rest_framework import serializers


class CampaignRequestSerializer(serializers.Serializer):
    """Validate incoming campaign execution requests."""

    goal = serializers.CharField(max_length=500)