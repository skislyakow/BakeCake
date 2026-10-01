from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from apps.analytics import views as analytics_views
from apps.orders import views as order_views
from apps.payments import views as payment_views
from apps.pricing import views as pricing_views
from apps.users import views as user_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("api/auth/login/", user_views.login, name="api-login"),
    path("api/auth/logout/", user_views.logout, name="api-logout"),
    path("api/me/", user_views.me, name="api-me"),
    path("api/configurator/", pricing_views.configurator, name="api-configurator"),
    path("api/quote/", order_views.quote, name="api-quote"),
    path("api/orders/", order_views.orders, name="api-orders"),
    path("api/orders/<str:number>/", order_views.order_detail, name="api-order-detail"),
    path("api/orders/<str:number>/issue/", order_views.order_issue, name="api-order-issue"),
    path("api/payments/<int:order_id>/", payment_views.create_payment, name="api-payment"),
    path("api/yookassa/webhook/", payment_views.webhook, name="api-yookassa-webhook"),
    path("api/track/visit/", analytics_views.track_visit, name="api-track-visit"),
    path("api/admin/orders/", analytics_views.admin_orders, name="api-admin-orders"),
    path("api/admin/orders/<int:order_id>/", analytics_views.admin_order_patch, name="api-admin-order"),
    path("api/admin/stats/", analytics_views.admin_stats, name="api-admin-stats"),
    path("api/admin/export/orders.csv", analytics_views.export_orders_csv, name="api-export-orders"),
    path("api/admin/export/stats.csv", analytics_views.export_stats_csv, name="api-export-stats"),
]
