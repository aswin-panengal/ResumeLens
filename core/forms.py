from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import StudentProfile
from .models import Job
from .models import Application

# Best practice: Fetch the custom user model dynamically
User = get_user_model()

# 1. STUDENT SIGNUP FORM 
class StudentSignUpForm(UserCreationForm):
    # Personal Info
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, help_text="This will be your login username.", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    
    # Academic Info (No resume here, they upload it when applying!)
    register_number = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': 'University Register Number', 'class': 'form-control'}))
    branch = forms.ChoiceField(choices=StudentProfile._meta.get_field('branch').choices, widget=forms.Select(attrs={'class': 'form-control'}))
    graduation_year = forms.IntegerField(initial=2026, required=True, widget=forms.NumberInput(attrs={'placeholder': 'Graduation Year (e.g., 2026)', 'class': 'form-control'}))

    class Meta(UserCreationForm.Meta):
        model = User
        # UserCreationForm automatically handles 'password' and 'password confirmation'
        fields = ("first_name", "last_name", "email")

    def save(self, commit=True):
        # Save the core User first
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  # Set email as username
        user.email = self.cleaned_data["email"]     # Save to the actual email field too
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_student = True
        
        if commit:
            user.save() # Saves to the custom User table
            
            # Now create the linked StudentProfile with the new fields
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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"] # Set email as username
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_placement_admin = True # Crucial for routing them to the right dashboard
        
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