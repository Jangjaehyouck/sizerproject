from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'common'

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='common/login.html'), name='login'),
    path('login/', auth_views.LoginView.as_view(template_name='common/login.html'), name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
]