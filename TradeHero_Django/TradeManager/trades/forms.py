# trades/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from .models import Trade, Strategy, Screenshot, Profile,Comment, CoachRequest

# --- Widgets ---

class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'


class MultiFileInput(forms.ClearableFileInput):
    """
    Permettre la sélection multiple (maintenir Ctrl/Cmd) sur un seul champ.
    """
    allow_multiple_selected = True


# --- Formulaires pour les Trades ---

class TradeForm(forms.ModelForm):
    """
    Formulaire principal pour créer/modifier un Trade.
    Ne définit pas de champ multi-upload car la logique
    de multi-screen se gère soit via inline formset,
    soit via getlist('screenshots') dans la vue.
    """
    def __init__(self, *args, **kwargs):
        # On récupère l'utilisateur si fourni dans la vue
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Si on a un utilisateur, on limite la queryset
        # du champ 'strategy' à ses stratégies uniquement
        if user is not None:
            self.fields['strategy'].queryset = Strategy.objects.filter(user=user)

    class Meta:
        model = Trade
        fields = [
            'strategy',
            'symbol',
            'trade_type',
            'entry_datetime',
            'exit_datetime',
            'entry_price',
            'exit_price',
            'quantity',
            'profit_loss',
            'commission',
            'note',
            'duration',
        ]
        widgets = {
            'strategy': forms.Select(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'trade_type': forms.Select(
                choices=[('Long', 'Long'), ('Short', 'Short')],
                attrs={'class': 'form-control'}
            ),
            'entry_datetime': DateTimeInput(attrs={'class': 'form-control'}),
            'exit_datetime': DateTimeInput(attrs={'class': 'form-control'}),
            'entry_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'exit_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'profit_loss': forms.NumberInput(attrs={'class': 'form-control'}),
            'commission': forms.NumberInput(attrs={'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'duration': forms.TextInput(attrs={'class': 'form-control'}),
        }


# Inline formset pour les screenshots liés à un Trade (optionnel).
# Si vous utilisez getlist('screenshots') dans la vue, vous pouvez ignorer ce formset.
ScreenshotFormSet = inlineformset_factory(
    Trade,
    Screenshot,
    fields=('image',),
    extra=1,
    can_delete=True
)


# --- Formulaire pour les Stratégies avec multi-upload ---

class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Entrez le nom de la stratégie'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Entrez la description de la stratégie'
            }),
        }

class ScreenshotForm(forms.ModelForm):
    class Meta:
        model = Screenshot
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control-file'
            }),
        }

    def __init__(self, *args, **kwargs):
        super(ScreenshotForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.image:
            self.fields['image'].required = False  # Rendre 'image' facultatif pour les instances existantes

StrategyScreenshotFormSet = inlineformset_factory(
    Strategy, 
    Screenshot,
    form=ScreenshotForm,
    fields=['image'],
    extra=1,
    can_delete=True
)

# --- Formulaire d'inscription utilisateur ---

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Adresse email'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom d\'utilisateur'
            }),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mot de passe'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Confirmez le mot de passe'
            }),
        }


# --- Formulaire d'import CSV ---

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='Sélectionnez un fichier CSV ou TXT',
        help_text='Formats acceptés : .csv, .txt'
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date de début'
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date de fin'
    )
    strategy = forms.ModelChoiceField(
        queryset=Strategy.objects.none(),
        label='Stratégie (optionnel)',
        required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['strategy'].queryset = Strategy.objects.filter(user=user)


# --- Formulaire de sélection de coach ---

class CoachSelectionForm(forms.Form):
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__is_coach=True),
        label="Choisir un coach",
        required=True
    )


class TradeNoteForm(forms.ModelForm):
    class Meta:
        model = Trade
        fields = ['note']
        widgets = {
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ajouter une note...',
            }),
        }

class CommentForm(forms.ModelForm):
    """
    Formulaire pour ajouter un commentaire à un Trade par un coach.
    """
    class Meta:
        model = Comment
        fields = ['trade', 'content']
        widgets = {
            'trade': forms.HiddenInput(),
            'content': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ajouter un commentaire'}),
        }