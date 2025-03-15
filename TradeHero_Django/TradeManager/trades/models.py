# trades/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Strategy(models.Model):
    """
    Représente une stratégie rattachée à un utilisateur (par exemple, l'élève),
    avec un nom et une description.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='strategies'
    )
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class Trade(models.Model):
    """
    Représente un trade réalisé par un utilisateur.
    Peut être associé à une stratégie.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    strategy = models.ForeignKey(
        Strategy, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    symbol = models.CharField(max_length=50)
    trade_type = models.CharField(max_length=10)  # 'Long' ou 'Short'
    entry_datetime = models.DateTimeField(null=True, blank=True)
    exit_datetime = models.DateTimeField(null=True, blank=True)
    entry_price = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    exit_price = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    quantity = models.IntegerField(default=1)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    commission = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    note = models.TextField(blank=True)
    duration = models.DurationField(null=True, blank=True)

    def __str__(self):
        entry_time = self.entry_datetime.strftime('%Y-%m-%d %H:%M:%S') if self.entry_datetime else 'Date non spécifiée'
        return f"Trade {self.symbol} - {self.user.username} le {entry_time}"


class Screenshot(models.Model):
    """
    Capture d'écran liée à un Trade ou à une Strategy.
    """
    image = models.ImageField(upload_to='screenshots/')
    trade = models.ForeignKey(
        Trade, 
        on_delete=models.CASCADE, 
        related_name='screenshots',
        null=True, 
        blank=True
    )
    strategy = models.ForeignKey(
        Strategy, 
        on_delete=models.CASCADE, 
        related_name='screenshots',
        null=True, 
        blank=True
    )

    def __str__(self):
        if self.trade:
            return f"Screenshot #{self.pk} (Trade {self.trade.symbol})"
        elif self.strategy:
            return f"Screenshot #{self.pk} (Strategy {self.strategy.name})"
        return f"Screenshot #{self.pk}"


class Profile(models.Model):
    """
    Profil utilisateur pour distinguer coach et élève.
    Un élève peut être lié à un coach.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_coach = models.BooleanField(default=False)
    # Si un élève, le champ coach pointe vers l'utilisateur qui est son coach
    coach = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )

    def __str__(self):
        return self.user.username


class Comment(models.Model):
    """
    Commentaire laissé par un coach sur un trade.
    """
    trade = models.ForeignKey(
        Trade, 
        on_delete=models.CASCADE, 
        related_name='comments'
    )
    coach = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='comments_made'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment #{self.pk} by {self.coach.username} on Trade {self.trade.pk}"


class CoachRequest(models.Model):
    """
    Demande d'un élève à un coach.
    """
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coach_requests'
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pending_students'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(null=True, blank=True)  # None = en attente, True = accepté, False = refusé

    def __str__(self):
        return f"CoachRequest from {self.student.username} to {self.coach.username}"
