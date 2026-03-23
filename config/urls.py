from django.contrib import admin
from django.urls import path, include
from core import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin & Auth
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-email/', views.verify_email, name='verify_email'),

    # General & Redirects
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # Student URLs
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('apply/<int:job_id>/', views.apply_for_job, name='apply_for_job'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('sandbox/', views.resume_sandbox, name='resume_sandbox'),

    # Recruiter/Placement Admin URLs
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/create-job/', views.create_job_view, name='create_job'),
    path('job/<int:job_id>/applicants/', views.job_applicants, name='job_applicants'),
    path('job/<int:job_id>/leaderboard/', views.leaderboard, name='leaderboard'),
    path('job/<int:job_id>/toggle/', views.toggle_job_status, name='toggle_job_status'),
    path('job/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('job/<int:job_id>/chat/', views.job_chat, name='job_chat'),

    # Super Admin
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
]

# Media handling for Resumes in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)