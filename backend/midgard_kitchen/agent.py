"""Midgard Kitchen — LiveKit voice agent (Thor pipeline).

Step 2: the real STT-LLM-TTS pipeline with the Thor persona and the LiveKit
audio turn detector. The RAG retrieval tool + narrative tool call are added in
Step 3. API verified against live LiveKit docs (AgentServer + TurnHandlingOptions
+ built-in audio TurnDetector).

Run (from backend/):
    uv run python -m midgard_kitchen.agent console
"""

from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    RunContext,
    TurnHandlingOptions,
    function_tool,
    inference,
)
from livekit.plugins import cartesia, deepgram, openai, silero

from .prompts import THOR_INSTRUCTIONS
from .rag.retrieve import consult_codex
from .settings import Settings
from .tools.narrative import read_the_skies

load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("midgard-kitchen")

settings = Settings()


class MidgardKitchenAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=THOR_INSTRUCTIONS)

    @function_tool()
    async def consult_the_codex(self, context: RunContext, query: str) -> str:
        """Consult the ancient Codex of Midgardian Sustenance for a specific fact,
        recipe, ingredient, measure, or instruction about cookery, provisions, or
        household management. Use this whenever the mortal asks for something that
        would be written in the tome, rather than answering from memory.

        Args:
            query: What to look up, e.g. "how to roast a goose" or "what the
                chapter on soups says about making good stock".
        """
        try:
            return await asyncio.to_thread(consult_codex, query)
        except Exception:  # graceful degradation (design-plan §9·S4)
            logger.exception("Codex retrieval failed")
            return "The Codex resists my grasp at this moment — its pages will not turn."

    @function_tool()
    async def summon_the_skies(self, context: RunContext, location: str) -> str:
        """Read the current weather over a mortal city so Thor may counsel a feast
        fit for the day — hearty stews and roasts for cold and grey, lighter fare
        for warm and clear. Use when the mortal asks what to cook, names their
        city, or wonders what suits today's weather.

        Args:
            location: The city or place to read the skies over, e.g. "Chicago" or "London".
        """
        try:
            return await read_the_skies(location)
        except Exception:  # graceful degradation (design-plan §9·S4)
            logger.exception("Failed to read the skies")
            return "The skies are clouded to me at this moment; I cannot read them."


def _build_tts(s: Settings) -> cartesia.TTS:
    kwargs: dict = {"model": s.tts_model}
    if s.tts_voice:
        kwargs["voice"] = s.tts_voice
    if s.tts_speed != 1.0:
        kwargs["speed"] = s.tts_speed
    if s.tts_volume != 1.0:
        kwargs["volume"] = s.tts_volume
    if s.tts_emotion:
        kwargs["emotion"] = s.tts_emotion  # sonic-3 emotion control (beta)
    return cartesia.TTS(**kwargs)


def _build_turn_detector(s: Settings) -> inference.TurnDetector:
    # LiveKit audio turn detector. Blank version = auto: full "v1" on LiveKit
    # Cloud, automatic fallback to local "v1-mini" otherwise. Pin "v1-mini" to
    # force fully-local operation.
    if s.turn_detector_version:
        return inference.TurnDetector(version=s.turn_detector_version)
    return inference.TurnDetector()


def prewarm(proc: agents.JobProcess) -> None:
    # Load Silero VAD once per worker process to cut per-session startup latency.
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: agents.JobContext) -> None:
    session = AgentSession(
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
        stt=deepgram.STT(
            model=settings.stt_model,
            language=settings.stt_language,
            keyterm=settings.stt_keyterms,
        ),
        llm=openai.LLM(model=settings.llm_model),
        tts=_build_tts(settings),
        turn_handling=TurnHandlingOptions(
            turn_detection=_build_turn_detector(settings),
        ),
    )

    await session.start(room=ctx.room, agent=MidgardKitchenAgent())

    await session.generate_reply(
        instructions=(
            "Greet the mortal grandly and in character as Thor. In a sentence or "
            "two, invite them to fuel themselves as a warrior does — real, hearty "
            "food that builds strength — and offer your counsel."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
