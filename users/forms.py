from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User

_INPUT = "w-full rounded-lg border border-white/10 bg-[#0B0B12] px-3 py-2 text-white outline-none focus:ring-2 focus:ring-[#4DA6FF]"


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password1", "password2")
        widgets = {
            "email": forms.EmailInput(attrs={"class": _INPUT, "autocomplete": "email"}),
            "first_name": forms.TextInput(attrs={"class": _INPUT}),
            "last_name": forms.TextInput(attrs={"class": _INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"class": _INPUT})
