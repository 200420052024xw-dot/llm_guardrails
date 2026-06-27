import logging
import logging.config
from pathlib import Path

from core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"},
            "message_only": {"format": "%(message)s"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "console"},
            "pipeline_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "pipeline.log"),
                "maxBytes": settings.log_max_bytes,
                "backupCount": settings.log_backup_count,
                "encoding": "utf-8",
                "formatter": "message_only",
            },
        },
        "root": {"level": "WARNING", "handlers": ["console"]},
        "loggers": {
            "guardrails.pipeline": {
                "level": "INFO",
                "handlers": ["pipeline_file"],
                "propagate": False,
            },
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
    })
