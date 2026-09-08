"""
logistics/api/address/serializers.py
====================================
Serializers for Ekart Warehouse / Pickup Addresses.
"""

from rest_framework import serializers
from logistics.models import EkartAddress

class EkartAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = EkartAddress
        fields = [
            'id', 'alias', 'phone', 'address_line1', 'address_line2', 
            'pincode', 'city', 'state', 'country', 'latitude', 'longitude'
        ]

    def validate_phone(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits.")
        return value