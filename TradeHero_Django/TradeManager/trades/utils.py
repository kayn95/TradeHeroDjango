# trades/utils.py

from __future__ import annotations

import logging
from datetime import datetime, date, timezone as py_tz
from typing import Optional, Union

from django.utils import timezone

logger = logging.getLogger(__name__)

# Formats additionnels (en plus d'ISO 8601)
_KNOWN_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
)

def _to_aware(dt: datetime, tz=None) -> datetime:
    """
    Rends un datetime TZ-aware.
    - Si 'dt' a déjà un tzinfo => convertit vers 'tz' si fourni.
    - Sinon => l'attache à 'tz' (ou TZ courant Django).
    """
    target_tz = tz or timezone.get_current_timezone()
    if dt.tzinfo is not None:
        try:
            return dt.astimezone(target_tz)
        except Exception:
            # Si tzinfo non standard, force conversion via timestamp
            return datetime.fromtimestamp(dt.timestamp(), target_tz)
    # naive -> make_aware
    try:
        return timezone.make_aware(dt, target_tz)
    except Exception:
        # Fallback si make_aware échoue
        return dt.replace(tzinfo=target_tz)


def _clean_str(s: str) -> str:
    """
    Nettoie les marqueurs spécifiques et espaces.
    """
    s = (s or "").strip()
    if not s:
        return s
    # Retire marqueurs custom
    for tag in ("BP", "EP"):
        s = s.replace(tag, "")
    # Normalise espaces
    s = " ".join(s.split())
    # Remplace virgules décimales potentielles dans sous-secondes ex: ".123,456"
    # (on évite de toucher aux délimiteurs CSV, ici on parse déjà une valeur isolée)
    return s


def _try_parse_epoch(s: str) -> Optional[datetime]:
    """
    Tente de parser un timestamp (secondes ou millisecondes).
    """
    try:
        val = float(s)
    except Exception:
        return None
    # Heuristique: > 10^12 => ms, > 10^9 => s
    if val > 1e12:
        val /= 1000.0
    try:
        return datetime.fromtimestamp(val, py_tz.utc)
    except Exception:
        return None


def _try_parse_iso(s: str) -> Optional[datetime]:
    """
    Tente de parser ISO-8601 via fromisoformat avec quelques normalisations.
    """
    iso = s
    # Autoriser 'Z' pour UTC
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    # Autoriser 'T' séparateur
    # fromisoformat gère déjà le 'T'
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def parse_custom_datetime(
    value: Union[None, str, datetime, date, float, int],
    tz=None,
    log_warnings: bool = True,
) -> Optional[datetime]:
    """
    Parse un champ datetime “libre” provenant de CSV/inputs utilisateurs.

    Accepte :
      - None -> None
      - datetime (aware/naive) -> aware (TZ courant ou 'tz' fourni)
      - date -> début de journée (00:00) en TZ fourni/courant
      - str :
          * ISO-8601 (avec 'T', 'Z', offsets), ex: '2024-05-10T14:32:01Z'
          * 'YYYY-mm-dd HH:MM:SS[.ffffff]'
          * variants dans _KNOWN_DT_FORMATS
          * timestamps en secondes/millisecondes (ex: '1715344321' ou '1715344321123')
          * nettoie les marqueurs 'BP'/'EP'
      - float/int : timestamp en secondes (ou millisecondes si > 1e12)

    Retour :
      - datetime timezone-aware en TZ courant ou 'tz' fourni
      - None si échec de parsing
    """
    if value is None:
        return None

    # datetime
    if isinstance(value, datetime):
        return _to_aware(value, tz)

    # date -> 00:00
    if isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, 0, 0, 0)
        return _to_aware(dt, tz)

    # timestamp numérique
    if isinstance(value, (int, float)):
        dt = _try_parse_epoch(str(value))
        return _to_aware(dt, tz) if dt else None

    # chaîne
    if isinstance(value, str):
        s = _clean_str(value)
        if not s:
            return None

        # Timestamps (sec/ms)
        dt = _try_parse_epoch(s)
        if dt:
            return _to_aware(dt, tz)

        # ISO 8601
        dt = _try_parse_iso(s)
        if dt:
            return _to_aware(dt, tz)

        # Essais de formats connus
        for fmt in _KNOWN_DT_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                return _to_aware(dt, tz)
            except ValueError:
                continue

        if log_warnings:
            logger.warning("Impossible de parser la date '%s' avec les formats connus.", s)
        return None

    # Type non supporté
    if log_warnings:
        logger.warning("Type de valeur non supporté pour parse_custom_datetime: %r", type(value))
    return None

# -- Validation d'images pour upload -----------------------------------------
from typing import Optional

def validate_image_file(f) -> Optional[str]:
    """
    Retourne None si le fichier 'f' est une image valide, sinon un message d'erreur.
    - Vérifie content_type image/*
    - Limite la taille (5 Mo)
    - (optionnel) Vérifie via Pillow si disponible
    """
    # Taille max 5 Mo
    MAX_BYTES = 5 * 1024 * 1024

    # 1) Type MIME
    content_type = getattr(f, "content_type", "") or ""
    if not content_type.startswith("image/"):
        return "Tous les fichiers doivent être des images."

    # 2) Taille
    size = getattr(f, "size", None)
    if size is not None and size > MAX_BYTES:
        return "L'image dépasse la taille maximale de 5 Mo."

    # 3) Validation Pillow (silencieuse si Pillow absent)
    try:
        from PIL import Image
        f.seek(0)
        Image.open(f).verify()
        f.seek(0)  # important pour que Django puisse relire le flux
    except ImportError:
        # Pillow pas installé : on s'arrête aux vérifs de base
        pass
    except Exception:
        return "Le fichier image semble corrompu ou illisible."

    return None
