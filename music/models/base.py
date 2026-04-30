from django.db import models

class BaseModel(models.Model):
    """
    Abstrakcyjny model bazowy zapewniający samoaktualizujące się pola „created_at” i „updated_at”.
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Utworzono")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Zaktualizowano")

    class Meta:
        abstract = True # Nie tworzy tabeli w bazie danych
