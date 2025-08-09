# --- Bibliothèque standard ---
import csv
from io import TextIOWrapper
from datetime import datetime
import json
from decimal import Decimal, InvalidOperation
import hashlib
from django.utils import timezone
from django.utils.timezone import now
from django.http import Http404

# --- Bibliothèques Django ---
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import (
    Sum, F, Q, DecimalField, Case, When, Value, ExpressionWrapper
)
from django.db.models.functions import TruncDate
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate, Coalesce

# --- Imports locaux ---
from .forms import (
    StrategyForm,
    StrategyScreenshotFormSet,
    TradeNoteForm,
    TradeForm,
    CustomUserCreationForm,
    CSVUploadForm,
    CoachSelectionForm,
)
from .models import (
    Trade,
    Comment,
    Strategy,
    Screenshot,
    Profile,
    CoachRequest,
)
from .utils import parse_custom_datetime, validate_image_file


# -----------------------------------
# Pages simples

def home(request):
    """Page d'accueil."""
    return render(request, "trades/home.html")


def non_authorise(request):
    """Page d'accès non autorisé (simple)."""
    return render(request, "trades/non_authorise.html", status=403)


# -----------------------------------
# TRADES

@login_required
def trade_list(request):
    """Liste paginée des trades de l'utilisateur (+ filtres date)."""
    trades_qs = (
        Trade.objects.filter(user=request.user)
        .select_related("strategy")
        .order_by("-entry_datetime")
    )
    strategies = Strategy.objects.filter(user=request.user)

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    try:
        if start_date:
            d = datetime.strptime(start_date, "%Y-%m-%d").date()
            trades_qs = trades_qs.filter(entry_datetime__date__gte=d)
        if end_date:
            d = datetime.strptime(end_date, "%Y-%m-%d").date()
            trades_qs = trades_qs.filter(entry_datetime__date__lte=d)
    except ValueError:
        messages.error(request, "Format de date invalide (YYYY-MM-DD).")

    paginator = Paginator(trades_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "trades/trade_list.html",
        {
            "trades": page_obj,
            "start_date": start_date,
            "end_date": end_date,
            "strategies": strategies,
        },
    )


@login_required
def trade_detail(request, pk):
    trade = get_object_or_404(
        Trade.objects.select_related("user", "user__profile", "strategy"), pk=pk
    )

    is_owner = trade.user_id == request.user.id
    is_su = request.user.is_superuser
    is_coach_user = getattr(request.user, "profile", None) and request.user.profile.is_coach

    if not (is_owner or is_su or is_coach_user):
        raise PermissionDenied("Not allowed")

    student_id = trade.user_id if (is_coach_user and not is_owner) else None
    can_edit_delete = is_owner or is_su

    return render(
        request,
        "trades/trade_detail.html",
        {"trade": trade, "student_id": student_id, "can_edit_delete": can_edit_delete},
    )


@login_required
def trade_new(request):
    """Création d'un trade (+ upload multi-screenshots)."""
    if request.method == "POST":
        form = TradeForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()

            files = request.FILES.getlist("screenshots")
            for f in files:
                err = validate_image_file(f)
                if err:
                    form.add_error(None, err)
                    return render(request, "trades/trade_edit.html", {"form": form})
                Screenshot.objects.create(image=f, trade=trade)

            return redirect("trade_detail", pk=trade.pk)
        return render(request, "trades/trade_edit.html", {"form": form})
    else:
        form = TradeForm(user=request.user)
    return render(request, "trades/trade_edit.html", {"form": form})


@login_required
def trade_edit(request, pk):
    """Édition d'un trade existant (owner/superuser)."""
    trade = get_object_or_404(Trade, pk=pk)
    if trade.user_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied("Not allowed")

    if request.method == "POST":
        form = TradeForm(request.POST, request.FILES, instance=trade, user=request.user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()

            files = request.FILES.getlist("screenshots")
            for f in files:
                err = validate_image_file(f)
                if err:
                    form.add_error(None, err)
                    return render(
                        request, "trades/trade_edit.html", {"form": form, "trade": trade}
                    )
                Screenshot.objects.create(image=f, trade=trade)

            return redirect("trade_detail", pk=trade.pk)
        return render(request, "trades/trade_edit.html", {"form": form, "trade": trade})
    else:
        form = TradeForm(instance=trade, user=request.user)
    return render(request, "trades/trade_edit.html", {"form": form, "trade": trade})


@login_required
def trade_delete(request, pk):
    """Suppression d'un trade (owner/superuser)."""
    trade = get_object_or_404(Trade, pk=pk)
    if trade.user_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied("Not allowed")
    trade.delete()
    return redirect("trade_list")


# -----------------------------------
# STRATÉGIES

@login_required
def strategy_list(request):
    strategies = Strategy.objects.filter(user=request.user).order_by("name")
    return render(request, "trades/strategy_list.html", {"strategies": strategies})


@login_required
def strategy_detail(request, pk):
    strategy = get_object_or_404(
        Strategy.objects.select_related("user", "user__profile"), pk=pk
    )
    strategy_owner = strategy.user

    is_owner = (strategy_owner.id == request.user.id)
    can_edit_delete = is_owner or request.user.is_superuser

    is_coach_user = getattr(request.user, "profile", None) and request.user.profile.is_coach
    is_legit_coach = is_coach_user and strategy_owner.profile.coach_id == request.user.id

    if not (can_edit_delete or is_legit_coach):
        return redirect("non_authorise")

    screenshots = strategy.screenshots.all()
    student_id = strategy_owner.id if (is_legit_coach and strategy_owner != request.user) else None

    return render(
        request,
        "trades/strategy_detail.html",
        {
            "strategy": strategy,
            "screenshots": screenshots,
            "can_edit_delete": can_edit_delete,
            "student_id": student_id,
        },
    )


@login_required
def strategy_new(request):
    if request.method == "POST":
        form = StrategyForm(request.POST)
        formset = StrategyScreenshotFormSet(request.POST, request.FILES, instance=None)
        if form.is_valid() and formset.is_valid():
            strategy = form.save(commit=False)
            strategy.user = request.user
            strategy.save()
            formset.instance = strategy
            formset.save()
            messages.success(request, "Stratégie créée avec succès.")
            return redirect("strategy_detail", pk=strategy.pk)
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = StrategyForm()
        formset = StrategyScreenshotFormSet(instance=None)

    return render(
        request,
        "trades/strategy_edit.html",
        {"form": form, "formset": formset, "strategy": None},
    )


@login_required
def strategy_edit(request, pk):
    strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
    if request.method == "POST":
        form = StrategyForm(request.POST, instance=strategy)
        formset = StrategyScreenshotFormSet(request.POST, request.FILES, instance=strategy)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Stratégie mise à jour avec succès.")
            return redirect("strategy_detail", pk=strategy.pk)
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = StrategyForm(instance=strategy)
        formset = StrategyScreenshotFormSet(instance=strategy)

    return render(
        request,
        "trades/strategy_edit.html",
        {"form": form, "formset": formset, "strategy": strategy},
    )


@login_required
def strategy_delete(request, pk):
    strategy = get_object_or_404(Strategy, pk=pk)
    if strategy.user_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied("Not allowed")
    strategy.delete()
    return redirect("strategy_list")


# -----------------------------------
# AUTH

def user_login(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("trade_list")
        return render(
            request, "registration/login.html", {"error": "Nom d'utilisateur ou mot de passe incorrect."}
        )
    return render(request, "registration/login.html")


def user_logout(request):
    logout(request)
    return redirect("home")


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Votre compte a été créé avec succès.")
            login(request, user)
            return redirect("trade_list")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {"form": form})


# -----------------------------------
# Ajouts utilitaires (images/stratégie sur trade)

@login_required
def add_trade_screenshot(request, trade_id):
    """Ajoute des screenshots à un trade (owner)."""
    trade = get_object_or_404(Trade, pk=trade_id, user=request.user)
    if request.method == "POST":
        files = request.FILES.getlist("images")
        if not files:
            messages.error(request, "Veuillez sélectionner au moins une image.")
            return redirect("trade_list")

        for f in files:
            err = validate_image_file(f)
            if err:
                messages.error(request, err)
                return redirect("trade_list")
            Screenshot.objects.create(image=f, trade=trade)

        messages.success(request, f"{len(files)} capture(s) ajoutée(s) avec succès.")
        return redirect("trade_list")
    return redirect("trade_list")


@login_required
def update_trade_strategy(request, trade_id):
    """Change la stratégie d’un trade (owner)."""
    trade = get_object_or_404(Trade, pk=trade_id, user=request.user)
    if request.method == "POST":
        strategy_id = request.POST.get("strategy")
        if strategy_id:
            try:
                strategy = Strategy.objects.get(pk=strategy_id, user=request.user)
                trade.strategy = strategy
                trade.save()
                messages.success(request, "Stratégie mise à jour avec succès.")
            except Strategy.DoesNotExist:
                messages.error(request, "Stratégie invalide.")
        else:
            messages.error(request, "Veuillez sélectionner une stratégie.")
    return redirect("trade_list")


# -----------------------------------
# Coach / Élève

def is_coach(user):
    return user.is_authenticated and getattr(user, "profile", None) and user.profile.is_coach


@login_required
def coach_students_list(request):
    if not is_coach(request.user):
        return redirect("non_authorise")
    students = User.objects.filter(profile__coach=request.user)
    return render(request, "trades/coach/students_list.html", {"students": students})


@login_required
def coach_student_trades(request, student_id):
    if not is_coach(request.user):
        return redirect("non_authorise")

    student = get_object_or_404(User.objects.select_related("profile"), pk=student_id)
    if student.profile.coach_id != request.user.id:
        return redirect("non_authorise")

    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    trades = (
        Trade.objects.filter(user=student)
        .select_related("strategy")
        .order_by("-entry_datetime")
    )

    try:
        if start_date_str:
            sd = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            trades = trades.filter(entry_datetime__date__gte=sd)
        if end_date_str:
            ed = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            trades = trades.filter(entry_datetime__date__lte=ed)
    except ValueError:
        messages.error(request, "Format de date invalide (YYYY-MM-DD).")

    if request.method == "POST":
        trade_id = request.POST.get("trade_id")
        content = (request.POST.get("content") or "").strip()
        if trade_id and content:
            trade = get_object_or_404(Trade, pk=trade_id, user=student)
            Comment.objects.create(trade=trade, coach=request.user, content=content)
            messages.success(request, "Commentaire ajouté avec succès.")
        return redirect("coach_student_trades", student_id=student.pk)

    return render(
        request,
        "trades/coach/student_trades.html",
        {"student": student, "trades": trades,
         "start_date": start_date_str, "end_date": end_date_str},
    )


@login_required
def choose_coach(request):
    if is_coach(request.user):
        messages.error(request, "Vous êtes coach, vous ne pouvez pas choisir de coach.")
        return redirect("home")

    profile = getattr(request.user, "profile", None)
    if profile and profile.coach:
        messages.info(request, f"Vous avez déjà un coach : {profile.coach.username}")
        return redirect("home")

    pending_req = CoachRequest.objects.filter(student=request.user, accepted__isnull=True).first()
    if pending_req:
        messages.info(request, f"Demande en attente auprès de {pending_req.coach.username}.")
        return redirect("home")

    if request.method == "POST":
        form = CoachSelectionForm(request.POST)
        if form.is_valid():
            selected_coach = form.cleaned_data["coach"]
            CoachRequest.objects.create(student=request.user, coach=selected_coach)
            messages.success(request, f"Demande envoyée à {selected_coach.username}.")
            return redirect("home")
    else:
        form = CoachSelectionForm()

    return render(request, "trades/choose_coach.html", {"form": form})


@login_required
def coach_pending_requests(request):
    if not is_coach(request.user):
        return redirect("non_authorise")
    requests_list = CoachRequest.objects.filter(coach=request.user, accepted__isnull=True)
    return render(request, "trades/coach_pending_requests.html", {"requests_list": requests_list})


@login_required
def coach_respond_request(request, req_id):
    if not is_coach(request.user):
        return redirect("non_authorise")

    coach_req = get_object_or_404(
        CoachRequest, pk=req_id, coach=request.user, accepted__isnull=True
    )

    if "accept" in request.POST:
        coach_req.accepted = True
        coach_req.save()
        student_profile = coach_req.student.profile
        student_profile.coach = request.user
        student_profile.save()
        messages.success(request, f"Vous avez accepté {coach_req.student.username}.")
    elif "refuse" in request.POST:
        coach_req.accepted = False
        coach_req.save()
        messages.info(request, f"Vous avez refusé {coach_req.student.username}.")

    return redirect("coach_pending_requests")


@require_POST
@login_required
@user_passes_test(is_coach)
def add_trade_comment(request):
    """Ajoute un commentaire d'un coach via AJAX."""
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return JsonResponse({"status": "error", "message": "Requête non AJAX."})

    trade_id = request.POST.get("trade_id")
    content = (request.POST.get("content") or "").strip()

    if not trade_id or not content:
        return JsonResponse({"status": "error", "message": "Tous les champs sont obligatoires."})

    trade = get_object_or_404(Trade.objects.select_related("user__profile"), pk=trade_id)

    if trade.user.profile.coach_id != request.user.id and not request.user.is_superuser:
        return JsonResponse(
            {"status": "error", "message": "Vous n'êtes pas le coach de cet élève."}, status=403
        )

    Comment.objects.create(trade=trade, coach=request.user, content=content)
    return JsonResponse({"status": "success", "message": "Commentaire ajouté avec succès."})


# -----------------------------------
# Notes sur un trade

@login_required
def update_trade_note(request, pk):
    """Ajoute une note à un trade (owner/superuser), supporte AJAX et non-AJAX."""
    trade = get_object_or_404(Trade.objects.select_related("user"), pk=pk)
    if not (trade.user_id == request.user.id or request.user.is_superuser):
        raise PermissionDenied("Not allowed")

    if request.method == "POST":
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

        if trade.note:
            if is_ajax:
                return JsonResponse({"status": "error", "message": "Une note existe déjà pour ce trade."})
            messages.error(request, f"Une note existe déjà pour le trade #{trade.id}.")
            return redirect("trade_list")

        form = TradeNoteForm(request.POST, instance=trade)
        if form.is_valid():
            form.save()
            if is_ajax:
                return JsonResponse({"status": "success", "message": "Note ajoutée avec succès."})
            messages.success(request, f"La note du trade #{trade.id} a été ajoutée avec succès.")
        else:
            if is_ajax:
                return JsonResponse({"status": "error", "message": "Erreur lors de l'ajout de la note."})
            messages.error(request, f"Erreur lors de l'ajout de la note du trade #{trade.id}.")

    return redirect("trade_list")


# -----------------------------------
# Import CSV

@login_required
def import_csv(request):
    """
    Importe un fichier CSV/TSV et crée des Trades en masse.
    - Détecte le délimiteur (tab, virgule, point-virgule)
    - Utilise Decimal (pas de float)
    - Recalcule le PnL côté serveur
    - bulk_create + transaction
    - Idempotence via import_hash (UniqueConstraint(user, import_hash))
    """
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES, user=request.user)
        if not form.is_valid():
            return render(request, "trades/import_csv.html", {"form": form})

        csv_file = form.cleaned_data["csv_file"]
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        selected_strategy = form.cleaned_data.get("strategy")
        selected_strategy_id = selected_strategy.id if selected_strategy else None

        if csv_file.size > 5 * 1024 * 1024:
            messages.error(request, "Fichier trop volumineux (>5MB).")
            return redirect("import_csv")

        wrapper = TextIOWrapper(csv_file.file, encoding="utf-8-sig", newline="")
        sample = wrapper.read(2048)
        wrapper.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
        except csv.Error:
            class _D: delimiter = "\t"
            dialect = _D()

        reader = csv.reader(wrapper, dialect)
        headers = next(reader, None)

        if not headers:
            messages.error(request, "Le fichier ne contient pas d'en-têtes valides.")
            return redirect("import_csv")

        headers = [h.strip() for h in headers]
        header_map = {h: i for i, h in enumerate(headers)}

        required = [
            "Symbol",
            "Trade Type",
            "Entry DateTime",
            "Exit DateTime",
            "Entry Price",
            "Exit Price",
            "Trade Quantity",
        ]
        for rh in required:
            if rh not in header_map:
                messages.error(request, f"En-tête '{rh}' manquante.")
                return redirect("import_csv")

        def g(row, key, default=""):
            idx = header_map.get(key)
            return row[idx].strip() if idx is not None and idx < len(row) else default

        BATCH = 1000
        inserted = 0
        errors = 0
        buffer_objs = []
        buffer_hashes = []

        def flush_batch():
            nonlocal inserted, buffer_objs, buffer_hashes
            if not buffer_objs:
                return
            existing = set(
                Trade.objects.filter(
                    user=request.user, import_hash__in=buffer_hashes
                ).values_list("import_hash", flat=True)
            )
            to_insert = [obj for obj in buffer_objs if obj.import_hash not in existing]
            if to_insert:
                Trade.objects.bulk_create(to_insert)
                inserted += len(to_insert)
            buffer_objs.clear()
            buffer_hashes.clear()

        with transaction.atomic():
            for row in reader:
                if not row or len(row) < len(headers):
                    continue

                symbol = g(row, "Symbol").upper()
                trade_type = (g(row, "Trade Type") or "").upper()
                entry_dt = parse_custom_datetime(g(row, "Entry DateTime"))
                exit_dt = parse_custom_datetime(g(row, "Exit DateTime"))

                if not symbol or trade_type not in ("LONG", "SHORT") or not entry_dt or not exit_dt:
                    errors += 1
                    continue

                if start_date and entry_dt.date() < start_date:
                    continue
                if end_date and entry_dt.date() > end_date:
                    continue

                try:
                    entry_price = Decimal(g(row, "Entry Price"))
                    exit_price = Decimal(g(row, "Exit Price"))
                    quantity = Decimal(g(row, "Trade Quantity"))
                    commission = Decimal(g(row, "Commission (C)", "0") or "0")
                except (InvalidOperation, ValueError):
                    errors += 1
                    continue

                direction = Decimal("1") if trade_type == "LONG" else Decimal("-1")
                pnl = (exit_price - entry_price) * quantity * direction - commission

                base = "|".join(
                    [
                        str(request.user.id),
                        str(selected_strategy_id or "none"),
                        symbol,
                        entry_dt.isoformat(),
                        exit_dt.isoformat(),
                        str(entry_price),
                        str(exit_price),
                        str(quantity),
                        trade_type,
                    ]
                )
                import_hash = hashlib.md5(base.encode("utf-8")).hexdigest()

                buffer_objs.append(
                    Trade(
                        user=request.user,
                        strategy=selected_strategy,
                        symbol=symbol,
                        trade_type=trade_type,
                        entry_datetime=entry_dt,
                        exit_datetime=exit_dt,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=quantity,
                        commission=commission,
                        profit_loss=pnl,
                        import_hash=import_hash,
                    )
                )
                buffer_hashes.append(import_hash)

                if len(buffer_objs) >= BATCH:
                    flush_batch()

            flush_batch()

        if errors and inserted:
            messages.warning(
                request, f"{inserted} trade(s) importé(s), {errors} ligne(s) ignorée(s) (format invalide)."
            )
        elif errors and not inserted:
            messages.error(request, f"Aucun trade importé. {errors} ligne(s) ignorée(s).")
        else:
            messages.success(request, f"{inserted} trade(s) importé(s) avec succès.")
        return redirect("trade_list")

    else:
        form = CSVUploadForm(user=request.user)

    return render(request, "trades/import_csv.html", {"form": form})


# -----------------------------------
# Statistiques

@login_required
def stats_view(request):
    """
    Statistiques par stratégie (via ORM & Decimal).
    Coach: peut aussi consulter les stats d'un élève via ?student_id=<id>.
    """
    # --- Quel utilisateur cible ? (par défaut: utilisateur courant)
    student_id = request.GET.get("student_id")
    target_user = request.user
    viewing_student = None

    if student_id:
        # Seul un coach peut voir un élève
        if not is_coach(request.user):
            raise PermissionDenied("Accès refusé.")
        try:
            student = User.objects.select_related("profile").get(pk=student_id)
        except User.DoesNotExist:
            raise Http404("Élève introuvable.")
        # Vérifier que c'est bien SON élève
        if getattr(student, "profile", None) and student.profile.coach_id == request.user.id:
            target_user = student
            viewing_student = student
        else:
            raise PermissionDenied("Vous n'êtes pas le coach de cet élève.")


    # --- Stratégies du user ciblé (toi OU l'élève)
    strategies = Strategy.objects.filter(user=target_user).order_by("name")

    strategy_id = request.GET.get("strategy_id")
    context = {
        "strategies": strategies,
        "selected_strategy": None,
        "total_profit": 0,
        "nb_trades": 0,
        "win_rate": 0,
        "average_profit": 0,
        "average_gain_percent": 0,
        "total_investment": 0,
        "roi": 0,
        "chart_data": None,
        "today": timezone.now().date().isoformat(),
        "viewing_student": viewing_student,   # <- utile au template (titre + champ caché)
    }

    # Si aucune stratégie n'est choisie, on affiche juste la page avec la liste
    if not strategy_id:
        return render(request, "trades/stats.html", context)

    # Sélection de la stratégie: elle doit appartenir à target_user
    strategy = get_object_or_404(Strategy, pk=strategy_id, user=target_user)
    context["selected_strategy"] = strategy

    # On prend les trades de cette stratégie (sortis)
    qs = Trade.objects.filter(strategy=strategy, exit_datetime__isnull=False)

    # Direction en Decimal + output_field explicite
    direction = Case(
        When(trade_type="LONG", then=Value(Decimal("1"))),
        When(trade_type="SHORT", then=Value(Decimal("-1"))),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=4, decimal_places=0),
    )

    # PnL (ExpressionWrapper pour typer la sortie)
    pnl_expr = ExpressionWrapper(
        (F("exit_price") - F("entry_price")) * F("quantity") * direction - F("commission"),
        output_field=DecimalField(max_digits=20, decimal_places=6),
    )

    total = qs.count()
    wins = qs.filter(
        (Q(trade_type="LONG") & Q(exit_price__gt=F("entry_price")))
        | (Q(trade_type="SHORT") & Q(exit_price__lt=F("entry_price")))
    ).count()

    agg = qs.aggregate(
        total_profit=Sum(pnl_expr),
        total_investment=Sum(
            ExpressionWrapper(
                F("entry_price") * F("quantity"),
                output_field=DecimalField(max_digits=20, decimal_places=6),
            )
        ),
    )

    total_profit = agg["total_profit"] or Decimal("0")
    total_investment = agg["total_investment"] or Decimal("0")

    context["nb_trades"] = total
    context["total_profit"] = float(total_profit)
    context["win_rate"] = (wins / total * 100) if total else 0
    context["average_profit"] = float(total_profit / total) if total else 0
    context["total_investment"] = float(total_investment)
    context["roi"] = float((total_profit / total_investment) * 100) if total_investment else 0

    # % gain moyen non pondéré
    pct_expr = ExpressionWrapper(
        (F("exit_price") - F("entry_price")) * Value(Decimal("100")) / F("entry_price"),
        output_field=DecimalField(max_digits=12, decimal_places=6),
    )
    pct_values = list(qs.annotate(pct=pct_expr).values_list("pct", flat=True))
    if pct_values:
        s = sum(Decimal(str(x)) for x in pct_values)
        context["average_gain_percent"] = float(s / len(pct_values))

    # Equity curve (PnL cumulé par jour de sortie)
    daily = (
        qs.annotate(day=TruncDate("exit_datetime"))
        .values("day")
        .annotate(pnl=Sum(pnl_expr))
        .order_by("day")
    )
    cum = Decimal("0")
    x, y = [], []
    for row in daily:
        cum += row["pnl"] or Decimal("0")
        x.append(row["day"].isoformat())
        y.append(float(cum))
    context["chart_data"] = json.dumps({"x": x, "y": y})

    return render(request, "trades/stats.html", context)