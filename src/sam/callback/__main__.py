# sam/callback/__main__.py
"""Entry point for callback service"""
from sam.common.config_loader import ConfigLoader

ConfigLoader.initialize_service("callback")
from .run_callback import main

if __name__ == "__main__":
    main()
