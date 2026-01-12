from langchain_community.chat_message_histories import RedisChatMessageHistory
from app.core.config import settings

print(f"Testing RedisChatMessageHistory with URL: {settings.redis_url}")

try:
    history = RedisChatMessageHistory(
        session_id="test_session",
        url=settings.redis_url,
        ttl=settings.redis_memory_ttl
    )
    print("SUCCESS: RedisChatMessageHistory created!")
    print(f"Messages: {history.messages}")
except Exception as e:
    print(f"ERROR: {e}")
