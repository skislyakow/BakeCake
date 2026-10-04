from django.shortcuts import redirect, render


def lk(request):
    """Личный кабинет: только для вошедших, гостя отправляем на главную."""
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "lk.html")
