# trades/utils.py

import logging
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)

def parse_custom_datetime(datetime_str):
    """
    Parse une chaîne de caractères datetime personnalisée, en supprimant des marqueurs comme 'BP' ou 'EP'
    et en essayant différents formats.
    """
    if not datetime_str or datetime_str.strip() == '':
        return None

    datetime_str = datetime_str.replace('BP', '').replace('EP', '').strip()
    datetime_str = ' '.join(datetime_str.split())
    datetime_formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']

    for fmt in datetime_formats:
        try:
            naive_datetime = datetime.strptime(datetime_str, fmt)
            # Convertir en datetime aware selon le fuseau horaire actuel
            aware_datetime = timezone.make_aware(naive_datetime, timezone.get_current_timezone())
            return aware_datetime
        except ValueError:
            continue

    logger.warning(f"Impossible de parser la date '{datetime_str}' avec les formats connus.")
    return None
