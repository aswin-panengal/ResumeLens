import json
import random
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse

from .models import User, StudentProfile, Job, Application
from .forms import StudentSignUpForm, AdminSignUpForm, JobPostForm, JobApplicationForm
from .utils import (
    extract_text_from_pdf, get_ats_score, save_to_vector_db, 
    generate_resume_feedback, chat_with_resumes
)

User = get_user_model()

# --- AUTH & SIGNUP ---

def home(request):
    return render(request, 'core/home.html')

# def signup_view(request):
#     user_type = request.GET.get('type', 'student')
    
#     if request.method == 'POST':
#         form = AdminSignUpForm(request.POST) if user_type == 'admin' else StudentSignUpForm(request.POST)

#         if form.is_valid():
#             user = form.save() 
            
#             if user_type == 'student':
#                 # OTP Generation
#                 otp = str(random.randint(100000, 999999))
#                 user.otp_code = otp
#                 user.otp_created_at = timezone.now()
#                 user.is_email_verified = False
#                 user.save()

#                 # Send Verification Email
#                 subject = 'Verify your ResumeLens Account'
#                 message = f'Hello {user.first_name},\n\nYour verification code is: {otp}\n\nExpires in 10 minutes.'
#                 send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

#                 request.session['verification_user_id'] = user.id
#                 messages.info(request, "Please enter the 6-digit code sent to your email.")
#                 return redirect('verify_email')
            
#             else:
#                 # Admin Flow
#                 user.is_approved = False
#                 user.save()
#                 messages.success(request, "Admin account created! Awaiting Super Admin approval.")
#                 return redirect('login')
#     else:
#         form = AdminSignUpForm() if user_type == 'admin' else StudentSignUpForm()

#     return render(request, 'registration/signup.html', {'form': form, 'user_type': user_type})
def signup_view(request):
    user_type = request.GET.get('type', 'student')
    
    if request.method == 'POST':
        form = AdminSignUpForm(request.POST) if user_type == 'admin' else StudentSignUpForm(request.POST)

        if form.is_valid():
            user = form.save() 
            
            if user_type == 'student':
                
                # THE TOGGLE SWITCH
                BYPASS_OTP = True
                
                if BYPASS_OTP:
                    # INSTANT BYPASS FLOW
                    user.is_email_verified = True
                    user.save()
                    messages.success(request, "Test Mode: Account instantly verified! You can log in.")
                    return redirect('login')
                else:
                    # OTP FLOW (Safe and untouched)
                    # OTP Generation
                    otp = str(random.randint(100000, 999999))
                    user.otp_code = otp
                    user.otp_created_at = timezone.now()
                    user.is_email_verified = False
                    user.save()

                    # Send Verification Email
                    subject = 'Verify your ResumeLens Account'
                    message = f'Hello {user.first_name},\n\nYour verification code is: {otp}\n\nExpires in 10 minutes.'
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

                    request.session['verification_user_id'] = user.id
                    messages.info(request, "Please enter the 6-digit code sent to your email.")
                    return redirect('verify_email')
            
            else:
                # Admin Flow
                user.is_approved = False
                user.save()
                messages.success(request, "Admin account created! Awaiting Super Admin approval.")
                return redirect('login')
    else:
        form = AdminSignUpForm() if user_type == 'admin' else StudentSignUpForm()

    return render(request, 'registration/signup.html', {'form': form, 'user_type': user_type})

def verify_email(request):
    user_id = request.session.get('verification_user_id')
    if not user_id:
        return redirect('signup')

    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        try:
            user = User.objects.get(id=user_id)
            if user.otp_code == user_otp:
                if timezone.now() < user.otp_created_at + timedelta(minutes=10):
                    user.is_email_verified = True
                    user.otp_code = None
                    user.save()
                    messages.success(request, 'Email verified! You can now log in.')
                    del request.session['verification_user_id']
                    return redirect('login')
                else:
                    messages.error(request, 'Code expired. Please sign up again.')
            else:
                messages.error(request, 'Invalid code.')
        except User.DoesNotExist:
            return redirect('signup')

    return render(request, 'registration/verify_email.html')

@login_required
def dashboard_redirect(request):
    if request.user.is_superuser:
        return redirect('superadmin_dashboard')
    elif request.user.is_placement_admin:
        if not request.user.is_approved:
            logout(request)
            messages.error(request, "Account pending approval.")
            return redirect('login')
        return redirect('admin_dashboard')
    else:
        if not request.user.is_email_verified:
            logout(request)
            messages.error(request, "Please verify your email.")
            return redirect('login')
        return redirect('student_dashboard')

def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('home')

# --- DASHBOARDS ---

@login_required
def superadmin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('home')

    if request.method == 'POST':
        recruiter_id = request.POST.get('recruiter_id')
        if recruiter_id:
            recruiter = get_object_or_404(User, id=recruiter_id)
            recruiter.is_approved = True
            recruiter.save()
            messages.success(request, f"Approved {recruiter.get_full_name()}")

    return render(request, 'core/superadmin_dashboard.html', {
        'pending_recruiters': User.objects.filter(is_placement_admin=True, is_approved=False),
        'approved_recruiters': User.objects.filter(is_placement_admin=True, is_approved=True)
    })

@login_required
def student_dashboard(request):
    all_jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    try:
        student = request.user.studentprofile
        my_apps = Application.objects.filter(student=student)
        applied_ids = my_apps.values_list('job_id', flat=True)
        
        context = {
            'jobs': all_jobs.exclude(id__in=applied_ids),
            'latest_score': my_apps.order_by('-applied_at').first().ai_similarity_score if my_apps.exists() else None
        }
    except AttributeError:
        context = {'jobs': all_jobs, 'latest_score': None}
    
    return render(request, 'core/student_dashboard.html', context)

@login_required
def admin_dashboard(request):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')
    return render(request, 'core/admin_dashboard.html', {'jobs': Job.objects.filter(is_active=True).order_by('-created_at')})

# --- JOB & APPLICATION LOGIC ---

@login_required
def create_job_view(request):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.save()
            messages.success(request, f"Job posted: {job.title}")
            return redirect('admin_dashboard')
    else:
        form = JobPostForm()
    return render(request, 'core/create_job.html', {'form': form})

@login_required
def apply_for_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    try:
        student_profile = request.user.studentprofile
    except AttributeError:
        messages.error(request, "Only students can apply.")
        return redirect('dashboard')

    if Application.objects.filter(student=student_profile, job=job).exists():
        messages.warning(request, "Already applied.")
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job, application.student = job, student_profile
            
            # AI Processing
            resume_text = extract_text_from_pdf(request.FILES['resume'])
            job_context = f"{job.title} {job.required_skills} {job.description}"
            score = get_ats_score(resume_text, job_context)
            
            application.ai_similarity_score = score
            application.save()
            save_to_vector_db(application.id, request.user.first_name, resume_text)
            
            messages.success(request, f"Applied! AI Match: {score}%")
            return redirect('my_applications')
    else:
        form = JobApplicationForm()
    return render(request, 'core/job_apply.html', {'form': form, 'job': job})

@login_required
def job_applicants(request, job_id):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')

    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        new_status = request.POST.get('new_status')
        application = get_object_or_404(Application, id=app_id)
        application.status = new_status
        application.save()
        messages.success(request, f"Status updated for {application.student.user.first_name}")

    # SORT BY DATE
    apps = Application.objects.filter(job=job).select_related('student__user').order_by('-applied_at')
    return render(request, 'core/job_applicants.html', {'job': job, 'applications': apps})



@login_required
def leaderboard(request, job_id):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')

    job = get_object_or_404(Job, id=job_id)

    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        new_status = request.POST.get('new_status')
        application = get_object_or_404(Application, id=app_id)
        application.status = new_status
        application.save()
        messages.success(request, f"Status updated to '{new_status.title()}' for {application.student.user.first_name}")
   
    apps = Application.objects.filter(job=job).select_related('student__user').order_by('-ai_similarity_score')
    
    return render(request, 'core/leaderboard.html', {'job': job, 'applications': apps})

@login_required
def my_applications(request):
    try:
        apps = Application.objects.filter(student=request.user.studentprofile).select_related('job').order_by('-applied_at')
        return render(request, 'core/my_applications.html', {'applications': apps})
    except AttributeError:
        return redirect('admin_dashboard')

# --- SPECIAL FEATURES ---

@login_required
def resume_sandbox(request):
    active_jobs = Job.objects.filter(is_active=True)
    feedback, real_score = None, None
    
    if request.method == 'POST' and request.FILES.get('resume'):
        job_id = request.POST.get('job_id')
        if job_id:
            target_job = get_object_or_404(Job, id=job_id)
            resume_text = extract_text_from_pdf(request.FILES['resume'])
            
            if resume_text:
                job_context = f"{target_job.title} {target_job.required_skills} {target_job.description}"
                
                # 1. Calculate the Math Score (Your code)
                real_score = get_ats_score(resume_text, job_context)
                
                # 2. THE FIX: Pass that real_score into the AI function so it can anchor the radar chart!
                context_string = f"Target: {target_job.title}\nJD: {target_job.description}\nResume: {resume_text}"
                feedback = generate_resume_feedback(context_string, real_score)
                
            else:
                messages.error(request, "Invalid PDF.")
        
    return render(request, 'core/resume_sandbox.html', {'feedback': feedback, 'real_score': real_score, 'jobs': active_jobs})

@login_required
def job_chat(request, job_id):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')
    
    job = get_object_or_404(Job, id=job_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            return JsonResponse({'reply': chat_with_resumes(job.id, data.get('message'))})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return render(request, 'core/job_chat.html', {'job': job})

@login_required
def toggle_job_status(request, job_id):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')
    job = get_object_or_404(Job, id=job_id)
    job.is_active = not job.is_active
    job.save()
    messages.success(request, f"Job {job.title} {'opened' if job.is_active else 'closed'}")
    return redirect('admin_dashboard')

@login_required 
def edit_job(request, job_id):
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')

    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        job.title = request.POST.get('title')
        job.company = request.POST.get('company')
        job.location = request.POST.get('location')
        
        # ADDED: Save the required skills to the database
        job.required_skills = request.POST.get('required_skills') 
        
        job.description = request.POST.get('description')
        job.save()
        messages.success(request, 'Updated successfully!')
        return redirect('admin_dashboard')
        
    return render(request, 'core/edit_job.html', {'job': job})

@login_required
def edit_profile(request):
    try:
        student = request.user.studentprofile
        if request.method == 'POST':
            user = request.user
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()

            student.branch = request.POST.get('branch', student.branch)
            student.graduation_year = request.POST.get('graduation_year', student.graduation_year)
            student.save()
            messages.success(request, "Profile updated!")
            return redirect('student_dashboard')

        return render(request, 'core/edit_profile.html', {'student': student, 'user': request.user})
    except AttributeError:
        return redirect('admin_dashboard')