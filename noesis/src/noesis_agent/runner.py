"""Compatibility executable delegating to the canonical runtime bootstrap."""

from noesis_agent.runtime.bootstrap import main, run


if __name__ == "__main__":
    run()
