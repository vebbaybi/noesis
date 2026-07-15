from __future__ import annotations

import logging
import inspect
from typing import Any

import tweepy
from tweepy import Response

from noesis_agent.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)


class XClient:
    def __init__(self) -> None:
        self.client: tweepy.Client | None = None
        self._authenticated_user_id: str | None = None
        self._authenticated_username: str | None = None

        required = [
            settings.x_api_key,
            settings.x_api_secret,
            settings.x_access_token,
            settings.x_access_token_secret,
        ]

        if all(required):
            try:
                self.client = tweepy.Client(
                    consumer_key=settings.x_api_key,
                    consumer_secret=settings.x_api_secret,
                    access_token=settings.x_access_token,
                    access_token_secret=settings.x_access_token_secret,
                    bearer_token=settings.x_bearer_token,
                    wait_on_rate_limit=True,
                    return_type=Response,
                )
                logger.info("X/Twitter client initialized successfully")
            except Exception as exc:  # pragma: no cover - defensive startup guard
                logger.error("Failed to initialize X client: %s", exc)
                self.client = None
        else:
            logger.warning("Incomplete X API credentials - X features disabled")

    def is_enabled(self) -> bool:
        return self.client is not None and settings.enable_x

    def get_authenticated_user(self, force_refresh: bool = False) -> dict[str, str] | None:
        if not self.client:
            return None

        if self._authenticated_user_id and not force_refresh:
            payload = {"id": self._authenticated_user_id}
            if self._authenticated_username:
                payload["username"] = self._authenticated_username
            return payload

        try:
            response = self.client.get_me(user_fields=["username", "name"])
        except tweepy.TweepyException as exc:
            logger.error("Failed to fetch authenticated X user: %s", exc)
            return None

        data = getattr(response, "data", None)
        if data is None:
            logger.warning("Authenticated X user lookup returned no data")
            return None

        self._authenticated_user_id = str(data.id)
        self._authenticated_username = getattr(data, "username", None)

        payload = {"id": self._authenticated_user_id}
        if self._authenticated_username:
            payload["username"] = self._authenticated_username
        return payload

    def post(
        self,
        text: str,
        reply_to_tweet_id: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        if dry_run or not self.is_enabled():
            preview = text[:80]
            suffix = "..." if len(text) > 80 else ""
            logger.info("[DRY RUN] Would post: %s%s", preview, suffix)
            return {
                "status": "dry_run",
                "text": text,
                "reply_to_tweet_id": reply_to_tweet_id,
            }

        try:
            assert self.client is not None
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to_tweet_id,
            )
            tweet_id = str(response.data["id"])
            logger.info("Posted tweet: %s | %s...", tweet_id, text[:60])
            return {"status": "success", "tweet_id": tweet_id, "data": response.data}
        except tweepy.TweepyException as exc:
            logger.error("Failed to post tweet: %s", exc)
            return {"status": "error", "error": str(exc)}

    def post_thread(
        self,
        posts: list[str],
        dry_run: bool = True,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        previous_id: str | None = None

        for index, text in enumerate(posts, 1):
            result = self.post(
                text=text,
                reply_to_tweet_id=previous_id,
                dry_run=dry_run,
            )
            results.append(result)

            status = result.get("status")
            if status == "success":
                previous_id = str(result["tweet_id"])
                continue
            if status == "dry_run":
                continue

            logger.warning("Thread stopped at part %s due to error", index)
            break

        return results

    def get_mentions(
        self,
        since_id: str | None = None,
        max_results: int = 10,
        expansions: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_enabled():
            logger.warning("X client not enabled - cannot fetch mentions")
            return []

        authenticated_user = self.get_authenticated_user()
        if not authenticated_user:
            logger.warning("Authenticated X user unavailable - cannot fetch mentions")
            return []

        try:
            assert self.client is not None
            params: dict[str, Any] = {
                "max_results": self._clamp_max_results(max_results),
                "tweet_fields": ["created_at", "text", "author_id", "conversation_id"],
                "user_fields": ["username", "name"],
                "expansions": expansions or ["author_id"],
            }
            if since_id:
                params["since_id"] = since_id

            response = self.client.get_users_mentions(
                id=authenticated_user["id"],
                **params,
            )

            tweets = list(getattr(response, "data", None) or [])
            if not tweets:
                return []

            users = self._included_users(response)
            mentions: list[dict[str, Any]] = []

            for tweet in sorted(tweets, key=self._tweet_sort_key):
                author = users.get(str(tweet.author_id))
                mentions.append(
                    {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "author_id": str(tweet.author_id),
                        "author_username": getattr(author, "username", None),
                        "author_name": getattr(author, "name", None),
                        "conversation_id": str(tweet.conversation_id),
                    }
                )

            logger.debug("Fetched %s new mentions", len(mentions))
            return mentions

        except tweepy.TweepyException as exc:
            logger.error("Error fetching mentions: %s", exc)
            return []

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        since_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []

        try:
            assert self.client is not None
            params: dict[str, Any] = {
                "max_results": self._clamp_max_results(max_results),
                "tweet_fields": ["created_at", "text", "author_id"],
                "expansions": ["author_id"],
                "user_fields": ["username"],
            }
            if since_id:
                params["since_id"] = since_id

            response = self.client.search_recent_tweets(query=query, **params)
            tweets = list(getattr(response, "data", None) or [])
            if not tweets:
                return []

            users = self._included_users(response)
            results: list[dict[str, Any]] = []

            for tweet in sorted(tweets, key=self._tweet_sort_key):
                author = users.get(str(tweet.author_id))
                results.append(
                    {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "author_id": str(tweet.author_id),
                        "author_username": getattr(author, "username", None),
                    }
                )

            return results

        except tweepy.TweepyException as exc:
            logger.error("Search failed: %s", exc)
            return []

    async def close(self) -> None:
        default_client = self.client
        if not default_client:
            return

        close = getattr(default_client, "aclose", None) or getattr(default_client, "close", None)
        if close is None:
            return

        result = close()
        if inspect.isawaitable(result):
            await result
        logger.info("X client connection closed")

    @staticmethod
    def _clamp_max_results(value: int) -> int:
        return max(5, min(int(value), 100))

    @staticmethod
    def _included_users(response: Response) -> dict[str, Any]:
        includes = getattr(response, "includes", None) or {}
        users = includes.get("users", [])
        return {str(user.id): user for user in users}

    @staticmethod
    def _tweet_sort_key(tweet: Any) -> int:
        try:
            return int(getattr(tweet, "id"))
        except (TypeError, ValueError):
            return 0
