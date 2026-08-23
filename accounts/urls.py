from django.urls import path

from . import views


urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='account-register'),
    path('sign-in/', views.SignInView.as_view(), name='account-sign-in'),
    path('sign-out/', views.SignOutView.as_view(), name='account-sign-out'),
    path('me/', views.CurrentAccountView.as_view(), name='account-me'),
]
