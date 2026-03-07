# ResumeLens: AI-Integrated Applicant Tracking System

ResumeLens is an Applicant Tracking System (ATS) built with Django and the Google Gemini API. It is designed to help recruiters manage job postings, parse candidate resumes, and use AI to evaluate applicants against specific job requirements. 

##  Key Features

* **AI Recruiter Assistant:** A built-in chat interface that allows recruiters to ask specific questions about the candidate pool, powered by Gemini 2.5 Flash.
* **Automated Data Privacy:** Uses Regular Expressions (Regex) to scrub sensitive candidate data (emails, phone numbers, LinkedIn URLs) from resumes before sending the text to the AI model.
* **Anonymous AI Routing:** Prevents data leakage by passing database integer IDs to the AI instead of candidate names, allowing the AI to generate accurate UI links without knowing the candidate's actual identity.
* **Resume Parsing & Scoring:** Extracts text from PDF uploads using PyPDF2 and provides an AI-generated match score based on the job description.
* **Status Pipeline:** A clean dashboard for recruiters to track and update candidate statuses (Applied, Shortlisted, Rejected, Selected).

##  Tech Stack

**Backend:**
* Python, Django
* Google Gemini API (gemini-2.5-flash)
* PyPDF2 (PDF text extraction)
* SQLite (Database)

**Frontend:**
* HTML5 & CSS3
* Bootstrap 5 (Responsive UI/UX)
* JavaScript & marked.js (For rendering Markdown links and bold text in the AI chat)

##  Local Setup Instructions

1. Clone the repository:
   ```bash
   git clone: https://github.com/aswin-panengal/ResumeLens.git
   cd ResumeLens 