from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Custom User Model
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_placement_admin = models.BooleanField(default=False)

    # Add explicit related_name arguments to fix the conflict
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="custom_user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_permissions_set",
        related_query_name="user",
    )

    def __str__(self):
        return self.username


# 2. Student Profile
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    register_number = models.CharField(max_length=20, unique=True, verbose_name="University Register Number")
    
    branch = models.CharField(max_length=50, choices=[
        ('MCA', 'Master of Computer Applications'),
        ('CSE', 'Computer Science Engineering'),
        ('ECE', 'Electronics and Communication Engineering'),
        ('MECH', 'Mechanical Engineering'),
    ])
    
    
    graduation_year = models.IntegerField(default=2026, verbose_name="Graduation Year")
    
    # Excellent field to keep for your Parser Engine aggregation
    skills_extracted = models.TextField(blank=True, help_text="AI will fill this automatically")

    def __str__(self):
        # Added last_name for a cleaner admin panel view
        return f"{self.user.first_name} {self.user.last_name} - {self.register_number}"
    
# 3. Job description
class Job(models.Model):
    title = models.CharField(max_length=200, verbose_name="Job Title")
    company = models.CharField(max_length=200, verbose_name="Company Name")
    location = models.CharField(max_length=200, verbose_name="Location")
    description = models.TextField(verbose_name="Job Description")
    required_skills = models.CharField(max_length=500, help_text="Comma separated (e.g., Python, SQL, React)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} at {self.company}"
    

# 4. Application model
class Application(models.Model):
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('selected', 'Selected'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    resume = models.FileField(upload_to='resumes/')
    
    # This is where the AI Magic will happen later!
    ai_similarity_score = models.FloatField(default=0.0) 
    
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'student') # Prevents applying to the same job twice

    def __str__(self):
        return f"{self.student.user.first_name} applied for {self.job.title}"