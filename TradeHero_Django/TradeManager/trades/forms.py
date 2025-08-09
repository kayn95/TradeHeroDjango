# trades/forms.py

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import Trade, Strategy, Screenshot, Comment

User = get_user_model()


# --- Widgets ---

class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class MultiFileInput(forms.ClearableFileInput):
    """Permettre la sélection multiple sur un seul champ."""
    allow_multiple_selected = True


# --- Formulaires pour les Trades ---

class TradeForm(forms.ModelForm):
    """
    Formulaire principal pour créer/modifier un Trade.
    Le multi-upload est géré par la vue via request.FILES.getlist('screenshots'),
    mais on expose un champ optionnel pour l'UX.
    """
    screenshots = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"class": "form-control", "multiple": True}),
        help_text="Vous pouvez sélectionner plusieurs images."
    )

    class Meta:
        model = Trade
        fields = [
            "strategy",
            "symbol",
            "trade_type",
            "entry_datetime",
            "exit_datetime",
            "entry_price",
            "exit_price",
            "quantity",
            "commission",
            "note",
        ]
        widgets = {
            "strategy": forms.Select(attrs={"class": "form-control"}),
            "symbol": forms.TextInput(attrs={"class": "form-control", "placeholder": "AAPL, BTCUSDT..."}),
            "trade_type": forms.Select(attrs={"class": "form-control"}),
            "entry_datetime": DateTimeInput(attrs={"class": "form-control"}),
            "exit_datetime": DateTimeInput(attrs={"class": "form-control"}),
            "entry_price": forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
            "exit_price": forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"}),
            "commission": forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Limiter les stratégies à l'utilisateur courant
        if user is not None:
            self.fields["strategy"].queryset = Strategy.objects.filter(user=user)

        # Choix pour le type (LONG/SHORT) depuis le modèle
        self.fields["trade_type"].widget = forms.Select(choices=Trade.SIDE_CHOICES)

    def clean(self):
        data = super().clean()
        entry = data.get("entry_datetime")
        exit_ = data.get("exit_datetime")
        if entry and exit_ and exit_ < entry:
            self.add_error("exit_datetime", "La date de sortie est antérieure à la date d'entrée.")
        return data


# Inline formset pour les screenshots liés à une Strategy
class ScreenshotForm(forms.ModelForm):
    class Meta:
        model = Screenshot
        fields = ["image"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre 'image' facultatif pour les instances existantes (édition)
        if self.instance and self.instance.pk and self.instance.image:
            self.fields["image"].required = False


StrategyScreenshotFormSet = inlineformset_factory(
    Strategy,
    Screenshot,
    form=ScreenshotForm,
    fields=["image"],
    extra=1,
    can_delete=True,
)


# --- Formulaire pour les Stratégies ---

class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom de la stratégie"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Description"}),
        }


# --- Formulaire d'inscription utilisateur ---

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Adresse email"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom d'utilisateur"}),
            "password1": forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Mot de passe"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirmez le mot de passe"}),
        }


# --- Formulaire d'import CSV/TSV ---

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Sélectionnez un fichier CSV/TSV",
        help_text="Formats acceptés : .csv, .tsv, .txt",
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de début",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de fin",
    )
    strategy = forms.ModelChoiceField(
        queryset=Strategy.objects.none(),
        label="Stratégie (optionnel)",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["strategy"].queryset = Strategy.objects.filter(user=user)


# --- Formulaire de sélection de coach ---

class CoachSelectionForm(forms.Form):
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__is_coach=True),
        label="Choisir un coach",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


# --- Notes & commentaires ---

class TradeNoteForm(forms.ModelForm):
    class Meta:
        model = Trade
        fields = ["note"]
        widgets = {
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Ajouter une note..."}
            ),
        }


class CommentForm(forms.ModelForm):
    """Formulaire pour ajouter un commentaire à un Trade par un coach."""
    class Meta:
        model = Comment
        fields = ["trade", "content"]
        widgets = {
            "trade": forms.HiddenInput(),
            "content": forms.Textarea(attrs={"rows": 2, "placeholder": "Ajouter un commentaire"}),
        }
