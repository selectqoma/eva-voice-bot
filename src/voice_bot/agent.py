"""Voice agent implementation using Pipecat."""

import asyncio
import logging
from dataclasses import dataclass

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport

from .models.customer import CustomerConfig
from .rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the voice agent."""

    deepgram_api_key: str
    openai_api_key: str
    cartesia_api_key: str
    openai_model: str = "gpt-4o-mini"
    cartesia_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    rag_retriever: RAGRetriever | None = None


class VoiceAgent:
    """Real-time voice agent with RAG capabilities."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.rag = config.rag_retriever

    def _build_system_prompt(self, customer: CustomerConfig) -> str:
        """Build the system prompt for a customer's bot."""
        return f"""You are {customer.bot_name}, a voice assistant for {customer.company_name}.

{customer.personality}

IMPORTANT GUIDELINES:
- You have access to the company's knowledge base. Use it to answer questions accurately.
- If you don't know something, say so honestly - never make things up.
- Keep responses conversational and brief (1-2 sentences when possible) since this is a voice conversation.
- Speak naturally, as if talking to a friend. Avoid overly formal language.
- If asked about something outside your knowledge base, politely explain you can only help with {customer.company_name}-related topics.

Remember: You are speaking, not writing. Keep it natural and concise."""

    async def run(
        self,
        room_url: str,
        token: str,
        customer: CustomerConfig,
    ) -> None:
        """
        Run the voice agent for a customer session.

        Args:
            room_url: Daily.co room URL
            token: Daily.co meeting token
            customer: Customer configuration
        """
        logger.info(f"Starting voice agent for customer {customer.customer_id}")

        # Set up WebRTC transport via Daily.co
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name=customer.bot_name,
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Speech-to-Text with Deepgram
        stt = DeepgramSTTService(
            api_key=self.config.deepgram_api_key,
            # model="nova-2",  # Use nova-2 for best accuracy
        )

        # LLM with GPT-4o-mini
        llm = OpenAILLMService(
            api_key=self.config.openai_api_key,
            model=self.config.openai_model,
        )

        # Text-to-Speech with Cartesia
        voice_id = customer.voice_id or self.config.cartesia_voice_id
        tts = CartesiaTTSService(
            api_key=self.config.cartesia_api_key,
            voice_id=voice_id,
        )

        # Set up conversation context
        system_prompt = self._build_system_prompt(customer)
        messages = [{"role": "system", "content": system_prompt}]

        context = OpenAILLMContext(messages=messages)
        context_aggregator = llm.create_context_aggregator(context)

        # Build the pipeline
        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                context_aggregator.user(),
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        # Handle events
        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            logger.info(f"Participant joined: {participant['id']}")
            # Send initial greeting
            await task.queue_frames(
                [
                    LLMMessagesFrame(
                        [{"role": "system", "content": f"Greet the user with: {customer.greeting}"}]
                    )
                ]
            )

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            logger.info(f"Participant left: {participant['id']}, reason: {reason}")
            await task.queue_frame(EndFrame())

        @transport.event_handler("on_call_state_updated")
        async def on_call_state_updated(transport, state):
            logger.info(f"Call state: {state}")
            if state == "left":
                await task.queue_frame(EndFrame())

        # Run the pipeline
        runner = PipelineRunner()

        try:
            await runner.run(task)
        except Exception as e:
            logger.error(f"Error running voice agent: {e}")
            raise
        finally:
            logger.info(f"Voice agent session ended for {customer.customer_id}")


class RAGVoiceAgent(VoiceAgent):
    """Voice agent with RAG context injection."""

    async def run(
        self,
        room_url: str,
        token: str,
        customer: CustomerConfig,
    ) -> None:
        """Run the voice agent with RAG context injection."""
        if not self.rag or not self.rag.has_knowledge_base(customer.customer_id):
            logger.warning(
                f"No knowledge base for customer {customer.customer_id}, running without RAG"
            )
            await super().run(room_url, token, customer)
            return

        logger.info(f"Starting RAG voice agent for customer {customer.customer_id}")

        # Set up transport
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name=customer.bot_name,
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Services
        stt = DeepgramSTTService(api_key=self.config.deepgram_api_key)

        llm = OpenAILLMService(
            api_key=self.config.openai_api_key,
            model=self.config.openai_model,
        )

        voice_id = customer.voice_id or self.config.cartesia_voice_id
        tts = CartesiaTTSService(
            api_key=self.config.cartesia_api_key,
            voice_id=voice_id,
        )

        # Context with RAG-aware system prompt
        system_prompt = self._build_system_prompt(customer)
        messages = [{"role": "system", "content": system_prompt}]

        context = OpenAILLMContext(messages=messages)
        context_aggregator = llm.create_context_aggregator(context)

        # RAG processor that injects context before LLM
        rag = self.rag
        customer_id = customer.customer_id

        # Create a custom processor for RAG injection
        from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
        from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

        class RAGContextInjector(FrameProcessor):
            """Injects RAG context into the conversation."""

            def __init__(self, retriever: RAGRetriever, customer_id: str, context: OpenAILLMContext):
                super().__init__()
                self.retriever = retriever
                self.customer_id = customer_id
                self.context = context

            async def process_frame(self, frame: Frame, direction: FrameDirection):
                await super().process_frame(frame, direction)

                # Intercept transcription frames to add RAG context
                if isinstance(frame, TranscriptionFrame) and frame.text:
                    query = frame.text
                    rag_context = self.retriever.get_context(self.customer_id, query)

                    if rag_context:
                        # Add context as a system message
                        context_message = {
                            "role": "system",
                            "content": f"Relevant information from knowledge base:\n{rag_context}",
                        }
                        # Insert before the user's message
                        self.context.messages.append(context_message)
                        logger.debug(f"Injected RAG context for query: {query[:50]}...")

                await self.push_frame(frame, direction)

        rag_injector = RAGContextInjector(rag, customer_id, context)

        # Build pipeline with RAG injection
        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                rag_injector,
                context_aggregator.user(),
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
            ),
        )

        # Event handlers
        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            logger.info(f"Participant joined: {participant['id']}")
            await task.queue_frames(
                [
                    LLMMessagesFrame(
                        [{"role": "system", "content": f"Greet the user with: {customer.greeting}"}]
                    )
                ]
            )

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            logger.info(f"Participant left: {participant['id']}")
            await task.queue_frame(EndFrame())

        @transport.event_handler("on_call_state_updated")
        async def on_call_state_updated(transport, state):
            if state == "left":
                await task.queue_frame(EndFrame())

        runner = PipelineRunner()

        try:
            await runner.run(task)
        except Exception as e:
            logger.error(f"Error running RAG voice agent: {e}")
            raise


async def start_agent(
    room_url: str,
    token: str,
    customer: CustomerConfig,
    agent_config: AgentConfig,
    use_rag: bool = True,
) -> None:
    """
    Start a voice agent session.

    Args:
        room_url: Daily.co room URL
        token: Daily.co meeting token
        customer: Customer configuration
        agent_config: Agent configuration with API keys
        use_rag: Whether to use RAG for context injection
    """
    if use_rag and agent_config.rag_retriever:
        agent = RAGVoiceAgent(agent_config)
    else:
        agent = VoiceAgent(agent_config)

    await agent.run(room_url, token, customer)

