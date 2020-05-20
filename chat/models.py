from django.db import models
from users.models import User

# Create your models here.


class ChatRecords(models.Model):
    '''在线客服聊天记录模型类'''
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='send_records', verbose_name='发送者', null=False)
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receive_records', verbose_name='接收者', null=False)
    message = models.TextField(verbose_name='聊天信息')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = "tb_chat_records"
        verbose_name = '客服聊天记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.id