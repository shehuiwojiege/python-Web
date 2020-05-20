import time
from django.db.models import Q
from django.shortcuts import render
from rest_framework import status
from users.models import User
from django.conf import settings
from datetime import datetime
from .models import ChatRecords
from .serializers import ChatRecordsSerializer
from django_redis import get_redis_connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from xadmin.views import BaseAdminView

# Create your views here.


class AdminUnreadRecordsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        '''ajax长轮训获取用户未读消息记录'''
        admin = request.user

        timeout = request.data['timeout']

        redis_conn = get_redis_connection('chatRecord')

        # 记录开始时间
        s_time = int(time.time())
        while True:

            # 查询指定字段为sender之后去重拿到sender_id的列表, 格式为[{'sender': 1}, {'sender': 2}]
            senders_dict = ChatRecords.objects.filter(receiver=admin).values('sender').distinct()

            # 记录循环进来时间
            e_time = int(time.time())

            if e_time-s_time >= int(timeout):
                # 循环时间到30s以上 立刻退出
                break

            flag = redis_conn.exists('new_records')
            if flag:
                # 有新消息
                redis_conn.delete('new_records')
                break
            else:
                time.sleep(1)
                continue

        # 有消息, 进行长轮训
        senders = []

        for sd in senders_dict:
            item = {}
            sender_id = sd['sender']
            item['count'] = redis_conn.llen(sender_id)
            sender = User.objects.get(id=sender_id)
            item['username'] = sender.username
            item['sender_id'] = sender.id
            item['user_id'] = sender.id
            item['user_pic'] = settings.FDFS_URL + str(sender.user_pic) if sender.user_pic else None
            last_record_ids = redis_conn.lrange(sender.id, 0, -1)

            if last_record_ids:
                '''redis中存在最新消息记录'''
                record = ChatRecords.objects.filter(id=int(last_record_ids[-1])).first()
                if not record:
                    return Response({'message': 'redis数据库或者mysql数据库出错'}, status=status.HTTP_400_BAD_REQUEST)
                item['last_send_message'] = record.message
            else:
                '''redis中不存在最新消息'''
                record = ChatRecords.objects.filter(Q(sender=sender)|Q(receiver=sender)).last()
                if not record:
                    return Response({'message': 'redis数据库或者mysql数据库出错'}, status=status.HTTP_400_BAD_REQUEST)
                item['last_send_message'] = None
            item['last_send_time'] = record.create_time.strftime('%Y-%m-%d %M:%H')
            senders.append(item)
        senders.sort(key=lambda x: x['last_send_time'], reverse=True)

        return Response(senders)


class ChatRecordsView(GenericAPIView):
    '''用户获取聊天记录'''
    permission_classes = [IsAuthenticated]
    serializer_class = ChatRecordsSerializer

    def get_queryset(self):
        user = self.request.user
        send_records = user.send_records.all()
        receive_records = user.receive_records.all()
        records = send_records | receive_records  # 合并查询集
        records = records.order_by('-create_time')
        for record in records:
            record.sender_name = record.sender.username
            record.receiver_name = record.receiver.username
        return records

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        page = sorted(page, key=lambda x:x.create_time)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AdminChatView(GenericAPIView):
    '''管理员获取聊天记录'''
    permission_classes = [IsAuthenticated]
    serializer_class = ChatRecordsSerializer

    def get_queryset(self):
        sender_id = self.kwargs['sender_id']
        records = ChatRecords.objects.filter(Q(receiver_id=1, sender_id=sender_id) | Q(receiver_id=sender_id, sender_id=1)).order_by('-create_time')
        for record in records:
            record.sender_name = record.sender.username
            record.receiver_name = record.receiver.username
        return records

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        page = sorted(page, key=lambda x:x.create_time)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def delete(self, request, sender_id):
        # 删除redis中未读消息记录
        redis_conn = get_redis_connection('chatRecord')
        redis_conn.delete(sender_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatView(BaseAdminView):
    permission_classes = [IsAuthenticated]

    '''后台新添一个客服聊天页面'''
    def get(self, request):
        return render(request, 'chat/index.html')
