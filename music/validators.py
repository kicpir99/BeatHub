from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from better_profanity import profanity
import os
from django.conf import settings

def load_bad_words():
    """Wczytuje polskie wulgaryzmy z pliku zewnętrznego."""
    polish_bad_words_path = os.path.join(settings.BASE_DIR, 'cenzura.txt')
    if os.path.exists(polish_bad_words_path):
        with open(polish_bad_words_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

# Inicjalizacja cenzury (raz przy starcie)
profanity.load_censor_words()
profanity.add_censor_words(load_bad_words())

def validate_no_profanity(value):
    """
    Walidator Django sprawdzający obecność wulgaryzmów w tekście.
    """
    if profanity.contains_profanity(value):
        raise ValidationError(
            _('Niestety, ten tekst zawiera niedozwolone słownictwo.'),
            code='profanity_detected'
        )
