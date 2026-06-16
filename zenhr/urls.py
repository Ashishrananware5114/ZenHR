from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='zenhr/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Core
    path('', views.dashboard_view, name='dashboard'),
    
    # Modules
    path('employees/', views.employee_list_view, name='employees'),
    path('employees/create/', views.create_employee_view, name='create_employee'),
    path('attendance/', views.attendance_view, name='attendance'),
    path('leaves/', views.leave_view, name='leaves'),
    path('payroll/', views.payroll_view, name='payroll'),
    path('ess/', views.ess_portal_view, name='ess_portal'),
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
    
    # API endpoints
    path('api/ai-query/', views.ai_query_api_view, name='ai_query_api'),
]
