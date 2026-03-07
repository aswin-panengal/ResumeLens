from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, StudentProfile

# Register the Custom User Model (with the built-in password management)
admin.site.register(User, UserAdmin)

# Register the Student Profile
admin.site.register(StudentProfile)