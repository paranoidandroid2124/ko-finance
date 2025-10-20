"""Telegram notification helper."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_alert(message: str) -> bool:
    """Send a message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram BOT token or chat ID is missing.")
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(api_url, json=payload)
            response.raise_for_status()

        if response.json().get("ok"):
            logger.info("Telegram alert sent successfully.")
            return True

        logger.error("Telegram API responded with an error: %s", response.json())
        return False

    except httpx.HTTPStatusError as exc:
        logger.error("Telegram alert failed with HTTP error: %s", exc.response.text)
        return False
    except Exception as exc:
        logger.error("Telegram alert failed: %s", exc, exc_info=True)
        return False


__all__ = ["send_telegram_alert"]

