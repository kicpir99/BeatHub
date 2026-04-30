from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile
from better_profanity import profanity

class UserSignUpForm(UserCreationForm):
    """Formularz rejestracji z walidacją nazwy użytkownika pod kątem wulgaryzmów."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    gender = forms.ChoiceField(
        choices=[
            ('M', 'Mężczyzna'),
            ('F', 'Kobieta'),
            ('O', 'Nie chcę podawać / Inna'),
        ],
        label="Płeć",
        initial='O',
        widget=forms.Select(attrs={
            'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and profanity.contains_profanity(username):
            raise forms.ValidationError('Twoja nazwa użytkownika zawiera niedozwolone słownictwo.')
        return username

class ProfileForm(forms.ModelForm):
    """Formularz do edycji profilu, zdjęcia i biogramu."""
    class Meta:
        model = Profile
        fields = ['avatar', 'gender', 'bio', 'location', 'instagram_url', 'twitter_url', 'website_url', 'visibility', 'show_profile_stats_publicly', 'show_detailed_stats_publicly']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-green-600 file:text-white hover:file:bg-green-500',
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full p-4 bg-gray-900 border border-gray-700 rounded-2xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'rows': 4,
                'placeholder': 'Napisz coś o sobie i swoim guście muzycznym...',
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'placeholder': 'np. Warszawa, Polska',
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'placeholder': 'https://instagram.com/twojprofil',
            }),
            'twitter_url': forms.URLInput(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'placeholder': 'https://x.com/twojprofil',
            }),
            'website_url': forms.URLInput(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'placeholder': 'https://twojastrona.pl',
            }),
            'visibility': forms.Select(attrs={
                'class': 'w-full p-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
            }),
            'show_profile_stats_publicly': forms.CheckboxInput(attrs={
                'class': 'toggle-switch-input',
            }),
            'show_detailed_stats_publicly': forms.CheckboxInput(attrs={
                'class': 'toggle-switch-input',
            }),
        }
        labels = {
            'avatar': 'Twoje zdjęcie profilowe',
            'gender': 'Płeć (używana do personalizacji zwrotów)',
            'bio': 'Coś o Tobie',
            'location': 'Lokalizacja',
            'instagram_url': 'Link do Instagrama',
            'twitter_url': 'Link do Twittera (X)',
            'website_url': 'Prywatna strona WWW',
            'visibility': 'Widoczność profilu',
            'show_profile_stats_publicly': 'Pokazuj wykresy na profilu',
            'show_detailed_stats_publicly': 'Dostęp do pełnych statystyk'
        }

    def clean(self):
        cleaned_data = super().clean()
        visibility = cleaned_data.get('visibility')
        bio = cleaned_data.get('bio')
        
        if visibility in ['public', 'followers'] and bio:
            if profanity.contains_profanity(bio):
                self.add_error('bio', 'Twój opis profilu nie może zawierać niedozwolonego słownictwa przy wybranym poziomie widoczności.')
                
        return cleaned_data