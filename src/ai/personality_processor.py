"""
Personality injection and response processing for Anime AI Character system.
Handles personality prompt loading, system message injection, response processing,
content filtering, and sentiment analysis for animation triggers.
"""

import re
import logging
import random
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
from .base_provider import Message

if TYPE_CHECKING:
    from .base_provider import MemoryContext

logger = logging.getLogger(__name__)


class Sentiment(Enum):
    """Sentiment types for animation triggers."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    EMBARRASSED = "embarrassed"
    ANGRY = "angry"
    CONFUSED = "confused"
    SPEAKING = "speaking"


@dataclass
class ProcessedResponse:
    """Processed AI response with metadata."""

    content: str
    sentiment: Sentiment
    animation_trigger: str
    confidence: float
    filtered: bool = False
    filter_reason: Optional[str] = None


class PersonalityProcessor:
    """Handles personality injection and response processing for anime AI character."""

    def __init__(self, personality_prompt: str, enable_content_filter: bool = True):
        """
        Initialize personality processor.

        Args:
            personality_prompt: Base personality prompt for the character
            enable_content_filter: Whether to enable content filtering
        """
        self.personality_prompt = personality_prompt
        self.enable_content_filter = enable_content_filter

        # Anime-style language patterns
        self.anime_patterns = {
            "tsundere_phrases": [
                "B-baka!",
                "It's not like I...",
                "Don't get the wrong idea!",
                "Hmph!",
                "W-whatever!",
                "I-it's not for you!",
            ],
            "cute_endings": [
                "(*blush*)",
                "(>.<)",
                "(^_^)",
                "(´∀｀)",
                "(￣▽￣)",
                "(*´ω｀*)",
                "(◕‿◕)",
                "(⌒‿⌒)",
            ],
            "exclamations": [
                "Kyaa!",
                "Ehh?!",
                "Mou~",
                "Ara ara~",
                "Sugoi!",
                "Kawaii!",
                "Yatta!",
                "Ganbatte!",
            ],
        }

        # Sentiment analysis patterns
        self.sentiment_patterns = {
            Sentiment.HAPPY: [
                r"\b(happy|joy|excited|wonderful|amazing|great|awesome|love|like)\b",
                r"[!]{2,}",
                r"(haha|hehe|yay|woohoo)",
                r"(^_^|\(^o^\))",
            ],
            Sentiment.SAD: [
                r"\b(sad|sorry|disappointed|upset|hurt|cry|tears)\b",
                r"(T_T|;_;|\(;´∩｀\))",
                r"\b(sob|sigh)\b",
            ],
            Sentiment.EXCITED: [
                r"\b(excited|amazing|incredible|fantastic|wow)\b",
                r"[!]{3,}",
                r"(kyaa|yatta|sugoi)",
                r"really\?+",
            ],
            Sentiment.EMBARRASSED: [
                r"\b(embarrass|blush|shy|nervous)\b",
                r"(b-baka|>.<|\(\*blush\*\))",
                r"it\'s not like",
                r"don\'t get the wrong idea",
            ],
            Sentiment.ANGRY: [
                r"\b(angry|mad|annoyed|irritated|hmph)\b",
                r"(>:|\(>_<\)|hmph)",
                r"baka{2,}",
            ],
            Sentiment.CONFUSED: [
                r"\b(confused|don\'t understand|what|huh|eh)\b",
                r"(\?\?\?|ehh\?|ara\?)",
                r"i don\'t get it",
            ],
        }

        # Animation mappings
        self.animation_mappings = {
            Sentiment.NEUTRAL: "idle",
            Sentiment.HAPPY: "smile",
            Sentiment.SAD: "sad",
            Sentiment.EXCITED: "excited",
            Sentiment.EMBARRASSED: "blush",
            Sentiment.ANGRY: "angry",
            Sentiment.CONFUSED: "confused",
            Sentiment.SPEAKING: "speak",
        }

        # Content filter patterns (inappropriate content indicators)
        self.inappropriate_patterns = [
            r"\b(explicit|nsfw|sexual|inappropriate)\b",
            r"\b(violence|harm|hurt|kill)\b",
            r"\b(hate|racist|discrimination)\b",
        ]

        logger.info("PersonalityProcessor initialized")

    def inject_personality(
        self, messages: List[Message], memory_context: Optional["MemoryContext"] = None
    ) -> List[Message]:
        """
        Inject personality prompt and memory context as system messages.

        Args:
            messages: Original conversation messages
            memory_context: Memory context from previous conversations (optional)

        Returns:
            Messages with personality system prompt and memory context injected
        """
        processed_messages = []

        # Add memory context as system message if available
        if memory_context:
            context_content = memory_context.format_for_ai()
            if context_content:
                memory_message = Message(
                    role="system",
                    content=f"Context from previous conversations:\n{context_content}",
                )
                processed_messages.append(memory_message)

        # Add personality as system message
        personality_message = Message(role="system", content=self.personality_prompt)
        processed_messages.append(personality_message)

        # Add original messages
        processed_messages.extend(messages)

        logger.debug(
            f"Injected personality prompt and memory context into {len(messages)} messages"
        )
        return processed_messages

    def process_response(self, response: str, provider_name: str) -> ProcessedResponse:
        """
        Process AI response with anime-style enhancements and sentiment analysis.

        Args:
            response: Raw AI response
            provider_name: Name of the AI provider used

        Returns:
            ProcessedResponse with enhanced content and metadata
        """
        # First check for content filtering if enabled
        if self.enable_content_filter and provider_name == "gemini":
            filter_result = self._check_content_filter(response)
            if filter_result[0]:  # Content was filtered
                return ProcessedResponse(
                    content=self._get_character_appropriate_rejection(),
                    sentiment=Sentiment.EMBARRASSED,
                    animation_trigger=self.animation_mappings[Sentiment.EMBARRASSED],
                    confidence=1.0,
                    filtered=True,
                    filter_reason=filter_result[1],
                )

        # Enhance response with anime-style language
        enhanced_response = self._enhance_anime_style(response)

        # Analyze sentiment
        sentiment, confidence = self._analyze_sentiment(enhanced_response)

        # Get animation trigger
        animation_trigger = self.animation_mappings.get(sentiment, "idle")

        return ProcessedResponse(
            content=enhanced_response,
            sentiment=sentiment,
            animation_trigger=animation_trigger,
            confidence=confidence,
            filtered=False,
        )

    def _enhance_anime_style(self, response: str) -> str:
        """
        Enhance response with anime-style language patterns.

        Args:
            response: Original response text

        Returns:
            Enhanced response with anime flair
        """
        enhanced = response

        # Add occasional anime expressions based on content
        if any(word in response.lower() for word in ["embarrass", "shy", "blush"]):
            if random.random() < 0.7:  # 70% chance
                enhanced += f" {random.choice(self.anime_patterns['tsundere_phrases'])}"

        # Add cute endings occasionally
        if random.random() < 0.4:  # 40% chance
            enhanced += f" {random.choice(self.anime_patterns['cute_endings'])}"

        # Replace some exclamations with anime equivalents
        if "!" in enhanced and random.random() < 0.3:  # 30% chance
            enhanced = enhanced.replace(
                "!", f'! {random.choice(self.anime_patterns["exclamations"])}', 1
            )

        # Ensure tsundere character traits if personality suggests it
        if "tsundere" in self.personality_prompt.lower():
            enhanced = self._add_tsundere_traits(enhanced)

        return enhanced

    def _add_tsundere_traits(self, response: str) -> str:
        """
        Add tsundere-specific language patterns.

        Args:
            response: Original response

        Returns:
            Response with tsundere traits
        """
        # Add stuttering for embarrassing topics
        if any(word in response.lower() for word in ["like", "love", "care", "help"]):
            response = re.sub(r"\b(I|i)\b", "I-I", response, count=1)

        # Add contradictory statements
        if "thank" in response.lower() and random.random() < 0.5:
            response += " It's not like I'm happy about it or anything!"

        return response

    def _analyze_sentiment(self, text: str) -> Tuple[Sentiment, float]:
        """
        Analyze sentiment of text for animation triggers.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (sentiment, confidence_score)
        """
        text_lower = text.lower()
        sentiment_scores = {}

        # Check each sentiment pattern
        for sentiment, patterns in self.sentiment_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches

            if score > 0:
                sentiment_scores[sentiment] = score

        # Determine dominant sentiment
        if not sentiment_scores:
            return Sentiment.NEUTRAL, 0.5

        # Get sentiment with highest score
        dominant_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        max_score = sentiment_scores[dominant_sentiment]

        # Calculate confidence (normalize score)
        total_words = len(text.split())
        confidence = min(max_score / max(total_words * 0.1, 1), 1.0)

        logger.debug(
            f"Sentiment analysis: {dominant_sentiment.value} (confidence: {confidence:.2f})"
        )
        return dominant_sentiment, confidence

    def _check_content_filter(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Check if content should be filtered.

        Args:
            content: Content to check

        Returns:
            Tuple of (should_filter, reason)
        """
        content_lower = content.lower()

        for pattern in self.inappropriate_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                reason = f"Matched inappropriate pattern: {pattern}"
                logger.warning(f"Content filtered: {reason}")
                return True, reason

        return False, None

    def _get_character_appropriate_rejection(self) -> str:
        """
        Get a character-appropriate rejection message for filtered content.

        Returns:
            Rejection message in character
        """
        rejections = [
            "B-baka! I can't talk about that kind of thing! (*blush*)",
            "Eh?! That's... that's too embarrassing to discuss! (>.<)",
            "I-I don't want to talk about that! Let's change the subject! (´∀｀)",
            "That's not appropriate! Ask me something else instead! Hmph!",
            "Mou~ I can't help with that kind of request! (￣▽￣)",
            "W-what are you thinking?! I won't discuss such things! (*covers face*)",
        ]

        return random.choice(rejections)

    def get_animation_for_sentiment(self, sentiment: Sentiment) -> str:
        """
        Get animation trigger name for a given sentiment.

        Args:
            sentiment: Sentiment enum value

        Returns:
            Animation trigger name
        """
        return self.animation_mappings.get(sentiment, "idle")

    def update_personality(self, new_personality: str) -> None:
        """
        Update the personality prompt.

        Args:
            new_personality: New personality prompt
        """
        self.personality_prompt = new_personality
        logger.info("Personality prompt updated")

    def get_personality_stats(self) -> Dict[str, Any]:
        """
        Get statistics about personality processing.

        Returns:
            Dictionary with personality processor stats
        """
        return {
            "personality_length": len(self.personality_prompt),
            "content_filter_enabled": self.enable_content_filter,
            "anime_patterns_count": sum(
                len(patterns) for patterns in self.anime_patterns.values()
            ),
            "sentiment_patterns_count": sum(
                len(patterns) for patterns in self.sentiment_patterns.values()
            ),
            "supported_sentiments": [s.value for s in Sentiment],
            "animation_mappings": {
                s.value: anim for s, anim in self.animation_mappings.items()
            },
        }


def create_personality_processor(
    personality_prompt: str, enable_content_filter: bool = True
) -> PersonalityProcessor:
    """
    Factory function to create a PersonalityProcessor instance.

    Args:
        personality_prompt: Personality prompt for the character
        enable_content_filter: Whether to enable content filtering

    Returns:
        Configured PersonalityProcessor instance
    """
    return PersonalityProcessor(personality_prompt, enable_content_filter)
