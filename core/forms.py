from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import StudentProfile, Job, Application

# Best practice: Fetch the custom user model dynamically
User = get_user_model()

# 1. STUDENT SIGNUP FORM 
class StudentSignUpForm(UserCreationForm):
    # Personal Info
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, help_text="This will be your login username.", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    
    # Academic Info
    register_number = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': 'University Register Number', 'class': 'form-control'}))
    branch = forms.ChoiceField(choices=StudentProfile._meta.get_field('branch').choices, widget=forms.Select(attrs={'class': 'form-control'}))
    graduation_year = forms.IntegerField(initial=2026, required=True, widget=forms.NumberInput(attrs={'placeholder': 'Graduation Year (e.g., 2026)', 'class': 'form-control'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email")

    # --- GATE 1: THE DOMAIN & DUPLICATE EMAIL CHECKER ---
    def clean_email(self):
        email = self.cleaned_data.get('email')
        allowed_domain = "@pondiuni.ac.in" 
        
        if email and not email.endswith(allowed_domain):
            raise forms.ValidationError(f"Registration is restricted to students with a {allowed_domain} email address.")
        
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
            
        return email

    # --- GATE 2: THE REGISTER NUMBER CHECKER ---
    def clean_register_number(self):
        register_number = self.cleaned_data.get('register_number')
        
        if StudentProfile.objects.filter(register_number=register_number).exists():
            raise forms.ValidationError("This Register Number is already associated with an account.")
            
        return register_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  
        user.email = self.cleaned_data["email"]     
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_student = True
        
        if commit:
            user.save() 
            StudentProfile.objects.create(
                user=user,
                register_number=self.cleaned_data.get('register_number'),
                branch=self.cleaned_data.get('branch'),
                graduation_year=self.cleaned_data.get('graduation_year')
            )
        return user


# 2. ADMIN SIGNUP FORM
class AdminSignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Official Admin Email'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email")

    # --- GATE 3: ADMIN DUPLICATE EMAIL CHECKER ---
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An admin account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"] 
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_placement_admin = True 
        
        if commit:
            user.save()
        return user

# 3. Job description 
class JobPostForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'company', 'location', 'description', 'required_skills']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control p-3', 'placeholder': 'e.g. Senior Data Analyst'}),
            'company': forms.TextInput(attrs={'class': 'form-control p-3', 'placeholder': 'e.g. Amazon, Google'}),
            'location': forms.TextInput(attrs={'class': 'form-control p-3', 'placeholder': 'e.g. Bangalore (Hybrid)'}),
            'description': forms.Textarea(attrs={'class': 'form-control p-3', 'rows': 5, 'placeholder': 'Paste the full Job Description (JD) here...'}),
            'required_skills': forms.TextInput(attrs={'class': 'form-control p-3', 'placeholder': 'e.g. Python, SQL, PowerBI (Comma separated)'}),
        }

# 4. Resume form 
class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['resume']
        widgets = {
            'resume': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
        }

    # GATE 4: THE BACKEND PDF ENFORCER 
    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        
        if resume:
            if not resume.name.lower().endswith('.pdf'):
                raise forms.ValidationError("Security Error: Only PDF files are accepted by the AI parser.")
            
            # Optional: Add a size limit (e.g., 5MB = 5 * 1024 * 1024 bytes)
            if resume.size > 5242880:
                raise forms.ValidationError("File too large. Please upload a PDF under 5MB.")
                
        return resume