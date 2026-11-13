from django.shortcuts import redirect, render


def lk(request):
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "lk.html")


def orders(request):
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "orders.html")
