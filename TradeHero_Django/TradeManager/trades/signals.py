# trades/signals.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.db import IntegrityError, transaction

from .models import Profile

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="trades_profile_create_update")
def create_or_update_user_profile(sender, instance: User, created: bool, **kwargs):
    """
    À la création d'un User -> créer un Profile.
    À la mise à jour -> s'assurer qu'un Profile existe.
    """
    if created:
        # get_or_create à l'intérieur d'une transaction pour éviter les courses
        try:
            with transaction.atomic():
                Profile.objects.get_or_create(user=instance)
        except IntegrityError:
            # Profil déjà créé par un autre handler/process -> ignorer
            pass
        return

    # Sur update, on ne crée pas d'écriture inutile si le profil n'existe pas.
    if hasattr(instance, "profile"):
        # Sauvegarde légère (déclenche les signaux éventuels liés au profil)
        instance.profile.save(update_fields=None)
    else:
        try:
            with transaction.atomic():
                Profile.objects.get_or_create(user=instance)
        except IntegrityError:
            pass


@receiver(post_migrate, dispatch_uid="trades_profile_backfill_after_migrate")
def ensure_profiles_exist(sender, **kwargs):
    """
    Après les migrations, créer les profils manquants (backfill idempotent).
    Utile si des Users existaient avant l'ajout du modèle Profile ou des signaux.
    """
    # Évite d'exécuter ce backfill lors des migrations d'autres apps
    app_config = kwargs.get("app_config")
    if not app_config or app_config.name != "trades":
        return

    # Crée les profils manquants en une seule passe
    users_without_profile = User.objects.filter(profile__isnull=True).only("id")
    to_create = [Profile(user=u) for u in users_without_profile]
    if to_create:
        Profile.objects.bulk_create(to_create, ignore_conflicts=True)
