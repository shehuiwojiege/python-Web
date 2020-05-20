# chat/consumers.py
import re
from django.conf import settings
from fdfs_client.client import Fdfs_client
from channels.exceptions import *
from calendar import timegm
from django_redis import get_redis_connection
from base64 import b64decode
from rest_framework_jwt.authentication import jwt_decode_handler
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
import json


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 获取url中的参数
        query_string = self.scope['query_string'].decode()
        params = query_string.split('&')

        item = {}
        for param in params:
            item[param.split('=')[0]] = param.split('=')[1]

        token = item.get('token')

        self.user_group = 'chat_'

        if token:
            try:
                payload = jwt_decode_handler(token)
            except:
                raise DenyConnection("签证错误")
            user_id = payload['user_id']
            user = await self.get_user(id=user_id)
            last_login = payload.get('last_login')
            if last_login != timegm(user.last_login.utctimetuple()):
                raise DenyConnection("签证已过期")

        else:
            user = self.scope['user']

        if not user:
            raise DenyConnection("用户不存在")

        receiver_name = item.get('receiver')
        if not receiver_name:
            raise DenyConnection("接收者名称错误")

        receiver = await self.get_user(username=receiver_name)
        if not receiver:
            raise DenyConnection("接收者不存在")

        self.receiver = receiver
        self.user = user

        # 远程组
        self.receiver_group = 'chat_%s_%s' % (self.receiver.username, self.user.username)

        # 用户组
        self.user_group = 'chat_%s_%s' % (self.user.username, self.receiver.username)

        # Join room group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        if message:
            # data:image/png;base64,i
            ret = re.findall('data:image/.*;base64,(.*)', message)
            if ret:
                user_pic_str = ret[0]
                image_src = await self.save_image_to_fdfs(user_pic_str)
                # 构造message
                message = '<img style="width: 80px; height: 60px" src="'+ image_src +'" data-preview-src="">'
            # Send message to room group

            chat_record = await self.save_model(self.user, self.receiver, message)

            if self.receiver.username == 'admin':
                '''为管理员添加消息提示'''
                await self.save_unread_records(chat_record, self.user)

            await self.channel_layer.group_send(
                # websocket发送消息
                self.receiver_group,
                {
                    'type': 'chat_message',
                    'message': message
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))

    @database_sync_to_async
    def save_model(self, sender, receiver, message):
        # 保存消息记录到数据库中
        from .models import ChatRecords
        return ChatRecords.objects.create(sender=sender, receiver=receiver, message=message)

    @database_sync_to_async
    def get_user(self, id=None, username=None):
        # 异步获取用户
        from users.models import User
        user = None
        if id:
            try:
                user = User.objects.get(id=id)
            except:
                return None
        if username:
            try:
                user = User.objects.get(username=username)
            except:
                return None
        return user

    async def save_unread_records(self, chat_record, sender):
        # 保存未读消息
        redis_conn = get_redis_connection('chatRecord')
        p = redis_conn.pipeline()
        p.rpush(sender.id, chat_record.id)
        p.set('new_records', 1)  # 在redis中添加未读标记
        p.execute()

    async def save_image_to_fdfs(self, pic_str):
        # 把图片存储到fastdfs文件系统中
        client = Fdfs_client(settings.FDFS_CLIENT_CONF)
        ret = client.upload_appender_by_buffer(b64decode(pic_str))
        if ret.get("Status") != "Upload successed.":
            raise Exception("upload file failed")
        file_name = ret.get("Remote file_id")
        return settings.FDFS_URL + file_name
