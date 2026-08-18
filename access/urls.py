from django.urls import path
from .views import AdministratorCreateView, MonitorCreateView, LoginView, LogoutView, CurrentUserView

# Define your urls here.

app_name = "access"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("administrators/", AdministratorCreateView.as_view(), name="administrator-create"),
    path("monitors/", MonitorCreateView.as_view(), name="monitor-create"),
]