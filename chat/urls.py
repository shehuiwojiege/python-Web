from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^chat/records/$', views.ChatRecordsView.as_view()),
    url(r'^chat/records/(?P<sender_id>\d+)/$', views.AdminChatView.as_view()),
    url(r'^chat/unread/records/$', views.AdminUnreadRecordsView.as_view())
]