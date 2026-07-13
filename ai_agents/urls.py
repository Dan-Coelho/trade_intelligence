# ai_agents/urls.py — URLs do app ai_agents
#
# Tarefa 7.2.3 — Registra path('chat/', ChatView.as_view(), name='chat')

from django.urls import path

from ai_agents.views import ChatView

app_name = 'ai_agents'

urlpatterns = [
    # 7.2.3 — Endpoint de Chat IA
    # POST /ai/chat/   →  ChatView
    # Payload: { "ticker": "PETR4", "message": "..." }
    path('chat/', ChatView.as_view(), name='chat'),
]
