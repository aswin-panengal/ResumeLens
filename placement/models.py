from django.db import models
from django.utils import timezone
from core.models import User, StudentProfile

class JobPosting(models.Model):
    title = models.CharField(max_length=200)
    company_name = models.CharField(max_length=100)
    description = models.TextField(help_text="Paste the full job Description (JD) here for AI matching")


    # Who posted?
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)


    created_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} at {self.company_name}"
    

class Application(models.Model):
    STATUS_CHOICES = [
        ('APPLIED', 'Applied'),
        ('SHORTLISTED', 'Shortlisted'),
        ('REJECTED', 'Rejected'),
        ('HIRED', 'Hired'),
    ]

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name ='applications')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)

    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')

    ai_match_score = models.FloatField(default=0.0, help_text="AI calculated match percentage")


    class Meta:
        # ensure student can't apply to the same job twice
        unique_together = ('job', 'student')

    def __str__(self):
        return f"{self.student.user.username} -> {self.job.title} ({self.ai_match_score}%)"
    