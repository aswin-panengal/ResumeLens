"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core import views
from django.conf import settings           
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('signup/', views.signup_view, name='signup'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('apply/<int:job_id>/', views.apply_for_job, name='apply_for_job'),
    path('job/<int:job_id>/applicants/', views.job_applicants, name='job_applicants'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('sandbox/', views.resume_sandbox, name='resume_sandbox'),
    path('job/<int:job_id>/toggle/', views.toggle_job_status, name='toggle_job_status'),
    path('job/<int:job_id>/chat/', views.job_chat, name='job_chat'),
    path('job/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('profile/edit/', views.edit_profile, name ='edit_profile'), 
    path('verify-email/', views.verify_email, name = 'verify_email'),
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


