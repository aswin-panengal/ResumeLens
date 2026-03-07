from django.contrib import admin
from .models import JobPosting, Application

# Register the Job Posting Table
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'deadline', 'is_active')
    list_filter = ('is_active', 'company_name')

admin.site.register(JobPosting, JobPostingAdmin)

# Register the Application Table
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'job', 'status', 'ai_match_score')
    list_filter = ('status', 'job')

admin.site.register(Application, ApplicationAdmin)