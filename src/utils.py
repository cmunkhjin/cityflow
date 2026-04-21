"""
src/utils.py
Бүх модульд хэрэглэгдэх туслах функцүүд.
"""

from __future__ import annotations
import math
import logging
import sys
from pathlib import Path


# ── Logging ───────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """
    Тогтмол форматтай logger буцаана.

    Args:
        name: ихэвчлэн __name__

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s  [%(levelname)s]  %(name)s — %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ── Цаг ───────────────────────────────────────────────────

def is_rush_hour(hour: int, rush_hours: list[list[int]]) -> bool:
    """
    Тухайн цаг оргил цагт орох эсэхийг шалгана.

    Args:
        hour:       0-23 цаг
        rush_hours: [[7,9],[17,19]] хэлбэрийн жагсаалт

    Returns:
        True бол оргил цаг
    """
    return any(s <= hour < e for s, e in rush_hours)


def get_speed(hour: int, cfg: dict) -> float:
    """
    Тухайн цагийн дундаж хурд (km/h) буцаана.

    Args:
        hour: 0-23
        cfg:  traffic config dict

    Returns:
        km/h float
    """
    rush = is_rush_hour(hour, cfg["traffic"]["rush_hours"])
    return cfg["traffic"]["speed_peak_kmh"] if rush else cfg["traffic"]["speed_normal_kmh"]


# ── Геометр ───────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float,
                lat2: float, lon2: float) -> float:
    """
    Хоёр GPS цэгийн шулуун зай (метрээр).

    Args:
        lat1, lon1: эхний цэг
        lat2, lon2: хоёр дахь цэг

    Returns:
        Метр
    """
    R, p = 6_371_000, math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def eta_minutes(distance_m: float, speed_kmh: float) -> float:
    """
    Зай болон хурдаас ETA (минут) тооцооллоно.

    Args:
        distance_m: метр
        speed_kmh:  km/h

    Returns:
        Минут (float, 1 аравтын бутархай)
    """
    return round((distance_m / 1000) / speed_kmh * 60, 1)


# ── IO ────────────────────────────────────────────────────

def ensure_dir(path: str | Path) -> Path:
    """
    Хавтас байхгүй бол үүсгэнэ.

    Args:
        path: хавтасны зам

    Returns:
        Path object
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p