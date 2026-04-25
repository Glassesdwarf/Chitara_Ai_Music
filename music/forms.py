from django import forms
from .models import Genre


class GenerateSongForm(forms.Form):
    title = forms.CharField(max_length=200, widget=forms.TextInput(
        attrs={"class": "form-input", "placeholder": "My midnight drive"}
    ))
    prompt = forms.CharField(widget=forms.Textarea(
        attrs={"class": "form-input", "rows": 4,
               "placeholder": "A dreamy synthwave track with soft drums and warm pads..."}
    ))
    genre = forms.ChoiceField(choices=Genre.choices, widget=forms.Select(
        attrs={"class": "form-input"}
    ))
