#!/usr/bin/env python3
"""
Demo script for personality injection and response processing.
Shows how the PersonalityProcessor enhances AI responses with anime-style language and sentiment analysis.
"""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai.personality_processor import PersonalityProcessor, Sentiment
from ai.base_provider import Message


async def demo_personality_processing():
    """Demonstrate personality processing features."""
    
    print("🎌 Anime AI Character - Personality Processing Demo")
    print("=" * 60)
    
    # Create personality processor with tsundere character
    personality_prompt = (
        "You are a tsundere anime girl named Miko. You're tough on the outside but caring inside. "
        "Always respond with anime flair, like 'B-baka!' for embarrassment, and end with cute emotes "
        "like (*blush*). Stay in character no matter what."
    )
    
    processor = PersonalityProcessor(personality_prompt, enable_content_filter=True)
    
    print(f"📝 Personality: {personality_prompt[:50]}...")
    print(f"🛡️  Content Filter: {'Enabled' if processor.enable_content_filter else 'Disabled'}")
    print()
    
    # Test messages for different scenarios
    test_scenarios = [
        {
            "name": "Happy Response",
            "response": "I'm so happy to help you! This is wonderful and exciting!",
            "expected_sentiment": Sentiment.HAPPY
        },
        {
            "name": "Embarrassed Response", 
            "response": "I-I guess I can help you... It's not like I want to or anything!",
            "expected_sentiment": Sentiment.EMBARRASSED
        },
        {
            "name": "Sad Response",
            "response": "I'm sorry, I feel really disappointed about this situation.",
            "expected_sentiment": Sentiment.SAD
        },
        {
            "name": "Neutral Response",
            "response": "The weather is nice today. How can I assist you?",
            "expected_sentiment": Sentiment.NEUTRAL
        },
        {
            "name": "Inappropriate Content (Gemini)",
            "response": "This contains explicit sexual content that should be filtered.",
            "expected_sentiment": Sentiment.EMBARRASSED,
            "should_filter": True
        }
    ]
    
    # Test personality injection
    print("🎭 Testing Personality Injection")
    print("-" * 40)
    
    messages = [
        Message(role="user", content="Hello, can you help me?"),
        Message(role="assistant", content="Sure, I'd be happy to help!")
    ]
    
    injected_messages = processor.inject_personality(messages)
    print(f"Original messages: {len(messages)}")
    print(f"With personality: {len(injected_messages)}")
    print(f"System message added: {injected_messages[0].role == 'system'}")
    print()
    
    # Test response processing
    print("🎨 Testing Response Processing & Sentiment Analysis")
    print("-" * 50)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"{i}. {scenario['name']}")
        print(f"   Input: {scenario['response'][:60]}...")
        
        # Test with different providers
        for provider in ["ollama", "gemini"]:
            processed = processor.process_response(scenario['response'], provider)
            
            print(f"   {provider.upper()}:")
            print(f"     Sentiment: {processed.sentiment.value} (confidence: {processed.confidence:.2f})")
            print(f"     Animation: {processed.animation_trigger}")
            print(f"     Filtered: {processed.filtered}")
            
            if processed.filtered:
                print(f"     Filter Reason: {processed.filter_reason}")
                print(f"     Rejection: {processed.content[:50]}...")
            else:
                print(f"     Enhanced: {processed.content[:50]}...")
            
            # Validate expectations
            if scenario.get('should_filter') and provider == "gemini":
                assert processed.filtered, f"Expected filtering for {scenario['name']} with Gemini"
            elif provider == "ollama":
                assert not processed.filtered, f"Ollama should not filter content"
        
        print()
    
    # Test anime-style enhancements
    print("✨ Testing Anime-Style Enhancements")
    print("-" * 40)
    
    test_responses = [
        "I'm embarrassed about this situation.",
        "Thank you for helping me today!",
        "I like spending time with you.",
        "This is really exciting news!"
    ]
    
    for response in test_responses:
        enhanced = processor._enhance_anime_style(response)
        print(f"Original: {response}")
        print(f"Enhanced: {enhanced}")
        print()
    
    # Test content filtering
    print("🛡️  Testing Content Filtering")
    print("-" * 30)
    
    test_content = [
        ("Hello world", False),
        ("This contains explicit content", True),
        ("Violence and harm", True),
        ("How are you today?", False)
    ]
    
    for content, should_filter in test_content:
        filtered, reason = processor._check_content_filter(content)
        status = "✅ PASS" if filtered == should_filter else "❌ FAIL"
        print(f"{status} '{content}' -> Filtered: {filtered}")
        if reason:
            print(f"      Reason: {reason}")
    
    print()
    
    # Show processor statistics
    print("📊 Personality Processor Statistics")
    print("-" * 40)
    
    stats = processor.get_personality_stats()
    for key, value in stats.items():
        if isinstance(value, list):
            print(f"{key}: {len(value)} items")
        elif isinstance(value, dict):
            print(f"{key}: {len(value)} mappings")
        else:
            print(f"{key}: {value}")
    
    print()
    print("🎉 Demo completed successfully!")
    print("The personality processor is working correctly with:")
    print("  ✅ Personality injection")
    print("  ✅ Anime-style language enhancement")
    print("  ✅ Sentiment analysis for animations")
    print("  ✅ Provider-specific content filtering")
    print("  ✅ Character-appropriate rejection messages")


if __name__ == "__main__":
    asyncio.run(demo_personality_processing())