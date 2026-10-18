"""Serializers for the invoice extraction endpoint."""
from rest_framework import serializers


class FieldResultSerializer(serializers.Serializer):
    value             = serializers.CharField(allow_null=True, default=None)
    evidence          = serializers.CharField(allow_null=True, default=None)
    confidence        = serializers.ChoiceField(
        choices=["medium", "low", "absent"], default="absent"
    )
    validation_errors = serializers.ListField(
        child=serializers.CharField(), default=list
    )


class ExtractionResultSerializer(serializers.Serializer):
    extraction_id        = serializers.UUIDField()
    provider_used        = serializers.CharField()
    model_used           = serializers.CharField()
    verification_status  = serializers.ChoiceField(
        choices=["not_configured", "passed", "warnings", "failed", "partial"]
    )
    verification_message = serializers.CharField()
    raw_text_extracted   = serializers.BooleanField()
    fields               = serializers.DictField(child=FieldResultSerializer())
    cross_field_errors   = serializers.ListField(
        child=serializers.CharField(), default=list
    )
    warnings             = serializers.ListField(
        child=serializers.CharField(), default=list
    )
