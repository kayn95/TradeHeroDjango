# trades/views.py

# --- Bibliothèque standard ---
import csv
import io
from datetime import datetime, timedelta
import json

# --- Bibliothèques Django (tierces) ---
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Sum

# --- Importations locales ---
from .forms import (
    StrategyForm,
    StrategyScreenshotFormSet,
    TradeNoteForm,
    TradeForm,
    CustomUserCreationForm,
    CSVUploadForm,
    CoachSelectionForm
)
from .models import (
    Trade, 
    Comment, 
    Strategy, 
    Screenshot, 
    Profile, 
    CoachRequest
)

# -----------------------------------
# Vue pour la page d'accueil

def home(request):
    """
    Affiche la page d'accueil de l'application.
    """
    return render(request, 'trades/home.html')


# -----------------------------------
# Vues pour les Trades

@login_required
def trade_list(request):
    """
    Affiche la liste des trades de l'utilisateur connecté,
    avec possibilité de filtrer par date (start_date/end_date).
    """
    trades = Trade.objects.filter(user=request.user)
    strategies = Strategy.objects.filter(user=request.user)

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        trades = trades.filter(entry_datetime__gte=start_date)
    if end_date:
        trades = trades.filter(entry_datetime__lte=end_date)

    return render(request, 'trades/trade_list.html', {
        'trades': trades,
        'start_date': start_date,
        'end_date': end_date,
        'strategies': strategies,  # Pour la sélection de stratégies
    })


@login_required
def trade_detail(request, pk):
    trade = get_object_or_404(Trade, pk=pk)
    
    # Par défaut, on suppose qu’on ne peut pas modifier/supprimer
    can_edit_delete = False
    
    # Logique d’autorisation : propriétaire du trade ou superuser
    if trade.user == request.user or request.user.is_superuser:
        can_edit_delete = True
    
    # Logique d’accès : si c’est un coach sur le trade d’un élève,
    # on retient l’ID de l’élève
    student_id = None
    if (request.user.profile.is_coach 
        and trade.user != request.user):
        student_id = trade.user.pk

    # Si l'utilisateur n'est pas proprio, ni superuser, ni coach, on redirige
    if (trade.user != request.user 
        and not request.user.is_superuser
        and not request.user.profile.is_coach):
        return redirect('trade_list')

    return render(request, 'trades/trade_detail.html', {
        'trade': trade,
        'student_id': student_id,
        'can_edit_delete': can_edit_delete,
    })


@login_required
def trade_new(request):
    """
    Permet la création d'un nouveau trade, avec multi-upload de screenshots.
    """
    if request.method == "POST":
        form = TradeForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()

            # Multi-upload pour les captures
            files = request.FILES.getlist('screenshots')
            for f in files:
                if not f.content_type.startswith('image/'):
                    form.add_error(
                        None, 
                        'Tous les fichiers doivent être des images.'
                    )
                    return render(
                        request, 
                        'trades/trade_edit.html', 
                        {'form': form}
                    )
                Screenshot.objects.create(image=f, trade=trade)

            return redirect('trade_detail', pk=trade.pk)
        else:
            # Affichage des erreurs du formulaire
            return render(request, 'trades/trade_edit.html', {'form': form})
    else:
        form = TradeForm(user=request.user)
    return render(request, 'trades/trade_edit.html', {'form': form})


@login_required
def trade_edit(request, pk):
    """
    Permet la modification d'un trade existant, si l'utilisateur en est
    le propriétaire ou s’il est superuser, avec ajout de nouveaux screenshots.
    """
    trade = get_object_or_404(Trade, pk=pk)
    if trade.user != request.user and not request.user.is_superuser:
        return redirect('trade_list')

    if request.method == "POST":
        form = TradeForm(request.POST, request.FILES, instance=trade, user=request.user)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.save()

            # Gestion des nouveaux screenshots
            files = request.FILES.getlist('screenshots')
            for f in files:
                Screenshot.objects.create(image=f, trade=trade)

            return redirect('trade_detail', pk=trade.pk)
        else:
            return render(
                request, 
                'trades/trade_edit.html', 
                {'form': form, 'trade': trade}
            )
    else:
        form = TradeForm(instance=trade, user=request.user)
    return render(
        request,
        'trades/trade_edit.html',
        {'form': form, 'trade': trade}
    )


@login_required
def trade_delete(request, pk):
    """
    Permet la suppression d'un trade si l'utilisateur est propriétaire
    ou superuser.
    """
    trade = get_object_or_404(Trade, pk=pk)
    if trade.user != request.user and not request.user.is_superuser:
        return redirect('trade_list')

    trade.delete()
    return redirect('trade_list')


# -----------------------------------
# Vues pour les Stratégies

@login_required
def strategy_list(request):
    """
    Affiche la liste des stratégies. Le superuser voit toutes les stratégies,
    sinon seules celles de l'utilisateur connecté.
    """
    if request.user.is_superuser:
        strategies = Strategy.objects.all()
    else:
        strategies = Strategy.objects.filter(user=request.user)

    return render(request, 'trades/strategy_list.html', {'strategies': strategies})


@login_required
def strategy_detail(request, pk):
    # On récupère la stratégie sans filtrer sur user, 
    # pour permettre au coach d'y accéder
    strategy = get_object_or_404(Strategy, pk=pk)
    strategy_owner = strategy.user

    # Par défaut, on n'a pas d'ID élève
    student_id = None

    # Logique pour savoir si l'utilisateur peut modifier la stratégie
    # (ex : propriétaire ou superuser)
    can_edit_delete = (strategy_owner == request.user or request.user.is_superuser)

    # Si l'utilisateur est coach ET le propriétaire a pour coach cet utilisateur,
    # ET que ce n’est pas la même personne (donc pas un auto-coach ?)
    if (
        request.user.profile.is_coach
        and strategy_owner.profile.coach == request.user
        and strategy_owner != request.user
    ):
        # => c'est un coach légitime, on prépare le retour vers coach_student_trades
        student_id = strategy_owner.pk

    # Vérification d'accès minimale : 
    #  - propriétaire, 
    #  - superuser, 
    #  - ou coach légitime
    if not (
        can_edit_delete
        or (request.user.profile.is_coach and strategy_owner.profile.coach == request.user)
    ):
        return redirect('non_authorise')  # ou lever une 404

    screenshots = strategy.screenshots.all()

    return render(request, 'trades/strategy_detail.html', {
        'strategy': strategy,
        'screenshots': screenshots,
        'can_edit_delete': can_edit_delete,
        'student_id': student_id,  # <-- important pour le template
    })


@login_required
def strategy_new(request):
    """
    Permet la création d'une nouvelle stratégie, avec un formset pour
    uploader plusieurs screenshots.
    """
    if request.method == "POST":
        form = StrategyForm(request.POST)
        formset = StrategyScreenshotFormSet(
            request.POST, request.FILES, instance=None
        )
        if form.is_valid() and formset.is_valid():
            strategy = form.save(commit=False)
            strategy.user = request.user
            strategy.save()
            formset.instance = strategy
            formset.save()
            messages.success(request, "Stratégie créée avec succès.")
            return redirect('strategy_detail', pk=strategy.pk)
        else:
            # Débogage : affichage des erreurs
            print("Form valid:", form.is_valid())
            print("Form errors:", form.errors)
            print("Formset valid:", formset.is_valid())
            print("Formset errors:", formset.errors)
            for sub_form in formset.forms:
                print("Form:", sub_form, "errors:", sub_form.errors)
            messages.error(
                request, 
                "Veuillez corriger les erreurs ci-dessous."
            )
    else:
        form = StrategyForm()
        formset = StrategyScreenshotFormSet(instance=None)

    return render(
        request,
        'trades/strategy_edit.html', {
            'form': form,
            'formset': formset,
            'strategy': None
        }
    )


@login_required
def strategy_edit(request, pk):
    """
    Permet la modification d'une stratégie existante (appartenant à 
    l'utilisateur), avec possibilité de gérer plusieurs screenshots.
    """
    strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
    if request.method == "POST":
        form = StrategyForm(request.POST, instance=strategy)
        formset = StrategyScreenshotFormSet(
            request.POST, request.FILES, instance=strategy
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Stratégie mise à jour avec succès.")
            return redirect('strategy_detail', pk=strategy.pk)
        else:
            # Débogage : affichage des erreurs
            print("Form valid:", form.is_valid())
            print("Form errors:", form.errors)
            print("Formset valid:", formset.is_valid())
            print("Formset errors:", formset.errors)
            for sub_form in formset.forms:
                print("Form:", sub_form, "errors:", sub_form.errors)
            messages.error(
                request, 
                "Veuillez corriger les erreurs ci-dessous."
            )
    else:
        form = StrategyForm(instance=strategy)
        formset = StrategyScreenshotFormSet(instance=strategy)

    return render(
        request,
        'trades/strategy_edit.html', {
            'form': form,
            'formset': formset,
            'strategy': strategy
        }
    )


@login_required
def strategy_delete(request, pk):
    """
    Supprime une stratégie si l'utilisateur en est le propriétaire
    ou superuser.
    """
    strategy = get_object_or_404(Strategy, pk=pk)
    if strategy.user != request.user and not request.user.is_superuser:
        return redirect('strategy_list')
    strategy.delete()
    return redirect('strategy_list')


# -----------------------------------
# Vues pour l'authentification

def user_login(request):
    """
    Gère la connexion d'un utilisateur via un formulaire standard.
    """
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('trade_list')
        else:
            error = "Nom d'utilisateur ou mot de passe incorrect."
            return render(request, 'registration/login.html', {'error': error})
    else:
        return render(request, 'registration/login.html')


def user_logout(request):
    """
    Gère la déconnexion de l'utilisateur.
    """
    logout(request)
    return redirect('home')


def register(request):
    """
    Permet à un nouvel utilisateur de s'inscrire.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Votre compte a été créé avec succès.")
            login(request, user)
            return redirect('trade_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


# -----------------------------------
# Fonction parse_custom_datetime

def parse_custom_datetime(datetime_str):
    """
    Parser pour convertir des chaînes de caractères en datetime,
    en gérant 'BP'/'EP' et différents formats possibles.
    """
    if not datetime_str or datetime_str.strip() == '':
        return None

    datetime_str = datetime_str.replace('BP', '').replace('EP', '').strip()
    datetime_str = ' '.join(datetime_str.split())
    datetime_formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']

    for fmt in datetime_formats:
        try:
            naive_datetime = datetime.strptime(datetime_str, fmt)
            aware_datetime = timezone.make_aware(
                naive_datetime,
                timezone.get_current_timezone()
            )
            return aware_datetime
        except ValueError:
            continue

    print(f"Impossible de parser la date '{datetime_str}' avec les formats connus.")
    return None


# -----------------------------------
# Vue pour l'import CSV

@login_required
def import_csv(request):
    """
    Permet à l'utilisateur d'importer un fichier CSV ou TXT, 
    afin de créer en masse des objects Trade.
    """
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            selected_strategy = form.cleaned_data.get('strategy')

            data_set = csv_file.read().decode('utf-8-sig')
            io_string = csv.reader(data_set.splitlines(), delimiter='\t')
            headers = next(io_string, None)

            if not headers:
                messages.error(request, "Le fichier ne contient pas d'en-têtes valides.")
                return redirect('import_csv')

            headers = [h.strip() for h in headers]
            header_map = {header: index for index, header in enumerate(headers)}

            required_headers = [
                'Symbol',
                'Trade Type',
                'Entry DateTime',
                'Exit DateTime',
                'Entry Price',
                'Exit Price',
                'Trade Quantity',
                'Profit/Loss (C)'
            ]
            for rh in required_headers:
                if rh not in header_map:
                    messages.error(request, f"En-tête '{rh}' manquante dans le fichier.")
                    return redirect('import_csv')

            trades_count = 0
            for row in io_string:
                if not row or len(row) < len(headers):
                    continue

                symbol = row[header_map['Symbol']]
                trade_type = row[header_map['Trade Type']]
                entry_datetime_str = row[header_map['Entry DateTime']]
                exit_datetime_str = row[header_map['Exit DateTime']]
                entry_price_str = row[header_map['Entry Price']]
                exit_price_str = row[header_map['Exit Price']]
                quantity_str = row[header_map['Trade Quantity']]
                profit_loss_str = row[header_map['Profit/Loss (C)']]
                commission_str = (
                    row[header_map.get('Commission (C)', '')]
                    if 'Commission (C)' in header_map else ''
                )

                def clean_datetime_str(dt_str):
                    dt_str = dt_str.replace('BP', '').replace('EP', '').strip()
                    return ' '.join(dt_str.split())

                entry_datetime_str = clean_datetime_str(entry_datetime_str)
                exit_datetime_str = clean_datetime_str(exit_datetime_str)

                try:
                    entry_datetime = datetime.strptime(
                        entry_datetime_str, '%Y-%m-%d %H:%M:%S.%f'
                    )
                    exit_datetime = datetime.strptime(
                        exit_datetime_str, '%Y-%m-%d %H:%M:%S.%f'
                    )
                except ValueError:
                    try:
                        entry_datetime = datetime.strptime(
                            entry_datetime_str, '%Y-%m-%d %H:%M:%S'
                        )
                        exit_datetime = datetime.strptime(
                            exit_datetime_str, '%Y-%m-%d %H:%M:%S'
                        )
                    except ValueError:
                        continue

                if start_date and entry_datetime.date() < start_date:
                    continue
                if end_date and entry_datetime.date() > end_date:
                    continue

                try:
                    entry_price = float(entry_price_str.strip())
                    exit_price = float(exit_price_str.strip())
                    quantity = int(quantity_str.strip())
                    profit_loss = float(profit_loss_str.strip())
                    commission = (
                        float(commission_str.strip())
                        if commission_str.strip() else 0.0
                    )
                except ValueError:
                    continue

                Trade.objects.create(
                    user=request.user,
                    strategy=selected_strategy,
                    symbol=symbol.strip(),
                    trade_type=trade_type.strip(),
                    entry_datetime=entry_datetime,
                    exit_datetime=exit_datetime,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    profit_loss=profit_loss,
                    commission=commission
                )
                trades_count += 1

            messages.success(
                request,
                f"{trades_count} trade(s) importé(s) avec succès."
            )
            return redirect('trade_list')
    else:
        form = CSVUploadForm(user=request.user)

    return render(request, 'trades/import_csv.html', {'form': form})


# -----------------------------------
# Ajout de screenshot via la colonne

@login_required
def add_trade_screenshot(request, trade_id):
    """
    Permet d'ajouter un ou plusieurs screenshots à un trade.
    """
    trade = get_object_or_404(Trade, pk=trade_id, user=request.user)
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        if not files:
            messages.error(request, "Veuillez sélectionner au moins une image.")
            return redirect('trade_list')

        for f in files:
            Screenshot.objects.create(image=f, trade=trade)

        messages.success(
            request,
            f"{len(files)} capture(s) ajoutée(s) avec succès."
        )
        return redirect('trade_list')
    return redirect('trade_list')


@login_required
def update_trade_strategy(request, trade_id):
    """
    Permet de mettre à jour la stratégie d'un trade en sélectionnant
    une stratégie existante.
    """
    trade = get_object_or_404(Trade, pk=trade_id, user=request.user)
    if request.method == 'POST':
        strategy_id = request.POST.get('strategy')
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
    return redirect('trade_list')


# -----------------------------------
# Vues Coach / élève

@login_required
def coach_students_list(request):
    """
    Affiche la liste des étudiants (users) reliés à un coach.
    """
    if not request.user.profile.is_coach:
        return redirect('non_authorise')
    students = User.objects.filter(profile__coach=request.user)
    return render(request, 'coach/students_list.html', {'students': students})


@login_required
def coach_student_trades(request, student_id):
    """
    Le coach consulte les trades d'un étudiant, peut commenter,
    et filtrer par date de début/fin.
    """
    if not request.user.profile.is_coach:
        return redirect('non_authorise')

    student = get_object_or_404(User, pk=student_id)
    if student.profile.coach != request.user:
        return redirect('non_authorise')

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    trades = Trade.objects.filter(user=student)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            trades = trades.filter(entry_datetime__date__gte=start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            trades = trades.filter(entry_datetime__date__lte=end_date)
        except ValueError:
            pass

    # Ajout de commentaire
    if request.method == 'POST':
        trade_id = request.POST.get('trade_id')
        content = request.POST.get('content')
        if trade_id and content:
            trade = get_object_or_404(Trade, pk=trade_id, user=student)
            Comment.objects.create(
                trade=trade, 
                coach=request.user, 
                content=content
            )
            messages.success(request, "Commentaire ajouté avec succès.")
        return redirect('coach_student_trades', student_id=student.pk)

    return render(request, 'trades/coach/student_trades.html', {
        'student': student,
        'trades': trades,
        'start_date': start_date_str,
        'end_date': end_date_str,
    })


@login_required
def choose_coach(request):
    """
    Permet à un élève de choisir un coach en soumettant un formulaire.
    """
    if request.user.profile.is_coach:
        messages.error(request, "Vous êtes coach, vous ne pouvez pas choisir de coach.")
        return redirect('home')

    if request.user.profile.coach:
        messages.info(
            request,
            f"Vous avez déjà un coach : {request.user.profile.coach.username}"
        )
        return redirect('home')

    pending_req = CoachRequest.objects.filter(
        student=request.user, 
        accepted__isnull=True
    ).first()

    if pending_req:
        messages.info(
            request,
            f"Demande en attente auprès de {pending_req.coach.username}."
        )
        return redirect('home')

    if request.method == 'POST':
        form = CoachSelectionForm(request.POST)
        if form.is_valid():
            selected_coach = form.cleaned_data['coach']
            CoachRequest.objects.create(student=request.user, coach=selected_coach)
            messages.success(
                request,
                f"Demande envoyée à {selected_coach.username}."
            )
            return redirect('home')
    else:
        form = CoachSelectionForm()

    return render(request, 'trades/choose_coach.html', {'form': form})


@login_required
def coach_pending_requests(request):
    """
    Affiche les demandes en attente pour le coach connecté.
    """
    if not request.user.profile.is_coach:
        return redirect('non_authorise')
    requests_list = CoachRequest.objects.filter(
        coach=request.user,
        accepted__isnull=True
    )
    return render(
        request,
        'trades/coach_pending_requests.html',
        {'requests_list': requests_list}
    )


@login_required
def coach_respond_request(request, req_id):
    """
    Permet au coach d'accepter ou de refuser une demande d'élève.
    """
    if not request.user.profile.is_coach:
        return redirect('non_authorise')

    coach_req = get_object_or_404(
        CoachRequest,
        pk=req_id,
        coach=request.user,
        accepted__isnull=True
    )

    if 'accept' in request.POST:
        coach_req.accepted = True
        coach_req.save()
        student_profile = coach_req.student.profile
        student_profile.coach = request.user
        student_profile.save()
        messages.success(
            request, 
            f"Vous avez accepté {coach_req.student.username}."
        )
    elif 'refuse' in request.POST:
        coach_req.accepted = False
        coach_req.save()
        messages.info(
            request,
            f"Vous avez refusé {coach_req.student.username}."
        )

    return redirect('coach_pending_requests')


@login_required
def coach_students_list(request):
    """
    Affiche la liste des étudiants liés au coach, si l'utilisateur est coach.
    """
    if not request.user.profile.is_coach:
        return redirect('non_authorise')
    students = User.objects.filter(profile__coach=request.user)
    return render(request, 'trades/coach/students_list.html', {'students': students})


def update_trade_note(request, pk):
    """
    Permet d'ajouter une note à un trade (si aucune note n'existe déjà).
    """
    trade = get_object_or_404(Trade, pk=pk)
    if request.method == 'POST':
        if trade.note:
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Une note existe déjà pour ce trade.'
                })
            messages.error(
                request,
                f'Une note existe déjà pour le trade #{trade.id}.'
            )
            return redirect('trade_list')

        form = TradeNoteForm(request.POST, instance=trade)
        if form.is_valid():
            form.save()
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Note ajoutée avec succès.'
                })
            messages.success(
                request,
                f'La note du trade #{trade.id} a été ajoutée avec succès.'
            )
        else:
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': "Erreur lors de l'ajout de la note."
                })
            messages.error(
                request,
                f"Erreur lors de l'ajout de la note du trade #{trade.id}."
            )
    return redirect('trade_list')


def is_coach(user):
    return user.is_authenticated and user.profile.is_coach



@require_POST
@login_required
@user_passes_test(is_coach)
def add_trade_comment(request):
    """
    Ajoute un commentaire d'un coach sur un trade via requête AJAX.
    """
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'message': 'Requête non AJAX.'
        })

    trade_id = request.POST.get('trade_id')
    content = request.POST.get('content').strip()

    if not trade_id or not content:
        return JsonResponse({
            'status': 'error',
            'message': 'Tous les champs sont obligatoires.'
        })

    trade = get_object_or_404(Trade, pk=trade_id)

    # Création du commentaire
    Comment.objects.create(
        trade=trade,
        coach=request.user,
        content=content,
        created_at=timezone.now()
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Commentaire ajouté avec succès.'
    })

@login_required
def stats_view(request):
    # 1) Récupérer toutes les stratégies de l’utilisateur
    strategies = Strategy.objects.filter(user=request.user)

    # 2) Lire la stratégie choisie depuis la requête GET
    strategy_id = request.GET.get('strategy_id')

    # Variables pour le contexte
    selected_strategy = None
    trades = None
    chart_data = None
    total_profit = 0
    nb_trades = 0
    win_rate = 0

    if strategy_id:
        # Vérifier que la stratégie existe et appartient à l’utilisateur
        selected_strategy = get_object_or_404(Strategy, pk=strategy_id, user=request.user)

        # Récupérer tous les trades de cette stratégie
        trades = Trade.objects.filter(strategy=selected_strategy)

        nb_trades = trades.count()
        # Somme de profit_loss
        total_profit = sum(t.profit_loss for t in trades)

        # Calcul du taux de réussite
        nb_winning = trades.filter(profit_loss__gt=0).count()
        if nb_trades > 0:
            win_rate = (nb_winning / nb_trades) * 100

        # Préparer les données pour un graphique
        # Exemple : On veut tracer un "Line Chart" (ou bar) avec la date d’entrée et profit
        # On construit 2 listes x et y
        x_values = []
        y_values = []

        # On peut ordonner par date pour un tracé plus cohérent
        trades_ordered = trades.order_by('entry_datetime')

        cumulative = 0
        x_values = []
        y_values = []

        for trade in trades_ordered:
            # On incrémente le cumul
            cumulative += float(trade.profit_loss)

            # On convertit la date en string pour l’axe X
            date_str = trade.entry_datetime.strftime('%Y-%m-%d %H:%M:%S') if trade.entry_datetime else ''
            
            x_values.append(date_str)
            y_values.append(cumulative)

        chart_data = {
            'x': x_values,
            'y': y_values
        }


    # Contexte à passer au template
    context = {
        'strategies': strategies,
        'selected_strategy': selected_strategy,
        'total_profit': total_profit,
        'nb_trades': nb_trades,
        'win_rate': win_rate,
        'chart_data': json.dumps(chart_data) if chart_data else None
    }
    return render(request, 'trades/stats.html', context)