"""Fixed cryptographic namespace for server-owned DeepSeek credentials."""
from uuid import UUID, uuid5, NAMESPACE_URL

PLATFORM_ID = uuid5(NAMESPACE_URL, "izo-asa:platform-credential:deepseek:v1")
# UUID-zero is a deliberate non-account encryption namespace, NOT a user ID.
PLATFORM_NAMESPACE = UUID(int=0)
AAD_PROVIDER = "platform-deepseek"
