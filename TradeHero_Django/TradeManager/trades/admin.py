# trades/admin.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import (
    Trade,
    Strategy,
    Screenshot,
    Profile,
    Comment,
    CoachRequest,
)

# ---------- Inlines ----------

class ScreenshotInline(admin.TabularInline):
    model = Screenshot
    extra = 0
    fields = ("image",)
    classes = ("collapse",)


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("coach", "content", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("coach",)
    classes = ("collapse",)


# ---------- Trade ----------

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "symbol",
        "user",
        "strategy",
        "trade_type",
        "entry_datetime",
        "exit_datetime",
        "quantity",
        "entry_price",
        "exit_price",
        "pnl_colored",
        "commission",
        "nb_screens",
    )
    list_filter = (
        "trade_type",
        "strategy",
        "user",
        ("entry_datetime", admin.DateFieldListFilter),
        ("exit_datetime", admin.DateFieldListFilter),
    )
    search_fields = (
        "symbol",
        "user__username",
        "strategy__name",
        "note",
    )
    date_hierarchy = "entry_datetime"
    inlines = [ScreenshotInline, CommentInline]
    autocomplete_fields = ("user", "strategy")
    list_select_related = ("user", "strategy")
    ordering = ("-entry_datetime",)

    fieldsets = (
        (None, {
            "fields": ("user", "strategy", "symbol", "trade_type", "note")
        }),
        ("Timing", {
            "fields": ("entry_datetime", "exit_datetime", "duration")
        }),
        ("Prix & Quantité", {
            "fields": ("entry_price", "exit_price", "quantity", "commission", "profit_loss")
        }),
    )

    @admin.display(description="PnL", ordering="profit_loss")
    def pnl_colored(self, obj: Trade) -> str:
        val = obj.profit_loss
        if val is None:
            return "-"
        color = "green" if val > 0 else ("red" if val < 0 else "inherit")
        prefix = "+" if val > 0 else ""
        return format_html('<span style="color:{};font-weight:600;">{}{:.2f}</span>', color, prefix, val)

    @admin.display(description="#Screens", ordering="screens_count")
    def nb_screens(self, obj: Trade) -> int:
        return getattr(obj, "screens_count", obj.screenshots.count())

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Annoter le nombre de screenshots pour éviter les N+1
        return qs.annotate(screens_count=Count("screenshots"))


# ---------- Strategy ----------

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "nb_trades", "nb_screens")
    search_fields = ("name", "description", "user__username")
    list_filter = ("user",)
    inlines = [ScreenshotInline]
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    ordering = ("name",)

    @admin.display(description="#Trades", ordering="trades_count")
    def nb_trades(self, obj: Strategy) -> int:
        return getattr(obj, "trades_count", obj.trade_set.count())

    @admin.display(description="#Screens", ordering="screens_count")
    def nb_screens(self, obj: Strategy) -> int:
        return getattr(obj, "screens_count", obj.screenshots.count())

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            trades_count=Count("trade"),
            screens_count=Count("screenshots"),
        )


# ---------- Profile ----------

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_coach", "coach")
    list_filter = ("is_coach",)
    search_fields = ("user__username", "user__email", "coach__username")
    autocomplete_fields = ("user", "coach")
    list_select_related = ("user", "coach")


# ---------- Comment (optionnel : visible seul si besoin) ----------

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "trade", "coach", "short_content", "created_at")
    list_filter = (
        ("created_at", admin.DateFieldListFilter),
        "coach",
    )
    search_fields = ("content", "coach__username", "trade__symbol", "trade__user__username")
    autocomplete_fields = ("trade", "coach")
    date_hierarchy = "created_at"
    list_select_related = ("trade", "coach")

    @admin.display(description="Contenu")
    def short_content(self, obj: Comment) -> str:
        txt = obj.content or ""
        return (txt[:80] + "…") if len(txt) > 80 else txt


# ---------- Screenshot (optionnel) ----------

@admin.register(Screenshot)
class ScreenshotAdmin(admin.ModelAdmin):
    list_display = ("id", "thumbnail", "trade", "strategy")
    search_fields = ("trade__symbol", "strategy__name")
    autocomplete_fields = ("trade", "strategy")
    list_select_related = ("trade", "strategy")

    @admin.display(description="Aperçu")
    def thumbnail(self, obj: Screenshot) -> str:
        if not obj.image:
            return "-"
        return format_html('<img src="{}" style="height:40px;border-radius:4px;" />', obj.image.url)


# ---------- CoachRequest ----------

@admin.register(CoachRequest)
class CoachRequestAdmin(admin.ModelAdmin):
    list_display = ("student", "coach", "accepted", "created_at")
    list_filter = ("accepted", ("created_at", admin.DateFieldListFilter))
    search_fields = ("student__username", "coach__username")
    autocomplete_fields = ("student", "coach")
    date_hierarchy = "created_at"
    list_select_related = ("student", "coach")
    actions = ("accepter_demandes", "refuser_demandes")

    @admin.action(description="Accepter les demandes sélectionnées")
    def accepter_demandes(self, request, queryset):
        updated = 0
        for req in queryset.select_related("student", "coach"):
            if req.accepted is True:
                continue
            # Accepter la demande + lier le profil de l'élève
            req.accepted = True
            req.save(update_fields=["accepted"])
            profile = getattr(req.student, "profile", None)
            if profile:
                profile.coach = req.coach
                profile.save(update_fields=["coach"])
            updated += 1
        self.message_user(request, f"{updated} demande(s) acceptée(s).", level=messages.SUCCESS)

    @admin.action(description="Refuser les demandes sélectionnées")
    def refuser_demandes(self, request, queryset):
        updated = queryset.exclude(accepted=False).update(accepted=False)
        self.message_user(request, f"{updated} demande(s) refusée(s).", level=messages.WARNING)
