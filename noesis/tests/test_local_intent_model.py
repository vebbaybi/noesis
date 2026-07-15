from __future__ import annotations

import pytest
from sklearn.metrics import accuracy_score, f1_score

from noesis_agent.cognition.nlu.intent_model import LocalIntentModel


# None of these utterances appears in the training corpus.  This is an explicit
# paraphrase/generalisation gate, rather than a test that merely repeats examples.
HELD_OUT = (
    ("discord_owner", "which member is presently responsible for this guild?"),
    ("discord_owner", "could you tell us who controls the server?"),
    ("discord_creator", "which person originally established this discord community?"),
    ("discord_creator", "can you name whoever first built the guild?"),
    ("discord_member_count", "what is the total population of this discord community?"),
    ("discord_member_count", "give me the number of users belonging to this group"),
    ("discord_channel", "where exactly are we chatting in this guild?"),
    ("discord_thread", "does this conversation live inside a thread?"),
    ("package_decision_query", "have numpy and pandas been selected as our v1 dependencies"),
    ("package_decision_query", "remind us which packages the first script will rely upon"),
    ("moderation_report", "please flag the member verbally attacking people above"),
    ("moderation_report", "somebody keeps posting hateful insults here"),
    ("hostile", "this bot is worthless and incompetent"),
    ("follow_up_repair", "you only responded to one half of what I said"),
    ("bug_report", "launching the application produces an exception"),
    ("feature_request", "would you implement speech recognition for us"),
    ("summarize", "give us the short version of the conversation"),
    ("explain", "walk me through why that behaviour occurs"),
    ("memory_write", "retain our database choice for future conversations"),
    ("memory_forget", "discard the fact you saved earlier"),
)


def test_offline_intent_model_generalises_to_held_out_paraphrases() -> None:
    model = LocalIntentModel()
    expected = [label for label, _ in HELD_OUT]
    predicted = [model.predict(text).label for _, text in HELD_OUT]
    assert accuracy_score(expected, predicted) >= 0.80, list(zip(expected, predicted))
    assert f1_score(expected, predicted, average="macro") >= 0.78


@pytest.mark.parametrize(("text", "intent"), (
    ("are we using numpy and pandas for version 1 of the script @Noesis", "package_decision_query"),
    ("who created this server @Noesis", "discord_creator"),
    ("okay who is the current owner of the server or channel @Noesis", "discord_owner"),
    ("how many people are in this group @Noesis", "discord_member_count"),
))
def test_screenshot_failures_have_stable_local_intents(text: str, intent: str) -> None:
    prediction = LocalIntentModel().predict(text)
    assert prediction.label == intent
    assert prediction.confidence > prediction.ranked[1][1] * 2
