from django import forms
from django.forms import inlineformset_factory
from .models import Playlist, PlaylistPosition, Song

class PlaylistForm(forms.ModelForm):
    """Główny formularz edycji metadanych playlisty."""
    class Meta:
        model = Playlist
        fields = ['name', 'description', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full p-4 bg-gray-900 border border-gray-700 rounded-2xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'placeholder': 'Nazwa Twojej playlisty'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full p-4 bg-gray-900 border border-gray-700 rounded-2xl text-white focus:ring-green-500 focus:border-green-500 outline-none',
                'rows': 3,
                'placeholder': 'O czym jest ta playlista?'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 bg-gray-900 border-gray-700 rounded text-green-500 focus:ring-green-500 focus:ring-offset-gray-900'
            })
        }
        labels = {
            'name': 'Nazwa playlisty',
            'description': 'Opis',
            'is_public': 'Publiczna (widoczna dla innych)'
        }

# Inline Formset do zarządzania piosenkami na playliście
PlaylistPositionFormSet = inlineformset_factory(
    Playlist, 
    PlaylistPosition,
    fields=['song', 'order'],
    extra=1, # Pozwala dodać jeden nowy utwór na końcu
    can_delete=True,
    widgets={
        'song': forms.Select(attrs={
            'class': 'flex-1 p-3 bg-gray-900 border border-gray-700 rounded-xl text-white outline-none focus:border-green-500'
        }),
        'order': forms.NumberInput(attrs={
            'class': 'w-20 p-3 bg-gray-900 border border-gray-700 rounded-xl text-white text-center outline-none focus:border-green-500'
        })
    }
)
