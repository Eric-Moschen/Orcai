from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import UserRegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard:home")
    else:
        form = UserRegistrationForm()
    return render(request, "users/register.html", {"form": form})
