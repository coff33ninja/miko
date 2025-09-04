#!/usr/bin/env python3
"""
Example showing how MemoryManager integrates with AI providers for conversation context.
This demonstrates the complete flow of memory-enhanced AI conversations.
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


class MockAIProvider:
    """Mock AI provider for demonstration purposes."""
    
    def __init__(self, personality_prompt: str):
        self.personality_prompt = personality_prompt
    
    async def generate_response(self, user_message: str, context: str = "") -> str:
        """Generate a mock AI response based on context."""
        
        # Simple rule-based responses for demo
        user_lower = user_message.lower()
        
        if "name" in user_lower and ("my" in user_lower or "i'm" in user_lower or "i am" in user_lower):
            return "Nice to meet you! I'll remember your name. What would you like to talk about? (*smile*)"
        
        elif "anime" in user_lower:
            if "attack on titan" in user_lower or "your name" in user_lower:
                return "Oh, I see you mentioned those before! You have great taste in anime! (*excited*)"
            else:
                return "Anime is amazing! I love discussing different series. What's your favorite? (*sparkle*)"
        
        elif "remember" in user_lower or "recall" in user_lower:
            if context and "favorite_anime" in context:
                return "Of course I remember! You love Attack on Titan and Your Name! (*proud*)"
            else:
                return "I try my best to remember our conversations! (*thoughtful*)"
        
        elif "joke" in user_lower:
            return "Why don't scientists trust atoms? Because they make up everything! (*giggle*) B-baka, that was terrible wasn't it?"
        
        else:
            return "That's interesting! Tell me more about that. (*curious*)"


async def simulate_conversation():
    """Simulate a conversation with memory integration."""
    
    print("🤖 Memory-Enhanced AI Conversation Demo")
    print("=" * 45)
    
    # Initialize memory manager
    config = MemoryConfig(
        mem0_api_key="",  # Session-only for demo
        mem0_collection="conversation_demo",
        memory_history_limit=10
    )
    
    memory_manager = MemoryManager(config)
    await memory_manager.initialize()
    
    # Initialize mock AI
    personality = "You are a tsundere anime girl named Miko. Respond with anime flair and emotes."
    ai_provider = MockAIProvider(personality)
    
    user_id = "conversation_user"
    
    print("Starting conversation simulation...\n")
    
    # Conversation turns
    conversation_turns = [
        "Hi there! My name is Sarah.",
        "I love watching anime in my free time.",
        "My favorites are Attack on Titan and Your Name.",
        "Do you remember what I told you about my favorite anime?",
        "Can you tell me a joke?",
        "What do you think about anime in general?"
    ]
    
    for turn_num, user_input in enumerate(conversation_turns, 1):
        print(f"Turn {turn_num}:")
        print(f"👤 User: {user_input}")
        
        # 1. Store user message
        user_message = ConversationMessage(
            role="user",
            content=user_input,
            timestamp=datetime.now(),
            user_id=user_id
        )
        await memory_manager.store_conversation(user_message)
        
        # 2. Get memory context for AI
        memory_context = await memory_manager.get_user_context(user_id, user_input)
        context_for_ai = memory_context.format_for_ai()
        
        # 3. Generate AI response with context
        ai_response = await ai_provider.generate_response(user_input, context_for_ai)
        
        print(f"🤖 Miko: {ai_response}")
        
        # 4. Store AI response
        ai_message = ConversationMessage(
            role="assistant",
            content=ai_response,
            timestamp=datetime.now(),
            user_id=user_id,
            sentiment="friendly"  # Could be determined by sentiment analysis
        )
        await memory_manager.store_conversation(ai_message)
        
        # 5. Update personality state based on conversation
        if "name" in user_input.lower() and turn_num == 1:
            await memory_manager.update_personality_state(user_id, {
                "user_name": "Sarah",
                "relationship_stage": "introduction"
            })
        elif "anime" in user_input.lower() and "favorite" in user_input.lower():
            await memory_manager.update_personality_state(user_id, {
                "favorite_anime": ["Attack on Titan", "Your Name"],
                "interests": ["anime"]
            })
        
        print()
        
        # Show memory context being used (for demonstration)
        if context_for_ai:
            print(f"💭 Memory context used:")
            print(f"   {context_for_ai.replace(chr(10), chr(10) + '   ')}")
            print()
    
    # Show final memory state
    print("📊 Final Memory State:")
    final_context = await memory_manager.get_user_context(user_id)
    print(f"Total conversation messages: {len(final_context.conversation_history)}")
    print(f"Personality state: {final_context.personality_state}")
    
    # Show conversation history
    print("\n📜 Conversation History:")
    for i, msg in enumerate(final_context.conversation_history, 1):
        role_emoji = "👤" if msg.role == "user" else "🤖"
        print(f"{i}. {role_emoji} {msg.role.title()}: {msg.content}")
    
    print("\n✅ Conversation simulation completed!")


async def demonstrate_memory_benefits():
    """Show the benefits of memory in conversations."""
    
    print("\n" + "=" * 50)
    print("🧠 Memory Benefits Demonstration")
    print("=" * 50)
    
    print("\nWithout Memory:")
    print("User: Do you remember my favorite anime?")
    print("AI: I don't have any previous context about your preferences.")
    
    print("\nWith Memory:")
    print("User: Do you remember my favorite anime?") 
    print("AI: Of course! You love Attack on Titan and Your Name!")
    
    print("\nMemory enables:")
    print("✓ Personalized responses")
    print("✓ Conversation continuity")
    print("✓ Relationship building")
    print("✓ Context-aware interactions")
    print("✓ User preference tracking")


if __name__ == "__main__":
    asyncio.run(simulate_conversation())
    asyncio.run(demonstrate_memory_benefits())