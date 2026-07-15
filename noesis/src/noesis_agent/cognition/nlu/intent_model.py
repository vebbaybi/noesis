from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline


@dataclass(frozen=True, slots=True)
class IntentPrediction:
    label: str
    confidence: float
    ranked: tuple[tuple[str, float], ...]


# These examples are deliberately phrased as user utterances, not keywords.  The
# character and word models generalise spelling, word order, and short paraphrases.
_EXAMPLES: dict[str, tuple[str, ...]] = {
    "discord_owner": (
        "who owns this server", "who is the current server owner", "who runs this guild",
        "which person owns this community", "tell me the owner of this group",
        "who is the current owner of the server or channel", "who administers this discord server",
        "can you identify the guild owner", "whose server is this", "who is in charge of this server",
        "which member is responsible for the guild", "who controls this community",
    ),
    "discord_creator": (
        "who created this server", "who made this discord", "who founded this guild",
        "identify the original server creator", "which user started this community",
        "who set up this server originally", "tell me the founder of this group",
        "do you know who created the guild", "who opened this discord server",
        "who established the server", "name the person who first built this community",
    ),
    "discord_member_count": (
        "how many members are in this server", "how many people are in this group",
        "what is the guild member count", "how large is this community", "how many users are here",
        "count everybody in this discord", "what is the size of this server",
        "number of people in the group", "tell me how many people belong here",
        "are there many members in this guild", "how many accounts joined this server",
        "what is the total server population", "how many users belong to the community",
    ),
    "discord_channel": (
        "what channel is this", "which channel are we in", "name the current channel",
        "where in the server are we talking", "is this the test channel", "tell me this channel name",
    ),
    "discord_thread": (
        "is this a thread", "which thread is this", "are we inside a discord thread",
        "name the current thread", "is this conversation threaded", "what thread are we in",
    ),
    "package_decision_query": (
        "are we using numpy and pandas for version one", "did we choose pandas for the first release",
        "which python libraries are we using", "what packages did we decide on",
        "is numpy part of version 1", "remind me whether matplotlib is in the first version",
        "what was our dependency decision", "will the script use numpy and pandas",
        "are pandas and numpy being used for v1", "which libraries did the team agree to use",
    ),
    "release_query": (
        "when is version one launching", "what is the release date", "when do we ship",
        "remind me of our launch date", "which day is the milestone", "when is v1 due",
    ),
    "project_fact": (
        "version one launches on july 20", "we decided to use numpy", "the release is next friday",
        "pandas is included in the first version", "our milestone is august 3", "deployment happens tomorrow",
    ),
    "moderation_report": (
        "someone is using abusive language", "people are cursing in this server", "report that hostile message",
        "a user is harassing everyone", "look at the insult above", "this person keeps spamming",
        "there is hate speech in the channel", "moderators should review that threat",
    ),
    "hostile": (
        "you are completely useless", "fuck you", "you are an idiot", "what a stupid bot",
        "shut up you moron", "you are a complete failure", "I hate you", "you cannot do anything right",
    ),
    "follow_up_repair": (
        "you missed my other question", "I asked two questions", "answer the second part",
        "that is not what I asked", "no I meant the owner", "you did not answer everything",
        "what about the other part", "well I also asked who created it",
        "you answered only half of my question", "you responded to just one part",
    ),
    "bug_report": (
        "the runner crashes", "this feature is broken", "I found a bug", "it is not working",
        "the command raises an error", "startup fails every time", "there is a regression",
        "launching the program throws an exception", "application startup produces a traceback",
    ),
    "feature_request": (
        "please add a dashboard", "could you support slack", "I want a new feature",
        "add voice transcription", "can you implement calendar integration", "support another platform",
    ),
    "summarize": (
        "summarize this discussion", "give me a recap", "what is the tldr", "condense the thread",
        "briefly recap what happened", "produce a short summary of these messages",
    ),
    "explain": (
        "explain how this works", "why does the runner do that", "what does this error mean",
        "help me understand the architecture", "describe this behavior", "explain that answer",
    ),
    "memory_write": (
        "remember that we chose pandas", "save this decision", "keep this in memory",
        "remember this for later", "store the release date", "note that Alice owns deployment",
        "retain our choice for the future", "keep the database selection for later conversations",
    ),
    "memory_forget": (
        "forget that decision", "remove this from memory", "do not remember this",
        "delete the saved fact", "forget what I said", "erase that memory",
    ),
    "help": (
        "what can you do", "show me your capabilities", "how can you help", "list available commands",
        "what features do you have", "help me use noesis",
    ),
    "greeting": (
        "hello", "hi noesis", "good morning", "hey there", "thanks noesis", "how are you",
    ),
    "general_question": (
        "what should we do next", "can you answer a question", "is the service online",
        "where can I find the documentation", "do you know the answer", "what happened today",
        "can this work offline", "which approach is better", "is that correct",
    ),
    "unclear": (
        "okay", "hmm", "that thing", "maybe", "do it", "interesting", "continue", "well",
        "perhaps sometime", "possibly later", "not sure yet",
    ),
}


def normalize_utterance(text: str) -> str:
    text = re.sub(r"<@!?\d+>|@noesis\b", " ", text, flags=re.IGNORECASE)
    return " ".join(text.casefold().split())


class LocalIntentModel:
    """Small, offline statistical NLU model trained from versioned domain examples."""

    def __init__(self) -> None:
        samples = [(utterance, label) for label, utterances in _EXAMPLES.items() for utterance in utterances]
        self.pipeline = Pipeline([
            ("features", FeatureUnion([
                ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
                ("characters", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)),
            ])),
            ("classifier", LogisticRegression(C=8.0, max_iter=2000, class_weight="balanced", random_state=17)),
        ])
        self.pipeline.fit([normalize_utterance(text) for text, _ in samples], [label for _, label in samples])

    def predict(self, text: str, *, top_k: int = 4) -> IntentPrediction:
        probabilities = self.pipeline.predict_proba([normalize_utterance(text)])[0]
        classes = self.pipeline.classes_
        ranked = sorted(zip(classes, probabilities), key=lambda item: item[1], reverse=True)
        label, confidence = ranked[0]
        # Abstain when the model has neither useful evidence nor separation from
        # the runner-up.  A short vague utterance must not become a fabricated fact.
        margin = float(confidence - ranked[1][1])
        normalized = normalize_utterance(text)
        if (confidence < 0.16 or margin < 0.025) and len(normalized.split()) <= 4:
            label = "unclear"
        return IntentPrediction(str(label), float(confidence),
                                tuple((str(name), float(score)) for name, score in ranked[:top_k]))


@lru_cache(maxsize=1)
def get_intent_model() -> LocalIntentModel:
    return LocalIntentModel()


__all__ = ["IntentPrediction", "LocalIntentModel", "get_intent_model", "normalize_utterance"]
