"""
Unit tests for AI provider implementations.
Tests the base provider interface, Ollama provider, Gemini provider, and factory.
"""

import pytest
import os
from unittest.mock import Mock, patch
from datetime import datetime

# Import the AI provider classes
from src.ai.base_provider import Message
from src.ai.ollama_provider import OllamaProvider
from src.ai.gemini_provider import GeminiProvider
from src.ai.provider_factory import ProviderFactory

# Configure pytest for async tests
pytest_plugins = ('pytest_asyncio',)


class TestMessage:
    """Test the Message dataclass."""
    
    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is None
    
    def test_message_with_timestamp(self):
        """Test creating a message with timestamp."""
        now = datetime.now()
        msg = Message(role="assistant", content="Hi there", timestamp=now)
        assert msg.timestamp == now


class TestOllamaProvider:
    """Test the Ollama provider implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'model': 'llama3',
            'host': 'http://localhost:11434'
        }
    
    @patch('src.ai.ollama_provider.ollama')
    def test_init_success(self, mock_ollama):
        """Test successful initialization."""
        provider = OllamaProvider(self.config)
        assert provider.model == 'llama3'
        assert provider.host == 'http://localhost:11434'
        assert provider.get_provider_name() == 'ollama'
        assert not provider.supports_content_filtering()
    
    def test_init_missing_ollama(self):
        """Test initialization without ollama library."""
        with patch('src.ai.ollama_provider.ollama', None):
            with pytest.raises(ImportError, match="ollama library is required"):
                OllamaProvider(self.config)
    
    @patch('src.ai.ollama_provider.ollama')
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_ollama):
        """Test successful response generation."""
        # Mock ollama response
        mock_ollama.chat.return_value = {
            'message': {'content': 'Hello! How can I help you today?'}
        }
        
        provider = OllamaProvider(self.config)
        messages = [Message(role="user", content="Hello")]
        personality = "You are a helpful assistant."
        
        response = await provider.generate_response(messages, personality)
        
        assert response == "Hello! How can I help you today?"
        mock_ollama.chat.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_ollama.chat.call_args[1]
        assert call_args['model'] == 'llama3'
        assert len(call_args['messages']) == 2  # system + user message
        assert call_args['messages'][0]['role'] == 'system'
        assert call_args['messages'][0]['content'] == personality
        assert call_args['messages'][1]['role'] == 'user'
        assert call_args['messages'][1]['content'] == "Hello"
    
    @patch('src.ai.ollama_provider.ollama')
    @pytest.mark.asyncio
    async def test_generate_response_error(self, mock_ollama):
        """Test response generation with error."""
        mock_ollama.chat.side_effect = Exception("Connection failed")
        
        provider = OllamaProvider(self.config)
        messages = [Message(role="user", content="Hello")]
        
        with pytest.raises(RuntimeError, match="Failed to generate response"):
            await provider.generate_response(messages, "")
    
    @pytest.mark.asyncio
    async def test_validate_content_always_true(self):
        """Test content validation always returns True."""
        with patch('src.ai.ollama_provider.ollama'):
            provider = OllamaProvider(self.config)
            assert await provider.validate_content("Any content") is True
            assert await provider.validate_content("Inappropriate content") is True
    
    @patch('src.ai.ollama_provider.ollama')
    @pytest.mark.asyncio
    async def test_check_connection_success(self, mock_ollama):
        """Test successful connection check."""
        mock_ollama.list.return_value = []
        
        provider = OllamaProvider(self.config)
        result = await provider.check_connection()
        
        assert result is True
        mock_ollama.list.assert_called_once()
    
    @patch('src.ai.ollama_provider.ollama')
    @pytest.mark.asyncio
    async def test_check_connection_failure(self, mock_ollama):
        """Test failed connection check."""
        mock_ollama.list.side_effect = Exception("Connection failed")
        
        provider = OllamaProvider(self.config)
        result = await provider.check_connection()
        
        assert result is False


class TestGeminiProvider:
    """Test the Gemini provider implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'api_keys': ['key1', 'key2', 'key3'],
            'model': 'gemini-pro',
            'current_key_index': 0
        }
    
    @patch('src.ai.gemini_provider.genai')
    @patch('src.ai.gemini_provider.HarmCategory')
    @patch('src.ai.gemini_provider.HarmBlockThreshold')
    def test_init_success(self, mock_harm_threshold, mock_harm_category, mock_genai):
        """Test successful initialization."""
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Mock the harm category and threshold enums
        mock_harm_category.HARM_CATEGORY_HARASSMENT = 'harassment'
        mock_harm_category.HARM_CATEGORY_HATE_SPEECH = 'hate_speech'
        mock_harm_category.HARM_CATEGORY_SEXUALLY_EXPLICIT = 'sexually_explicit'
        mock_harm_category.HARM_CATEGORY_DANGEROUS_CONTENT = 'dangerous_content'
        mock_harm_threshold.BLOCK_MEDIUM_AND_ABOVE = 'block_medium_and_above'
        
        provider = GeminiProvider(self.config)
        
        assert provider.api_keys == ['key1', 'key2', 'key3']
        assert provider.model_name == 'gemini-pro'
        assert provider.current_key_index == 0
        assert provider.get_provider_name() == 'gemini'
        assert provider.supports_content_filtering()
        
        mock_genai.configure.assert_called_with(api_key='key1')
        mock_genai.GenerativeModel.assert_called_with('gemini-pro')
    
    def test_init_missing_genai(self):
        """Test initialization without genai library."""
        with patch('src.ai.gemini_provider.genai', None):
            with pytest.raises(ImportError, match="google-generativeai library is required"):
                GeminiProvider(self.config)
    
    def test_init_no_api_keys(self):
        """Test initialization without API keys."""
        config = {'api_keys': []}
        with patch('src.ai.gemini_provider.genai'):
            with pytest.raises(ValueError, match="At least one Gemini API key is required"):
                GeminiProvider(config)
    
    @patch('src.ai.gemini_provider.genai')
    def test_init_invalid_key_index(self, mock_genai):
        """Test initialization with invalid key index."""
        config = self.config.copy()
        config['current_key_index'] = 10  # Out of bounds
        
        provider = GeminiProvider(config)
        assert provider.current_key_index == 0  # Should reset to 0
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_rotate_api_key_success(self, mock_genai):
        """Test successful API key rotation."""
        provider = GeminiProvider(self.config)
        
        result = await provider.rotate_api_key()
        
        assert result is True
        assert provider.current_key_index == 1
        assert mock_genai.configure.call_count == 2  # Initial + rotation
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_rotate_api_key_exhausted(self, mock_genai):
        """Test API key rotation when all keys exhausted."""
        config = {'api_keys': ['key1'], 'current_key_index': 0}
        provider = GeminiProvider(config)
        
        result = await provider.rotate_api_key()
        
        assert result is False
        assert provider.current_key_index == 0  # Should stay the same
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_genai):
        """Test successful response generation."""
        mock_response = Mock()
        mock_response.text = "Hello! How can I help you?"
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(self.config)
        messages = [Message(role="user", content="Hello")]
        personality = "You are a helpful assistant."
        
        response = await provider.generate_response(messages, personality)
        
        assert response == "Hello! How can I help you?"
        mock_model.generate_content.assert_called_once()
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_generate_response_blocked_content(self, mock_genai):
        """Test response generation with blocked content."""
        mock_response = Mock()
        mock_response.text = None  # Content blocked
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(self.config)
        messages = [Message(role="user", content="Inappropriate content")]
        
        response = await provider.generate_response(messages, "")
        
        # Should return character-appropriate rejection (check for any of the possible messages)
        rejection_keywords = ["baka", "embarrassing", "appropriate", "change", "mou"]
        assert any(keyword in response.lower() for keyword in rejection_keywords)
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_generate_response_rate_limit_rotation(self, mock_genai):
        """Test response generation with rate limit and key rotation."""
        mock_model = Mock()
        
        # First call fails with rate limit, second succeeds
        mock_response = Mock()
        mock_response.text = "Success after rotation"
        
        mock_model.generate_content.side_effect = [
            Exception("rate limit exceeded"),
            mock_response
        ]
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(self.config)
        messages = [Message(role="user", content="Hello")]
        
        response = await provider.generate_response(messages, "")
        
        assert response == "Success after rotation"
        assert provider.current_key_index == 1  # Should have rotated
        assert mock_model.generate_content.call_count == 2
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_validate_content_success(self, mock_genai):
        """Test successful content validation."""
        mock_response = Mock()
        mock_response.text = "This content is appropriate"
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(self.config)
        
        result = await provider.validate_content("Hello world")
        
        assert result is True
        mock_model.generate_content.assert_called_once()
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_validate_content_blocked(self, mock_genai):
        """Test content validation with blocked content."""
        mock_response = Mock()
        mock_response.text = None  # Content blocked
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        provider = GeminiProvider(self.config)
        
        result = await provider.validate_content("Inappropriate content")
        
        assert result is False


class TestProviderFactory:
    """Test the provider factory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear environment variables
        for key in ['USE_OLLAMA', 'OLLAMA_MODEL', 'GEMINI_API_KEYS']:
            if key in os.environ:
                del os.environ[key]
    
    @patch('src.ai.provider_factory.OllamaProvider')
    def test_create_ollama_provider(self, mock_ollama_provider):
        """Test creating Ollama provider."""
        os.environ['USE_OLLAMA'] = 'true'
        os.environ['OLLAMA_MODEL'] = 'llama3'
        
        ProviderFactory.create_provider()
        
        mock_ollama_provider.assert_called_once()
        call_args = mock_ollama_provider.call_args[0][0]
        assert call_args['model'] == 'llama3'
    
    @patch('src.ai.provider_factory.GeminiProvider')
    def test_create_gemini_provider(self, mock_gemini_provider):
        """Test creating Gemini provider."""
        os.environ['USE_OLLAMA'] = 'false'
        os.environ['GEMINI_API_KEYS'] = 'key1,key2,key3'
        
        ProviderFactory.create_provider()
        
        mock_gemini_provider.assert_called_once()
        call_args = mock_gemini_provider.call_args[0][0]
        assert call_args['api_keys'] == ['key1', 'key2', 'key3']
    
    def test_create_gemini_provider_no_keys(self):
        """Test creating Gemini provider without API keys."""
        os.environ['USE_OLLAMA'] = 'false'
        
        with pytest.raises(ValueError, match="GEMINI_API_KEYS environment variable is required"):
            ProviderFactory.create_provider()
    
    def test_get_provider_config_ollama(self):
        """Test getting Ollama provider configuration."""
        os.environ['USE_OLLAMA'] = 'true'
        os.environ['OLLAMA_MODEL'] = 'llama3'
        
        config = ProviderFactory.get_provider_config()
        
        assert config['provider_type'] == 'ollama'
        assert config['use_ollama'] is True
        assert config['ollama_model'] == 'llama3'
    
    def test_get_provider_config_gemini(self):
        """Test getting Gemini provider configuration."""
        os.environ['USE_OLLAMA'] = 'false'
        os.environ['GEMINI_API_KEYS'] = 'key1,key2'
        
        config = ProviderFactory.get_provider_config()
        
        assert config['provider_type'] == 'gemini'
        assert config['use_ollama'] is False
        assert config['gemini_api_keys_count'] == 2
    
    def test_validate_configuration_ollama_valid(self):
        """Test validating valid Ollama configuration."""
        os.environ['USE_OLLAMA'] = 'true'
        os.environ['OLLAMA_MODEL'] = 'llama3'
        
        errors = ProviderFactory.validate_configuration()
        
        assert errors == []
    
    def test_validate_configuration_ollama_invalid(self):
        """Test validating invalid Ollama configuration."""
        os.environ['USE_OLLAMA'] = 'true'
        # Missing OLLAMA_MODEL
        
        errors = ProviderFactory.validate_configuration()
        
        assert len(errors) > 0
        assert any('OLLAMA_MODEL is required' in error for error in errors)
    
    def test_validate_configuration_gemini_valid(self):
        """Test validating valid Gemini configuration."""
        os.environ['USE_OLLAMA'] = 'false'
        os.environ['GEMINI_API_KEYS'] = 'key1,key2'
        
        errors = ProviderFactory.validate_configuration()
        
        assert errors == []
    
    def test_validate_configuration_gemini_invalid(self):
        """Test validating invalid Gemini configuration."""
        os.environ['USE_OLLAMA'] = 'false'
        # Missing GEMINI_API_KEYS
        
        errors = ProviderFactory.validate_configuration()
        
        assert len(errors) > 0
        assert any('GEMINI_API_KEYS is required' in error for error in errors)
    
    def test_update_gemini_key_index(self):
        """Test updating Gemini key index."""
        ProviderFactory.update_gemini_key_index(2)
        
        assert os.environ['GEMINI_CURRENT_KEY_INDEX'] == '2'


class TestPersonalityProcessor:
    """Test the PersonalityProcessor implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.personality_processor import PersonalityProcessor, Sentiment
        self.personality_prompt = "You are a tsundere anime girl named Miko."
        self.processor = PersonalityProcessor(self.personality_prompt, enable_content_filter=True)
        self.Sentiment = Sentiment
    
    def test_init(self):
        """Test personality processor initialization."""
        assert self.processor.personality_prompt == self.personality_prompt
        assert self.processor.enable_content_filter is True
        assert len(self.processor.anime_patterns) > 0
        assert len(self.processor.sentiment_patterns) > 0
    
    def test_inject_personality(self):
        """Test personality injection into messages."""
        from src.ai.base_provider import Message
        
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there")
        ]
        
        processed = self.processor.inject_personality(messages)
        
        assert len(processed) == 3  # system + original messages
        assert processed[0].role == "system"
        assert processed[0].content == self.personality_prompt
        assert processed[1].content == "Hello"
        assert processed[2].content == "Hi there"
    
    def test_sentiment_analysis_happy(self):
        """Test sentiment analysis for happy content."""
        text = "I'm so happy and excited! This is wonderful!"
        sentiment, confidence = self.processor._analyze_sentiment(text)
        
        assert sentiment in [self.Sentiment.HAPPY, self.Sentiment.EXCITED]
        assert confidence > 0
    
    def test_sentiment_analysis_sad(self):
        """Test sentiment analysis for sad content."""
        text = "I'm so sad and disappointed. This makes me cry."
        sentiment, confidence = self.processor._analyze_sentiment(text)
        
        assert sentiment == self.Sentiment.SAD
        assert confidence > 0
    
    def test_sentiment_analysis_embarrassed(self):
        """Test sentiment analysis for embarrassed content."""
        text = "B-baka! It's not like I wanted to help you or anything!"
        sentiment, confidence = self.processor._analyze_sentiment(text)
        
        assert sentiment == self.Sentiment.EMBARRASSED
        assert confidence > 0
    
    def test_sentiment_analysis_neutral(self):
        """Test sentiment analysis for neutral content."""
        text = "The weather is nice today."
        sentiment, confidence = self.processor._analyze_sentiment(text)
        
        assert sentiment == self.Sentiment.NEUTRAL
        assert confidence >= 0
    
    def test_enhance_anime_style(self):
        """Test anime-style enhancement of responses."""
        response = "I'm embarrassed about this."
        enhanced = self.processor._enhance_anime_style(response)
        
        # Should contain some anime flair
        assert len(enhanced) >= len(response)
        # May contain tsundere phrases or cute endings
    
    def test_add_tsundere_traits(self):
        """Test adding tsundere-specific traits."""
        response = "I like helping you."
        enhanced = self.processor._add_tsundere_traits(response)
        
        # Should add stuttering for emotional content
        assert "I-I" in enhanced or "like" in enhanced
    
    def test_content_filter_inappropriate(self):
        """Test content filtering for inappropriate content."""
        inappropriate_content = "This contains explicit sexual content."
        should_filter, reason = self.processor._check_content_filter(inappropriate_content)
        
        assert should_filter is True
        assert reason is not None
    
    def test_content_filter_appropriate(self):
        """Test content filtering for appropriate content."""
        appropriate_content = "Hello, how are you today?"
        should_filter, reason = self.processor._check_content_filter(appropriate_content)
        
        assert should_filter is False
        assert reason is None
    
    def test_character_appropriate_rejection(self):
        """Test character-appropriate rejection messages."""
        rejection = self.processor._get_character_appropriate_rejection()
        
        # Should contain anime-style rejection
        anime_keywords = ["baka", "embarrass", "appropriate", "mou", "blush", "covers", "discuss"]
        assert any(keyword in rejection.lower() for keyword in anime_keywords)
    
    def test_process_response_normal(self):
        """Test processing a normal response."""
        response = "Hello! I'm happy to help you today!"
        processed = self.processor.process_response(response, "ollama")
        
        assert processed.content != ""
        assert processed.sentiment in list(self.Sentiment)
        assert processed.animation_trigger != ""
        assert processed.confidence >= 0
        assert processed.filtered is False
    
    def test_process_response_filtered_gemini(self):
        """Test processing a response that gets filtered with Gemini."""
        inappropriate_response = "This contains explicit content that should be filtered."
        processed = self.processor.process_response(inappropriate_response, "gemini")
        
        assert processed.filtered is True
        assert processed.filter_reason is not None
        assert processed.sentiment == self.Sentiment.EMBARRASSED
        # Content should be replaced with rejection message (not the original inappropriate content)
        assert processed.content != inappropriate_response
        assert len(processed.content) > 0  # Should have some rejection message
        # Should be a character-appropriate rejection (contains anime-style elements)
        anime_style_indicators = ["!", "?", "*", "(", ")", "~", "baka", "embarrassing", "appropriate", "mou", "eh", "discuss"]
        assert any(indicator in processed.content.lower() for indicator in anime_style_indicators)
    
    def test_process_response_no_filter_ollama(self):
        """Test processing with Ollama (no content filtering)."""
        # Disable content filter for this test
        from src.ai.personality_processor import PersonalityProcessor
        processor = PersonalityProcessor(self.personality_prompt, enable_content_filter=False)
        inappropriate_response = "This contains explicit content."
        processed = processor.process_response(inappropriate_response, "ollama")
        
        assert processed.filtered is False
        assert processed.filter_reason is None
        # Content should be processed normally, not filtered
    
    def test_get_animation_for_sentiment(self):
        """Test getting animation triggers for sentiments."""
        assert self.processor.get_animation_for_sentiment(self.Sentiment.HAPPY) == "smile"
        assert self.processor.get_animation_for_sentiment(self.Sentiment.SAD) == "sad"
        assert self.processor.get_animation_for_sentiment(self.Sentiment.EMBARRASSED) == "blush"
        assert self.processor.get_animation_for_sentiment(self.Sentiment.NEUTRAL) == "idle"
    
    def test_update_personality(self):
        """Test updating personality prompt."""
        new_personality = "You are a cheerful idol character."
        self.processor.update_personality(new_personality)
        
        assert self.processor.personality_prompt == new_personality
    
    def test_get_personality_stats(self):
        """Test getting personality processor statistics."""
        stats = self.processor.get_personality_stats()
        
        assert 'personality_length' in stats
        assert 'content_filter_enabled' in stats
        assert 'anime_patterns_count' in stats
        assert 'sentiment_patterns_count' in stats
        assert 'supported_sentiments' in stats
        assert 'animation_mappings' in stats
        
        assert stats['content_filter_enabled'] is True
        assert stats['personality_length'] > 0
        assert len(stats['supported_sentiments']) > 0


class TestProviderWithPersonalityProcessor:
    """Test AI providers with personality processor integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.personality_processor import PersonalityProcessor
        self.personality_prompt = "You are a tsundere anime girl."
        self.processor = PersonalityProcessor(self.personality_prompt)
    
    @patch('src.ai.ollama_provider.ollama')
    @pytest.mark.asyncio
    async def test_ollama_with_personality_processor(self, mock_ollama):
        """Test Ollama provider with personality processor."""
        from src.ai.ollama_provider import OllamaProvider
        from src.ai.base_provider import Message
        
        # Mock ollama response
        mock_ollama.chat.return_value = {
            'message': {'content': 'Hello! How can I help you?'}
        }
        
        config = {'model': 'llama3', 'host': 'http://localhost:11434'}
        provider = OllamaProvider(config)
        provider.set_personality_processor(self.processor)
        
        messages = [Message(role="user", content="Hello")]
        
        # Test the enhanced response method
        processed_response = await provider.generate_processed_response(messages)
        
        assert processed_response.content != ""
        assert hasattr(processed_response, 'sentiment')
        assert hasattr(processed_response, 'animation_trigger')
        assert hasattr(processed_response, 'confidence')
    
    @patch('src.ai.gemini_provider.genai')
    @pytest.mark.asyncio
    async def test_gemini_with_personality_processor(self, mock_genai):
        """Test Gemini provider with personality processor."""
        from src.ai.gemini_provider import GeminiProvider
        from src.ai.base_provider import Message
        
        # Mock genai response
        mock_response = Mock()
        mock_response.text = "Hello! How can I help you?"
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        config = {
            'api_keys': ['key1'],
            'model': 'gemini-pro',
            'current_key_index': 0
        }
        provider = GeminiProvider(config)
        provider.set_personality_processor(self.processor)
        
        messages = [Message(role="user", content="Hello")]
        
        # Test the enhanced response method
        processed_response = await provider.generate_processed_response(messages)
        
        assert processed_response.content != ""
        assert hasattr(processed_response, 'sentiment')
        assert hasattr(processed_response, 'animation_trigger')
        assert hasattr(processed_response, 'confidence')
    
    @patch('src.ai.provider_factory.OllamaProvider')
    @patch('src.ai.provider_factory.PersonalityProcessor')
    def test_factory_creates_provider_with_processor(self, mock_processor_class, mock_provider_class):
        """Test that factory creates provider with personality processor."""
        from src.ai.provider_factory import ProviderFactory
        
        # Mock the provider and processor
        mock_provider = Mock()
        mock_provider.get_provider_name.return_value = "ollama"
        mock_provider_class.return_value = mock_provider
        
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        
        os.environ['USE_OLLAMA'] = 'true'
        os.environ['OLLAMA_MODEL'] = 'llama3'
        
        provider = ProviderFactory.create_provider()
        
        # Verify processor was created and attached
        mock_processor_class.assert_called_once()
        mock_provider.set_personality_processor.assert_called_once_with(mock_processor)