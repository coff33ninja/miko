#!/usr/bin/env python3
"""
Demo script showing how to use the MemoryManager for conversation memory.
This example demonstrates the key features of the memory management system.
"""

import asyncio
import logging
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory import MemoryManager, ConversationMessage
from src.config.settings import MemoryConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_memory_manager():
    """Demonstrate MemoryManager functionality."""

    print("🧠 Anime AI Character Memory Management Demo")
    print("=" * 50)

    # Create memory configuration (without API key for demo)
    config = MemoryConfig(
        mem0_api_key="",  # Empty for session-only demo
        mem0_collection="demo_collection",
        memory_history_limit=5,
    )

    # Initialize memory manager
    manager = MemoryManager(config)
    mem0_available = await manager.initialize()

    print(f"Memory system initialized (Mem0 available: {mem0_available})")
    print()

    # Demo user
    user_id = "demo_user"

    # 1. Store some conversation messages
    print("📝 Storing conversation messages...")

    messages = [
        ConversationMessage(
            role="user",
            content="Hi! My name is Alex and I love anime.",
            timestamp=datetime.now(),
            user_id=user_id,
        ),
        ConversationMessage(
            role="assistant",
            content="Nice to meet you Alex! I love anime too! What's your favorite series?",
            timestamp=datetime.now(),
            user_id=user_id,
            sentiment="friendly",
        ),
        ConversationMessage(
            role="user",
            content="I really enjoy Attack on Titan and Your Name.",
            timestamp=datetime.now(),
            user_id=user_id,
        ),
        ConversationMessage(
            role="assistant",
            content="Great choices! Attack on Titan has such an intense story. Your Name made me cry! (*emotional*)",
            timestamp=datetime.now(),
            user_id=user_id,
            sentiment="emotional",
        ),
    ]

    for message in messages:
        await manager.store_conversation(message)
        print(f"  Stored: {message.role} - {message.content[:50]}...")

    print()

    # 2. Get user context
    print("🔍 Retrieving user context...")
    context = await manager.get_user_context(user_id, "anime preferences")

    print(f"User: {context.user_id}")
    print(f"Conversation history: {len(context.conversation_history)} messages")
    print(f"Relevant memories: {len(context.relevant_memories)} items")

    # Format context for AI
    ai_context = context.format_for_ai()
    if ai_context:
        print("\nFormatted context for AI:")
        print(ai_context)
    else:
        print("No context available for AI formatting")

    print()

    # 3. Update personality state
    print("🎭 Updating personality state...")
    await manager.update_personality_state(
        user_id,
        {
            "favorite_anime": ["Attack on Titan", "Your Name"],
            "mood": "excited",
            "user_name": "Alex",
        },
    )

    # Get updated context
    updated_context = await manager.get_user_context(user_id)
    print(f"Personality state: {updated_context.personality_state}")
    print()

    # 4. Test memory pruning
    print("✂️ Testing memory pruning...")

    # Add more messages to trigger pruning (limit is 5)
    for i in range(3):
        extra_message = ConversationMessage(
            role="user",
            content=f"Extra message {i + 1}",
            timestamp=datetime.now(),
            user_id=user_id,
        )
        await manager.store_conversation(extra_message)

    final_context = await manager.get_user_context(user_id)
    print(
        f"Messages after pruning: {len(final_context.conversation_history)} (limit: {config.memory_history_limit})"
    )

    # Show remaining messages
    for msg in final_context.conversation_history:
        print(f"  - {msg.role}: {msg.content[:30]}...")

    print()

    # 5. Get session statistics
    print("📊 Session statistics...")
    stats = manager.get_session_stats()
    print(f"Total users: {stats['total_users']}")
    print(f"Total messages: {stats['total_messages']}")
    print(f"Mem0 available: {stats['mem0_available']}")

    for uid, user_stats in stats["users"].items():
        print(f"  User {uid}: {user_stats['message_count']} messages")

    print()

    # 6. Health check
    print("🏥 Health check...")
    health = await manager.health_check()
    print(f"Status: {health['status']}")
    print(f"Mem0 available: {health['mem0_available']}")
    print(f"Session memory active: {health['session_memory_active']}")

    if health["errors"]:
        print("Errors:")
        for error in health["errors"]:
            print(f"  - {error}")

    print()

    # 7. Cleanup demo
    print("🧹 Cleaning up demo data...")
    deleted = await manager.delete_user_memories(user_id)
    print(f"User memories deleted: {deleted}")

    final_stats = manager.get_session_stats()
    print(f"Final message count: {final_stats['total_messages']}")

    print("\n✅ Demo completed!")


if __name__ == "__main__":
    asyncio.run(demo_memory_manager())
