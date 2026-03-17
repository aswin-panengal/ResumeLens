from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Custom User Model
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_placement_admin = models.BooleanField(default=False)

    is_email_verified = models.BooleanField(default=False, help_text="True when student enters correct OTP.")
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    
    is_approved = models.BooleanField(default=False, help_text="Super Admin must check this for new Placement Admins.")

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
    BRANCH_CHOICES = [
        ('MCA', 'Master of Computer Applications'),
        ('CSE', 'Computer Science Engineering'),
        ('ECE', 'Electronics and Communication Engineering'),
        ('MECH', 'Mechanical Engineering'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    register_number = models.CharField(max_length=20, unique=True, verbose_name="University Register Number")
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    graduation_year = models.IntegerField(default=2026, verbose_name="Graduation Year")
    
    # AI Parser Field
    skills_extracted = models.TextField(blank=True, help_text="AI will fill this automatically")

    def __str__(self):
        # Fallback to username if first/last names are blank
        full_name = self.user.get_full_name() or self.user.username
        return f"{full_name} - {self.register_number}"
    

# 3. Job Description
class Job(models.Model):
    title = models.CharField(max_length=200, verbose_name="Job Title")
    company = models.CharField(max_length=200, verbose_name="Company Name")
    location = models.CharField(max_length=200, verbose_name="Location")
    description = models.TextField(verbose_name="Job Description")
    required_skills = models.CharField(max_length=500, help_text="Comma separated (e.g., Python, SQL, React)")
    
    # Notice we changed this to SET_NULL so deleting users doesn't crash the database
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_jobs')
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} at {self.company}"
    

# 4. Application Model
class Application(models.Model):
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('selected', 'Selected'),
    ]

    # CRITICAL FIX: Changed CASCADE to SET_NULL. This ensures application history stays even if the job is deleted.
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='applications')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    resume = models.FileField(upload_to='resumes/')
    ai_similarity_score = models.FloatField(default=0.0) 
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'student') 

    def __str__(self):
        job_title = self.job.title if self.job else "Deleted Job"
        return f"{self.student.user.username} applied for {job_title}"