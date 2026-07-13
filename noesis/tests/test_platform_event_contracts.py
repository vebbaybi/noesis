import pytest
from pydantic import ValidationError

from noesis_agent.models.platform_events import SpaceEventContract, XEventContract
from noesis_agent.platforms.mention_normalizers import normalize_x_mention


def test_x_contract_and_normalizer_distinguish_reply_quote_and_conversation() -> None:
    reply = normalize_x_mention({"id": "1", "text": "@Noesis context?", "conversation_id": "c",
                                 "in_reply_to_tweet_id": "0"})
    assert reply.metadata["event_type"] == "reply"
    contract = XEventContract(event_id="1", event_type="quote", conversation_id="c",
                              referenced_post_ids=["0"])
    assert contract.event_type == "quote"


def test_spaces_contract_covers_live_cognitive_events_and_rejects_unknown_types() -> None:
    assert SpaceEventContract(space_id="s", event_id="e", event_type="commitment",
                              participant_role="speaker", text="I will ship Friday").event_type == "commitment"
    with pytest.raises(ValidationError):
        SpaceEventContract(space_id="s", event_id="e", event_type="invented")
