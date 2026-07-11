from __future__ import annotations

from pathlib import Path
import wave

from noesis_agent.brain.adaptive_policy import AdaptiveStylePolicy
from noesis_agent.brain.nlp_engine import LocalNLPEngine
from noesis_agent.brain.service import BrainService
from noesis_agent.brain.voice_profiles import VoiceProfileManager
from noesis_agent.services.memory_service import MemoryService
from noesis_agent.store.json_store import JsonStore


class DummyOpenAI:
    def is_enabled(self) -> bool:
        return False


def _write_silent_wav(path: Path, seconds: int, sample_rate: int = 16000) -> None:
    frames = b"\x00\x00" * sample_rate * seconds
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def test_local_nlp_detects_finance_risk_and_humor() -> None:
    analysis = LocalNLPEngine().analyze(
        "Is BTC liquidity real here or is this just another guaranteed 10x meme? lol"
    )

    assert "market_analysis" in analysis.intents
    assert "risk_review" in analysis.intents
    assert analysis.finance_score > 0.2
    assert analysis.humor_score > 0.0
    assert analysis.risk_flags


def test_adaptive_policy_persists_feedback(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    nlp = LocalNLPEngine()
    analysis = nlp.analyze("Break down ETH market structure and risk.")
    policy = AdaptiveStylePolicy(store)
    decision = policy.select_style(analysis)

    before = policy.weights[decision.style]["finance_score"]
    policy.record_feedback(decision.style, reward=1.0, feature_snapshot=decision.feature_snapshot)

    reloaded = AdaptiveStylePolicy(store)
    after = reloaded.weights[decision.style]["finance_score"]
    assert after > before


def test_voice_profile_manager_tracks_training_readiness(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    manager = VoiceProfileManager(store, tmp_path)
    manager.create_profile(
        "wildf",
        display_name="Wildf",
        preferred_openai_voice="alloy",
        speaking_notes="dry humor, sharp cadence",
        pacing=0.95,
    )

    for index in range(3):
        wav_path = tmp_path / f"sample_{index}.wav"
        _write_silent_wav(wav_path, seconds=15)
        transcript = f"Sample transcript {index}" if index < 2 else ""
        manager.add_sample("wildf", wav_path, transcript=transcript)

    status = manager.evaluate_training_readiness("wildf")
    assert status["sample_count"] == 3
    assert status["ready_for_training"] is True
    assert status["training_status"] == "ready_for_training"


def test_brain_service_builds_context_with_local_recall(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    memory = MemoryService(tmp_path)
    memory.index_transcript(
        "session-1",
        "host: Treasury quality matters more than hype.\n"
        "guest: NFT liquidity is thin and conviction needs downside framing.",
    )
    brain = BrainService(
        store=store,
        openai_service=DummyOpenAI(),
        memory_service=memory,
        data_dir=tmp_path,
    )

    context = brain.build_context(
        instruction="Give a sharp crypto market take on NFT liquidity.",
        latest_context="The room wants a fast answer.",
        transcript_tail="guest: Treasury quality and NFT liquidity still matter.",
        session_id="session-1",
    )

    assert context.policy.style in {"balanced", "analytical", "educational", "humorous", "skeptical"}
    assert context.finance.active is True
    assert context.recall_hits
    assert "liquidity" in context.fallback_reply.lower()
