# trades/models.py
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone
from django.core.validators import MinValueValidator

User = settings.AUTH_USER_MODEL


# ----------------------------
# Strategy
# ----------------------------
class Strategy(models.Model):
    """
    Stratégie rattachée à un utilisateur (élève), avec nom et description.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="strategies",
    )
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="uniq_strategy_user_name",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "name"]),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ----------------------------
# Trade
# ----------------------------
class Trade(models.Model):
    """
    Représente un trade réalisé par un utilisateur.
    Peut être associé à une stratégie.
    """
    LONG = "LONG"
    SHORT = "SHORT"
    SIDE_CHOICES = [(LONG, "Long"), (SHORT, "Short")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trades")
    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
    )

    symbol = models.CharField(max_length=50, db_index=True)
    trade_type = models.CharField(max_length=5, choices=SIDE_CHOICES, db_index=True)

    entry_datetime = models.DateTimeField(null=True, blank=True, db_index=True)
    exit_datetime = models.DateTimeField(null=True, blank=True, db_index=True)

    # Decimal partout (pas de float)
    entry_price = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0"))
    exit_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Taille de position (> 0).",
    )
    commission = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0"))

    # PnL stocké (affichage rapide) — recalculé à l’import côté vue
    profit_loss = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    note = models.TextField(blank=True)
    duration = models.DurationField(null=True, blank=True)

    # Idempotence d’import (UniqueConstraint avec user)
    import_hash = models.CharField(max_length=64, db_index=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-entry_datetime", "-id"]
        indexes = [
            models.Index(fields=["user", "entry_datetime"]),
            models.Index(fields=["symbol", "entry_datetime"]),
            models.Index(fields=["strategy", "entry_datetime"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            # Unicité par utilisateur si import_hash présent
            models.UniqueConstraint(
                fields=["user", "import_hash"],
                name="uniq_user_importhash",
                condition=~Q(import_hash=""),
            ),
            # Quantité positive
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="chk_trade_qty_gt_0",
            ),
            models.CheckConstraint(
                check=Q(trade_type__in=["LONG", "SHORT"]),
                name="trade_type_valid",
            ),
            # Exit >= Entry quand les deux sont renseignés
            models.CheckConstraint(
                check=Q(exit_datetime__isnull=True) | Q(entry_datetime__isnull=True) | Q(exit_datetime__gte=F("entry_datetime")),
                name="chk_trade_exit_after_entry",
            ),
        ]

    def __str__(self) -> str:
        user_display = getattr(self.user, "username", self.user_id)
        if self.entry_datetime:
            return f"Trade {self.symbol} - {user_display} le {self.entry_datetime:%Y-%m-%d %H:%M:%S}"
        return f"Trade {self.symbol} - {user_display} (date inconnue)"

    @property
    def computed_pnl(self) -> Decimal:
        """
        PnL calculé dynamiquement (source de vérité mathématique).
        """
        if self.exit_price is None or self.entry_price is None or self.quantity is None:
            return Decimal("0")
        direction = Decimal("1") if self.trade_type == self.LONG else Decimal("-1")
        return (self.exit_price - self.entry_price) * self.quantity * direction - (self.commission or Decimal("0"))

    def save(self, *args, **kwargs):
        # Met à jour la durée si dates présentes
        if self.entry_datetime and self.exit_datetime:
            self.duration = self.exit_datetime - self.entry_datetime
        # Si on a un exit_price et que profit_loss est nul / None, on l’aligne
        if self.exit_price is not None and (self.profit_loss is None or self.profit_loss == 0):
            self.profit_loss = self.computed_pnl
        super().save(*args, **kwargs)


# ----------------------------
# Screenshot
# ----------------------------
class Screenshot(models.Model):
    """
    Capture d'écran liée à un Trade ou à une Strategy.
    """
    image = models.ImageField(upload_to="screenshots/")
    trade = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name="screenshots",
        null=True,
        blank=True,
    )
    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.CASCADE,
        related_name="screenshots",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["trade"]),
            models.Index(fields=["strategy"]),
        ]

    def __str__(self) -> str:
        if self.trade_id:
            return f"Screenshot #{self.pk} (Trade {self.trade.symbol})"
        if self.strategy_id:
            return f"Screenshot #{self.pk} (Strategy {self.strategy.name})"
        return f"Screenshot #{self.pk}"


# ----------------------------
# Profile
# ----------------------------
class Profile(models.Model):
    """
    Profil utilisateur pour distinguer coach et élève.
    Un élève peut être lié à un coach.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_coach = models.BooleanField(default=False)
    coach = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    class Meta:
        indexes = [
            models.Index(fields=["is_coach"]),
            models.Index(fields=["coach"]),
        ]

    def __str__(self) -> str:
        return getattr(self.user, "username", str(self.user_id))


# ----------------------------
# Comment
# ----------------------------
class Comment(models.Model):
    """
    Commentaire laissé par un coach sur un trade.
    """
    trade = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments_made",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["coach"]),
            models.Index(fields=["trade"]),
        ]

    def __str__(self) -> str:
        coach_disp = getattr(self.coach, "username", self.coach_id)
        return f"Comment #{self.pk} by {coach_disp} on Trade {self.trade_id}"


# ----------------------------
# CoachRequest
# ----------------------------
class CoachRequest(models.Model):
    """
    Demande d'un élève à un coach.
    """
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="coach_requests",
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pending_students",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # None = en attente, True = accepté, False = refusé
    accepted = models.BooleanField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "coach"],
                name="uniq_coach_request",
            ),
        ]
        indexes = [
            models.Index(fields=["coach", "accepted"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        student_disp = getattr(self.student, "username", self.student_id)
        coach_disp = getattr(self.coach, "username", self.coach_id)
        return f"CoachRequest from {student_disp} to {coach_disp}"
