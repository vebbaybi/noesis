from __future__ import annotations

from pathlib import Path

from noesis_agent.shared.noesislogger import NoesisLogger


class SpotifyPodcastAdapter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = NoesisLogger("noesis.platforms.spotify").logger

    async def publish(self, title: str, description: str, audio_path: Path) -> Path:
        target = self.output_dir / audio_path.name
        target.write_bytes(Path(audio_path).read_bytes())
        self.logger.info("Simulated Spotify publish", extra={"target": str(target)})
        return target
