from django.shortcuts import redirect, render


def lk(request):
    """Личный кабинет: личные данные. Только для вошедших."""
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "lk.html")


def orders(request):
    """Мои заказы: только для вошедших."""
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "orders.html")
