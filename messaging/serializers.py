from rest_framework import serializers
from .models import FarmerContact

class FarmerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmerContact
        fields = [
            'id', 
            'name', 
            'mobile', 
            'address', 
            'member_count', 
            'cultivated_area', 
            'major_crop', 
            'crop_of_interest',
            'status',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
       
        if not (request and request.user and request.user.is_staff):
            self.fields['status'].read_only = True