# sam/lanzador/__main__.py
"""Entry point for lanzador service"""
import asyncio

from sam.common.config_loader import ConfigLoader

ConfigLoader.initialize_service("lanzador")
from .run_lanzador import main_async

if __name__ == "__main__":
    asyncio.run(main_async())
