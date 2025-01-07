# trades/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Dès qu'un User est créé ou mis à jour, on crée/MAJ automatiquement le Profile.
    """
    if created:
        # Nouveau user => on crée le profil
        Profile.objects.create(user=instance)
    else:
        # User existant => on s'assure de sauver son profil s'il existe
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            # Optionnel : on crée le profil si jamais il n’existe pas
            Profile.objects.create(user=instance)
