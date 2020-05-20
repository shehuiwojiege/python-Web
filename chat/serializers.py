from rest_framework import serializers
from .models import ChatRecords


class ChatRecordsSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(read_only=True)
    receiver_name = serializers.CharField(read_only=True)

    class Meta:
        model = ChatRecords
        fields = ('id', 'sender_name', 'receiver_name', 'message', 'create_time')
        extra_kwargs = {
            'create_time': {
                'read_only': True,
                'format': '%Y-%m-%d %H:%M'
            },
        }


