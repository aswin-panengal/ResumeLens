from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import StudentSignUpForm, AdminSignUpForm, JobPostForm 
from .models import StudentProfile, Job
from .models import Application
from .forms import JobApplicationForm
from .utils import extract_text_from_pdf, get_ats_score, save_to_vector_db, generate_resume_feedback
from django.http import HttpResponse
from django.http import JsonResponse
import json
from .utils import chat_with_resumes 

# IMPORTS FOR OTP EMAIL VERIFICATION 
import random
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


# 1. The Home Page
def home(request):
    return render(request, 'core/home.html')

# 2. The Signup Page (UPDATED WITH OTP & ADMIN APPROVAL)
def signup_view(request):
    # Defaults to student if no type is in the URL
    user_type = request.GET.get('type', 'student')
    
    if request.method == 'POST':
        if user_type == 'admin':
            form = AdminSignUpForm(request.POST)
        else:
            form = StudentSignUpForm(request.POST)

        if form.is_valid():
            # Capture the created user object
            user = form.save() 
            
            # --- STUDENT FLOW (OTP) ---
            if user_type == 'student':
                # 1. Generate OTP
                otp = str(random.randint(100000, 999999))
                user.otp_code = otp
                user.otp_created_at = timezone.now()
                user.is_email_verified = False
                user.save()

                # 2. Send the Email
                subject = 'Verify your ResumeLens Account'
                message = f'Hello {user.first_name},\n\nYour 6-digit verification code is: {otp}\n\nThis code expires in 10 minutes.'
                send_mail(
                    subject, 
                    message, 
                    settings.EMAIL_HOST_USER, 
                    [user.email], 
                    fail_silently=False
                )

                # 3. Save ID in session so the verify page knows who is trying to verify
                request.session['verification_user_id'] = user.id
                
                messages.info(request, "We sent a 6-digit code to your email. Please verify your account.")
                return redirect('verify_email')
            
            # --- ADMIN FLOW (SUPER ADMIN APPROVAL) ---
            else:
                user.is_approved = False # Lock them out initially
                user.save()
                messages.success(request, "Admin account created! Please wait for Super Admin approval to log in.")
                return redirect('login')
    else:
        # If it's a GET request, just show the empty form
        if user_type == 'admin':
            form = AdminSignUpForm()
        else:
            form = StudentSignUpForm()

    return render(request, 'registration/signup.html', {
        'form': form, 
        'user_type': user_type
    })

# 3. The Router (UPDATED FOR SUPER ADMIN)
@login_required
def dashboard_redirect(request):
    # 1. Route the Super Admin (You) to the new approval dashboard
    if request.user.is_superuser:
        return redirect('superadmin_dashboard')
        
    # 2. Route the Placement Admin (Recruiters)
    elif request.user.is_placement_admin:
        if not request.user.is_approved:
            logout(request)
            messages.error(request, "Your admin account is still pending Super Admin approval.")
            return redirect('login')
        return redirect('admin_dashboard')
        
    # 3. Route the Students
    else:
        if not request.user.is_email_verified:
            logout(request)
            messages.error(request, "Please verify your email address before logging in.")
            return redirect('login')
        return redirect('student_dashboard')

# --- NEW: SUPER ADMIN DASHBOARD ---
@login_required
def superadmin_dashboard(request):
    # Security Check: Kick out anyone who isn't the master superuser
    if not request.user.is_superuser:
        messages.error(request, "Access Denied. Super Admin only.")
        return redirect('home')

    # Handle the Approval Button Click
    if request.method == 'POST':
        recruiter_id = request.POST.get('recruiter_id')
        action = request.POST.get('action')
        
        if recruiter_id and action == 'approve':
            recruiter = get_object_or_404(User, id=recruiter_id)
            recruiter.is_approved = True
            recruiter.save()
            messages.success(request, f"Recruiter {recruiter.first_name} has been officially approved!")
            return redirect('superadmin_dashboard')

    # Fetch lists to display on the page
    pending_recruiters = User.objects.filter(is_placement_admin=True, is_approved=False)
    approved_recruiters = User.objects.filter(is_placement_admin=True, is_approved=True)

    context = {
        'pending_recruiters': pending_recruiters,
        'approved_recruiters': approved_recruiters
    }
    return render(request, 'core/superadmin_dashboard.html', context)
# ----------------------------------

# 4. Student Dash
@login_required
def student_dashboard(request):
    all_jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    try:
        student = request.user.studentprofile
        my_applications = Application.objects.filter(student=student).select_related('job')
        
        # Get the latest score for the widget 
        latest_app = my_applications.order_by('-applied_at').first()
        latest_score = latest_app.ai_similarity_score if latest_app else None
        
        applied_job_ids = my_applications.values_list('job_id', flat=True)
        available_jobs = all_jobs.exclude(id__in=applied_job_ids)
        
    except AttributeError:
        my_applications = []
        available_jobs = all_jobs
        latest_score = None

    return render(request, 'core/student_dashboard.html', {
        'jobs': available_jobs,
        'my_applications': my_applications,
        'latest_score': latest_score # Make sure to pass this!
    })

# 5. Admin Dash 
@login_required
def admin_dashboard(request):
    # Security Check: Redirect if not an Admin
    if not request.user.is_placement_admin and not request.user.is_superuser:
        messages.error(request, "Access Denied. Faculty only.")
        return redirect('student_dashboard')

    # 1. Handle Job Posting Form Submission
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            # Save the job to the database
            job = form.save()
            
            # Show success message
            messages.success(request, f"Successfully posted opening for {job.title} at {job.company}!")
            
            # Redirect to the same page to clear the form and show the new job
            return redirect('admin_dashboard') 
    else:
        # If GET request, just show an empty form
        form = JobPostForm()

    # 2. Fetch all jobs for the "Live Feed" on the right side
    active_jobs = Job.objects.filter(is_active=True).order_by('-created_at')

    context = {
        'form': form,
        'jobs': active_jobs
    }
    return render(request, 'core/admin_dashboard.html', context)

# 6. Custom Log Out View
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully. See you soon!")
    return redirect('home')

# 7. Apply View
@login_required
def apply_for_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # 1. Check if the user is a student
    try:
        # THE FIX: Use 'studentprofile' 
        student_profile = request.user.studentprofile 
    except AttributeError:
        # This error happens if the User is an Admin (who has no student profile)
        messages.error(request, "Only students can apply for jobs.")
        return redirect('admin_dashboard')
    except StudentProfile.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect('student_dashboard')

    # 2. Check if already applied
    if Application.objects.filter(student=student_profile, job=job).exists():
        messages.warning(request, "You have already applied for this job!")
        return redirect('student_dashboard')

    # 3. Handle Form Submission
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.student = student_profile
            
            #  START AI ATS ENGINE 
            # 1. Extract text from the uploaded PDF
            resume_file = request.FILES['resume']
            resume_text = extract_text_from_pdf(resume_file)
            
            # 2. Combine Job Description & Skills for a better comparison
            job_context = f"{job.title} {job.required_skills} {job.description}"
            
            # 3. Calculate Score using our AI Model
            score = get_ats_score(resume_text, job_context)
            application.ai_similarity_score = score
            
            # 4. Save the application to PostgreSQL so it generates an ID
            application.save() 
            
            # 5. Save to ChromaDB for the Admin Chat Feature
            save_to_vector_db(application.id, request.user.first_name, resume_text)
            
            # Dynamic success message showing the score
            messages.success(request, f"Application submitted! Your Resume matched {score}% with the job requirements.")
            
            # Redirect to the new My Applications page to see the progress bar
            return redirect('my_applications') 
    else:
        form = JobApplicationForm()

    return render(request, 'core/job_apply.html', {'form': form, 'job': job})

# 8. Job applicants 
@login_required
def job_applicants(request, job_id):
    # Security: Only Admins can see this
    if not request.user.is_placement_admin and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('student_dashboard')

    # Get the Job
    job = get_object_or_404(Job, id=job_id)

    # HANDLE STATUS UPDATES (If Admin clicks a dropdown item)
    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        new_status = request.POST.get('new_status')
        if app_id and new_status:
            application = get_object_or_404(Application, id=app_id)
            application.status = new_status
            application.save()
            messages.success(request, f"Status updated to {new_status.title()} for {application.student.user.first_name}")
            return redirect('job_applicants', job_id=job.id)

    # Get all applications for this job, SORTED by highest AI score first
    # CHANGE 'ai_similarity_score' if your model field is named differently!
    applications = Application.objects.filter(job=job).select_related('student', 'student__user').order_by('-ai_similarity_score')

    context = {
        'job': job,
        'applications': applications
    }
    return render(request, 'core/job_applicants.html', context)

# 9. My application view 
@login_required
def my_applications(request):
    try:
        student = request.user.studentprofile
        applications = Application.objects.filter(student=student).select_related('job').order_by('-applied_at')
    except AttributeError:
        return redirect('admin_dashboard')

    return render(request, 'core/my_applications.html', {'applications': applications})

# 10. Sandbox for resume 
@login_required
def resume_sandbox(request):
    feedback = None
    real_score = None
    
    # 1. Fetch all active jobs for the dropdown menu
    active_jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    if request.method == 'POST' and request.FILES.get('resume'):
        resume_file = request.FILES['resume']
        job_id = request.POST.get('job_id') # Get the ID from the dropdown
        
        if job_id:
            # 2. Get the specific job from the database
            # Make sure you have 'from django.shortcuts import get_object_or_404' at the top!
            target_job = get_object_or_404(Job, id=job_id)
            
            # Combine the job details just like we do in the real application
            job_context = f"{target_job.title} {target_job.required_skills} {target_job.description}"
            
            # 3. Extract Resume Text
            resume_text = extract_text_from_pdf(resume_file)
            
            # 4. Calculate the REAL Vector Score
            real_score = get_ats_score(resume_text, job_context)
            
            # 5. Ask Gemini for Feedback tailored to this exact job
            prompt_context = f"Target Role: {target_job.title}\nJob Requirements: {target_job.required_skills}\n\nCandidate Resume:\n{resume_text}"
            feedback = generate_resume_feedback(prompt_context)
        
    return render(request, 'core/resume_sandbox.html', {
        'feedback': feedback, 
        'real_score': real_score,
        'jobs': active_jobs # Pass the jobs to the HTML
    })

@login_required
def toggle_job_status(request, job_id):
    # Safety check: Only admins can do this 
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')
    job = get_object_or_404(Job, id= job_id)
    job.is_active = not job.is_active
    job.save()

    status = "opened" if job.is_active else "closed"
    messages.success(request, f"Job '{job.title} has been {status}")
    return redirect('admin_dashboard')

@login_required
def job_chat(request, job_id):
    # Security: Only Admins can see this
    if not request.user.is_placement_admin and not request.user.is_superuser:
        return redirect('student_dashboard')
    
    # Get the specific job
    job = get_object_or_404(Job, id=job_id)

    # Handle the AJAX Chat Request (When the admin types a message)
    if request.method == 'POST':
        try:
            # Parse the JSON sent by the frontend chat box
            data = json.loads(request.body)
            user_query = data.get('message')

            if not user_query:
                return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

            # --- THE REAL RAG ENGINE ---
            # We pass the job ID and the admin's question to your Gemini function
            bot_response = chat_with_resumes(job.id, user_query)

            # Return Gemini's answer back to the chat interface
            return JsonResponse({'reply': bot_response})

        except Exception as e:
            # If anything breaks, tell the chat UI
            return JsonResponse({'error': str(e)}, status=500)

    # If it's a normal page load (GET request), render the Chat HTML interface
    return render(request, 'core/job_chat.html', {'job': job})

@login_required 
def edit_job(request, job_id):
    # SECURITY: Only Admins can edit jobs!
    if not request.user.is_placement_admin and not request.user.is_superuser:
        messages.error(request, "Access Denied. You cannot edit jobs.")
        return redirect('student_dashboard')

    job = get_object_or_404(Job, id=job_id)

    if request.method == 'POST':
        # Grab the new data from the form
        job.title = request.POST.get('title')
        job.company = request.POST.get('company')
        job.location = request.POST.get('location')
        job.description = request.POST.get('description')

        # save it to the database
        job.save()
        messages.success(request, 'Job posting updated successfully!')

        return redirect('admin_dashboard')
        
    context = {
        'job':job
    }
    return render(request, 'core/edit_job.html', context)

@login_required
def edit_profile(request):
    # 1. Security Check: Ensure only students can access this
    try:
        student = request.user.studentprofile
    except AttributeError:
        messages.error(request, "Admins do not have a student profile.")
        return redirect('admin_dashboard')

    if request.method == 'POST':
        # 2. Update the base User model (First and Last Name)
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()

        # 3. Update the StudentProfile model 
        # (Change 'branch' and 'graduation_year' if your model uses different field names!)
        student.branch = request.POST.get('branch', student.branch)
        student.graduation_year = request.POST.get('graduation_year', student.graduation_year)
        
        # Save the changes
        student.save()
        messages.success(request, "Your profile has been updated successfully!")
        
        return redirect('student_dashboard')

    # 4. GET request: Load the page with the current data
    context = {
        'student': student,
        'user': request.user
    }
    return render(request, 'core/edit_profile.html', context)


# 11. Email verification
def verify_email(request):
    # Grab the user ID we temporarily saved during signup
    user_id = request.session.get('verification_user_id')
    
    if not user_id:
        messages.error(request, "Please sign up first.")
        return redirect('signup')

    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        user = User.objects.get(id=user_id)
            
        # Security Check 1: Does the code match?
        if user.otp_code == user_otp:
            # Security Check 2: Is the code younger than 10 minutes?
            expiration_time = user.otp_created_at + timedelta(minutes=10)
                
            if timezone.now() < expiration_time:
                # Success! Unlock the account
                user.is_email_verified = True
                user.otp_code = None # Destroy the code so it can't be reused
                user.save()
                    
                messages.success(request, 'Email verified successfully! You can now log in.')
                del request.session['verification_user_id'] # Clean up the session data
                
                return redirect('login') 
            else:
                messages.error(request, 'This code has expired. Please sign up again.')
        else:
            messages.error(request, 'Invalid code. Please try again.')

    return render(request, 'registration/verify_email.html')