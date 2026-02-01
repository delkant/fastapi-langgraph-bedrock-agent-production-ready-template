"""LLM service for managing LLM calls with retries and fallback mechanisms."""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger

# Import all providers - we'll choose which to use at runtime
try:
    from langchain_aws import ChatBedrock
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False
    ClientError = Exception  # Fallback
    BotoCoreError = Exception

try:
    from langchain_openai import ChatOpenAI
    from openai import (
        APIError,
        APITimeoutError,
        OpenAIError,
        RateLimitError,
    )
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAIError = Exception  # Fallback
    RateLimitError = Exception
    APITimeoutError = Exception
    APIError = Exception


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    @staticmethod
    def _get_bedrock_credentials():
        """Get AWS credentials for Bedrock based on available configuration."""
        if not BEDROCK_AVAILABLE:
            raise ImportError("AWS Bedrock dependencies not available")

        # Set environment variables to avoid metadata service calls
        import os
        os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'
        os.environ['AWS_REGION'] = settings.AWS_REGION

        if settings.AWS_BEARER_TOKEN_BEDROCK:
            # Decode bearer token to access key components
            logger.info("Using AWS bearer token authentication for Bedrock")

            try:
                import base64
                # Decode the base64 bearer token
                decoded_bytes = base64.b64decode(settings.AWS_BEARER_TOKEN_BEDROCK + '==')  # Add padding
                decoded_text = decoded_bytes.decode('latin-1')

                if ':' in decoded_text:
                    # Split into access key ID and secret
                    access_key_id, secret_access_key = decoded_text.split(':', 1)

                    # Remove any prefix (like "BedrockAPIKey-") if present
                    if 'BedrockAPIKey-' in access_key_id:
                        access_key_id = access_key_id.replace('BedrockAPIKey-', '').strip()

                    logger.info(f"Decoded bearer token to access key ID: {access_key_id[:10]}...")

                    # Set AWS environment variables
                    os.environ['AWS_ACCESS_KEY_ID'] = access_key_id
                    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_access_key

                    return boto3.Session(
                        aws_access_key_id=access_key_id,
                        aws_secret_access_key=secret_access_key,
                        region_name=settings.AWS_REGION,
                    )
                else:
                    logger.error("Bearer token does not contain ':' separator")
                    return None

            except Exception as e:
                logger.error(f"Failed to decode bearer token: {e}")
                return None
        elif settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            # Use access keys
            os.environ['AWS_ACCESS_KEY_ID'] = settings.AWS_ACCESS_KEY_ID
            os.environ['AWS_SECRET_ACCESS_KEY'] = settings.AWS_SECRET_ACCESS_KEY
            os.environ['AWS_REGION'] = settings.AWS_REGION
            os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'

            return boto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
        else:
            # Use default credentials (from ~/.aws/credentials, IAM role, etc.)
            return boto3.Session(region_name=settings.AWS_REGION)

    @staticmethod
    def _create_bedrock_model(model_id: str) -> Dict[str, Any]:
        """Create a single Bedrock model configuration."""
        if not BEDROCK_AVAILABLE:
            raise ImportError(
                "AWS Bedrock provider selected but dependencies not available. "
                "Install with: pip install langchain-aws boto3"
            )

        # Get AWS session for authentication
        aws_session = LLMRegistry._get_bedrock_credentials()

        # Configure model kwargs based on model type
        if "claude-3-haiku" in model_id:
            top_p = 0.9
        elif "claude-3-opus" in model_id or "claude-3-5-sonnet" in model_id:
            top_p = 0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8
        else:
            top_p = 0.8  # Default for other models

        if aws_session:
            # Use session-based client
            return {
                "name": model_id,
                "llm": ChatBedrock(
                    model_id=model_id,
                    model_kwargs={
                        "max_tokens": settings.MAX_TOKENS,
                        "temperature": settings.DEFAULT_LLM_TEMPERATURE,
                        "top_p": top_p,
                    },
                    client=aws_session.client('bedrock-runtime'),
                ),
            }
        else:
            # Fallback to environment-based authentication
            return {
                "name": model_id,
                "llm": ChatBedrock(
                    model_id=model_id,
                    region_name=settings.AWS_REGION,
                    model_kwargs={
                        "max_tokens": settings.MAX_TOKENS,
                        "temperature": settings.DEFAULT_LLM_TEMPERATURE,
                        "top_p": top_p,
                    },
                ),
            }

    @staticmethod
    def _create_openai_model(model_name: str) -> Dict[str, Any]:
        """Create a single OpenAI model configuration."""
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI provider selected but dependencies not available. "
                "Install with: pip install langchain-openai openai"
            )

        # Configure model kwargs based on model type
        model_kwargs = {
            "model": model_name,
            "temperature": settings.DEFAULT_LLM_TEMPERATURE,
            "api_key": settings.OPENAI_API_KEY,
            "max_tokens": settings.MAX_TOKENS,
        }

        # Add model-specific parameters
        if "gpt-4o" in model_name and model_name != "gpt-4o-mini":
            model_kwargs.update({
                "top_p": 0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
                "presence_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
                "frequency_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
            })
        else:
            model_kwargs["top_p"] = 0.9 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8

        return {
            "name": model_name,
            "llm": ChatOpenAI(**model_kwargs),
        }

    @staticmethod
    def _get_llms() -> List[Dict[str, Any]]:
        """Get the appropriate LLMs based on the configured provider and available models."""
        available_models = getattr(settings, 'AVAILABLE_LLM_MODELS', [])

        if not available_models:
            logger.warning("No available models configured, using defaults")
            if settings.LLM_PROVIDER == "bedrock":
                available_models = ["anthropic.claude-3-sonnet-20240229-v1:0"]
            else:
                available_models = ["gpt-4o-mini"]

        models = []
        for model_id in available_models:
            try:
                if settings.LLM_PROVIDER == "bedrock":
                    models.append(LLMRegistry._create_bedrock_model(model_id))
                else:
                    models.append(LLMRegistry._create_openai_model(model_id))

                logger.info("llm_model_initialized", model=model_id, provider=settings.LLM_PROVIDER)
            except Exception as e:
                logger.error("failed_to_initialize_model", model=model_id, provider=settings.LLM_PROVIDER, error=str(e))

        if not models:
            raise RuntimeError(f"No LLM models could be initialized for provider '{settings.LLM_PROVIDER}'")

        return models

    # Class-level variable containing all available LLM models
    LLMS: List[Dict[str, Any]] = []

    @classmethod
    def initialize(cls):
        """Initialize the LLMs list based on current provider settings."""
        cls.LLMS = cls._get_llms()

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        Args:
            model_name: Name of the model to retrieve
            **kwargs: Optional arguments to override default model configuration

        Returns:
            BaseChatModel instance

        Raises:
            ValueError: If model_name is not found in LLMS
        """
        # Ensure LLMs are initialized
        if not cls.LLMS:
            cls.initialize()

        # Find the model in the registry
        model_entry = None
        for entry in cls.LLMS:
            if entry["name"] == model_name:
                model_entry = entry
                break

        if not model_entry:
            available_models = [entry["name"] for entry in cls.LLMS]
            raise ValueError(
                f"model '{model_name}' not found in registry. available models: {', '.join(available_models)}"
            )

        # If user provides kwargs, create a new instance with those args
        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))

            if settings.LLM_PROVIDER == "bedrock":
                aws_session = cls._get_bedrock_credentials()
                return ChatBedrock(
                    model_id=model_name,
                    client=aws_session.client('bedrock-runtime'),
                    **kwargs
                )
            else:
                return ChatOpenAI(model=model_name, api_key=settings.OPENAI_API_KEY, **kwargs)

        # Return the default instance
        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get all registered LLM names in order.

        Returns:
            List of LLM names
        """
        if not cls.LLMS:
            cls.initialize()
        return [entry["name"] for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Get model entry at specific index.

        Args:
            index: Index of the model in LLMS list

        Returns:
            Model entry dict
        """
        if not cls.LLMS:
            cls.initialize()
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]  # Wrap around to first model


class LLMService:
    """Service for managing LLM calls with retries and circular fallback.

    This service handles all LLM interactions with automatic retry logic,
    rate limit handling, and circular fallback through all available models.
    """

    def __init__(self):
        """Initialize the LLM service."""
        self._llm: Optional[BaseChatModel] = None
        self._current_model_index: int = 0

        # Initialize the LLM registry
        LLMRegistry.initialize()

        # Validate that default model is in available models
        available_models = getattr(settings, 'AVAILABLE_LLM_MODELS', [])
        if settings.DEFAULT_LLM_MODEL not in available_models:
            logger.warning(
                "default_model_not_in_available_models",
                default_model=settings.DEFAULT_LLM_MODEL,
                available_models=available_models,
                provider=settings.LLM_PROVIDER,
            )

        # Find index of default model in registry
        all_names = LLMRegistry.get_all_names()
        try:
            self._current_model_index = all_names.index(settings.DEFAULT_LLM_MODEL)
            self._llm = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)
            logger.info(
                "llm_service_initialized",
                provider=settings.LLM_PROVIDER,
                default_model=settings.DEFAULT_LLM_MODEL,
                model_index=self._current_model_index,
                total_models=len(all_names),
                available_models=available_models,
                environment=settings.ENVIRONMENT.value,
            )
        except (ValueError, Exception) as e:
            # Default model not found, use first model
            if LLMRegistry.LLMS:
                self._current_model_index = 0
                self._llm = LLMRegistry.LLMS[0]["llm"]
                logger.warning(
                    "default_model_not_found_using_first",
                    requested=settings.DEFAULT_LLM_MODEL,
                    using=all_names[0] if all_names else "none",
                    available_models=available_models,
                    error=str(e),
                )
            else:
                logger.error("no_llm_models_available", error=str(e))
                raise RuntimeError(f"No LLM models available for provider '{settings.LLM_PROVIDER}'")

    def _get_next_model_index(self) -> int:
        """Get the next model index in circular fashion.

        Returns:
            Next model index (wraps around to 0 if at end)
        """
        total_models = len(LLMRegistry.LLMS)
        next_index = (self._current_model_index + 1) % total_models
        return next_index

    def _switch_to_next_model(self) -> bool:
        """Switch to the next model in the registry (circular).

        Returns:
            True if successfully switched, False otherwise
        """
        try:
            next_index = self._get_next_model_index()
            next_model_entry = LLMRegistry.get_model_at_index(next_index)

            logger.warning(
                "switching_to_next_model",
                from_index=self._current_model_index,
                to_index=next_index,
                to_model=next_model_entry["name"],
            )

            self._current_model_index = next_index
            self._llm = next_model_entry["llm"]

            logger.info("model_switched", new_model=next_model_entry["name"], new_index=next_index)
            return True
        except Exception as e:
            logger.error("model_switch_failed", error=str(e))
            return False

    def _get_retry_exceptions(self):
        """Get the appropriate exception types for retry based on provider."""
        if settings.LLM_PROVIDER == "bedrock":
            return (ClientError, BotoCoreError)
        else:
            return (RateLimitError, APITimeoutError, APIError)

    @retry(
        stop=stop_after_attempt(settings.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),  # We'll handle specific logic inside
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _call_llm_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the LLM with automatic retry logic.

        Args:
            messages: List of messages to send to the LLM

        Returns:
            BaseMessage response from the LLM

        Raises:
            LLMError: If all retries fail
        """
        if not self._llm:
            raise RuntimeError("llm not initialized")

        try:
            response = await self._llm.ainvoke(messages)
            logger.debug("llm_call_successful", message_count=len(messages), provider=settings.LLM_PROVIDER)
            return response
        except Exception as e:
            # Check if it's a retryable error based on provider
            retry_errors = self._get_retry_exceptions()
            if isinstance(e, retry_errors):
                logger.warning(
                    "llm_call_failed_retrying",
                    error_type=type(e).__name__,
                    error=str(e),
                    provider=settings.LLM_PROVIDER,
                    exc_info=True,
                )
                raise
            else:
                logger.error(
                    "llm_call_failed",
                    error_type=type(e).__name__,
                    error=str(e),
                    provider=settings.LLM_PROVIDER,
                )
                raise

    async def call(
        self,
        messages: List[BaseMessage],
        model_name: Optional[str] = None,
        **model_kwargs,
    ) -> BaseMessage:
        """Call the LLM with the specified messages and circular fallback.

        Args:
            messages: List of messages to send to the LLM
            model_name: Optional specific model to use. If None, uses current model.
            **model_kwargs: Optional kwargs to override default model configuration

        Returns:
            BaseMessage response from the LLM

        Raises:
            RuntimeError: If all models fail after retries
        """
        # If user specifies a model, get it from registry
        if model_name:
            try:
                self._llm = LLMRegistry.get(model_name, **model_kwargs)
                # Update index to match the requested model
                all_names = LLMRegistry.get_all_names()
                try:
                    self._current_model_index = all_names.index(model_name)
                except ValueError:
                    pass  # Keep current index if model name not in list
                logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))
            except ValueError as e:
                logger.error("requested_model_not_found", model_name=model_name, error=str(e))
                raise

        # Track which models we've tried to prevent infinite loops
        total_models = len(LLMRegistry.LLMS)
        models_tried = 0
        starting_index = self._current_model_index
        last_error = None

        while models_tried < total_models:
            try:
                response = await self._call_llm_with_retry(messages)
                return response
            except Exception as e:
                last_error = e
                models_tried += 1

                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    provider=settings.LLM_PROVIDER,
                    error=str(e),
                )

                # If we've tried all models, give up
                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[starting_index]["name"],
                        provider=settings.LLM_PROVIDER,
                    )
                    break

                # Switch to next model in circular fashion
                if not self._switch_to_next_model():
                    logger.error("failed_to_switch_to_next_model")
                    break

                # Continue loop to try next model

        # All models failed
        raise RuntimeError(
            f"failed to get response from llm after trying {models_tried} models. last error: {str(last_error)}"
        )

    def get_llm(self) -> Optional[BaseChatModel]:
        """Get the current LLM instance.

        Returns:
            Current BaseChatModel instance or None if not initialized
        """
        return self._llm

    def bind_tools(self, tools: List) -> "LLMService":
        """Bind tools to the current LLM.

        Args:
            tools: List of tools to bind

        Returns:
            Self for method chaining
        """
        if self._llm:
            self._llm = self._llm.bind_tools(tools)
            logger.debug("tools_bound_to_llm", tool_count=len(tools))
        return self


# Create global LLM service instance
llm_service = LLMService()
