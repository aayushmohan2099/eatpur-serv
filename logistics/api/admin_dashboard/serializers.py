"""
logistics/api/admin_dashboard/serializers.py
============================================
Serializers for audit logs and analytics.
"""

from rest_framework import serializers
from logistics.models import LogisticsAPILog

class LogisticsAPILogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsAPILog
        fields = [
            "id", 
            "endpoint", 
            "method", 
            "status_code", 
            "response_time_ms", 
            "created_at",
            "request_payload",
            "response_payload"
        ]