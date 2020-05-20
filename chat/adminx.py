import xadmin

from .views import ChatView


xadmin.site.register_view(r'chat/$', ChatView, name='chat')

