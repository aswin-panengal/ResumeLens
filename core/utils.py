import PyPDF2
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
import os
from django.conf import settings
import json


# 1. Load the AI Model 
# (This downloads a small but powerful embedding model the first time it runs)
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Setup ChromaDB Vector Database
# This creates a local folder called 'chroma_db' to store the vectors
chroma_client = chromadb.PersistentClient(path=os.path.join(settings.BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection(name="resumes")

def extract_text_from_pdf(pdf_file):
    """Reads the uploaded PDF and extracts the raw text."""
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + " "
    return text

def get_ats_score(resume_text, job_text):
    """Converts text to vectors and calculates the match percentage."""
    # Encode text into mathematical vectors
    resume_vector = model.encode([resume_text])
    job_vector = model.encode([job_text])
    
    # Calculate Cosine Similarity (Score between 0 and 1)
    similarity = cosine_similarity(resume_vector, job_vector)[0][0]
    
    # Convert to a clean percentage, ensuring it doesn't go below 0
    match_percentage = max(0, float(similarity) * 100)
    return round(match_percentage, 1)

def save_to_vector_db(application_id, student_name, resume_text):
    """Saves the resume into ChromaDB for the Chat feature later."""
    vector = model.encode(resume_text).tolist()
    
    collection.upsert(
        ids=[str(application_id)],
        embeddings=[vector],
        metadatas=[{
            "application_id": application_id, 
            "student_name": student_name,
            "type": "resume"
        }],
        documents=[resume_text]
    )

# Resume Analyzer

import google.generativeai as genai
# Note: In a production app, never hardcode the API key. Put it in a .env file!

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))




import json
import google.generativeai as genai

import json
import google.generativeai as genai

def generate_resume_feedback(prompt_context):
    """Uses GenAI to return a 5-point chart metric AND elite 3-point text analysis."""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are an elite Lead Corporate Recruiter evaluating a candidate against a specific Job Description.
    
    CRITICAL RESTRICTION: Return strictly valid JSON. Do not include markdown, backticks, or text outside the JSON.
    
    1. Evaluate the candidate's EXACT ALIGNMENT with the Job Description across 5 metrics to power a Radar Chart. 
    You must be highly critical and strict. 
    - If the job requires a skill (like Python) and they do not have it, score them below 30.
    - Do not grade their general ability; grade ONLY how perfectly they match this specific role. 
    - A generally good resume that does not fit the specific job description should receive very low scores (20s to 40s).
    
    2. Provide 3 specific strengths and 3 specific areas for improvement using the exact elite corporate categories provided below. Keep details under 15 words.
    
    Use this EXACT JSON structure:
    {{
      "radar_metrics": [
        {{"category": "Core Tech Skills", "score": 88}},
        {{"category": "Quantifiable Impact", "score": 65}},
        {{"category": "Tool & Framework Stack", "score": 90}},
        {{"category": "Domain Expertise", "score": 75}},
        {{"category": "Project Complexity", "score": 80}}
      ],
      "strengths": [
        {{"category": "Core Competency", "detail": "Max 15 words explaining alignment with technical or domain skills."}},
        {{"category": "Quantifiable Impact", "detail": "Max 15 words on measurable results shown in past projects."}},
        {{"category": "Domain Expertise", "detail": "Max 15 words on architectural or theoretical understanding."}}
      ],
      "improvements": [
        {{"category": "Missing Core Proficiency", "detail": "Max 15 words on a critical missing skill or tool."}},
        {{"category": "Scale/Complexity Gap", "detail": "Max 15 words on lack of enterprise-level complexity."}},
        {{"category": "Actionable Next Step", "detail": "Max 15 words suggesting a specific project to bridge the gap."}}
      ]
    }}
    
    Context:
    {prompt_context}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}
    

# RAG function 


import re
import PyPDF2
import google.generativeai as genai
from .models import Application, Job

def scrub_pii(text):
    """
    Privacy Filter: Redacts emails and phone numbers from resume text 
    before sending it to the LLM to ensure data minimization.
    """
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '[REDACTED EMAIL]', text)
    text = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[REDACTED PHONE]', text)
    text = re.sub(r'linkedin\.com/in/[a-zA-Z0-9_-]+', '[REDACTED LINKEDIN]', text)
    return text

def chat_with_resumes(job_id, user_query):
    """
    Fetches the Job, the Resumes, and the ATS data, anonymizes the text, 
    and uses Gemini to answer the recruiter's question with full context.
    """
    # 1. Fetch the specific Job and the Applications
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return "Error: Could not find the job posting details."
        
    applications = Application.objects.filter(job_id=job_id).select_related('student', 'student__user')
    
    if not applications.exists():
        return "There are no applicants for this job yet. I have no resumes to analyze."

    # 2. Extract text, apply Privacy Filter, and inject ATS Data
    context_text = ""
    for app in applications:
        if app.resume:
            try:
                reader = PyPDF2.PdfReader(app.resume.path)
                resume_text = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        resume_text += text + "\n"
                
                safe_resume_text = scrub_pii(resume_text)
                score = app.ai_similarity_score if app.ai_similarity_score else 0
                status = app.status.upper()
                
                # --- UNIQUE ID & NAME LOGIC ---
                first_name = app.student.user.first_name or "Candidate"
                last_initial = app.student.user.last_name[:1] + "." if app.student.user.last_name else ""
                
                # Grab the ID from the User model to prevent crashes
                student_id = app.student.user.id 
                
                # Clean name for the AI to use naturally
                candidate_identifier = f"{first_name} {last_initial}"
                
                # Link back to the leaderboard
                leaderboard_url = f"/job/{job.id}/applicants/"
                
                # We pass the ID to the AI so it can print it in the final button
                context_text += f"--- CANDIDATE: {candidate_identifier} (ID: {student_id}) ---\n"
                context_text += f"Leaderboard Link: {leaderboard_url}\n"
                context_text += f"ATS Vector Match Score: {score}%\n"
                context_text += f"Current System Status: {status}\n"
                context_text += f"Anonymized Resume Text:\n{safe_resume_text}\n\n"
                
            except Exception as e:
                # Print statement to catch any hidden PDF reading errors in your terminal!
                print(f"CRITICAL ERROR reading resume for App ID {app.id}: {str(e)}")
                continue 

    if not context_text.strip():
        return "I couldn't read the text from the submitted resumes. Please ensure they are valid PDFs."

    # 3. The Ultimate Zero-Hallucination Recruiter Prompt
    prompt = f"""
    You are ResumeLens AI, an elite, highly logical Technical Recruitment Assistant.
    You are assisting a human recruiter in evaluating a pool of candidates for the following role:
    
    --- TARGET JOB DETAILS ---
    Job Title: {job.title}
    Company: {job.company}
    Job Description & Requirements: {job.description}
    --------------------------
    
    Below is the extracted, anonymized data for all applicants. You have their 'ATS Vector Match Score' (calculated by a separate embedding model), their current pipeline status, and their resume text.
    
    CRITICAL RULES - DO NOT VIOLATE:
    1. ZERO HALLUCINATION: You must base your answers STRICTLY and ONLY on the provided "Anonymized Resume Text". 
    2. NO ASSUMPTIONS: If a skill or experience is not explicitly written, assume they do not have it.
    3. EVALUATING "BEST": Combine the ATS Vector Match Score with the specific skills in the text.
    4. BE DECISIVE: Give a clear recommendation or direct answer to the recruiter's question.
    5. PROFESSIONAL HYPERLINKS: DO NOT hyperlink the candidate's name every time you type it. Instead, write their name normally in the text. At the end of their evaluation, provide exactly ONE clickable action link formatted like this: [👉 Manage Status for Candidate Name (#ID)](Leaderboard Link). 
    6. FORMATTING: Use markdown, bullet points, and bold text for readability. Avoid large blocks of text.
    7. STRICT BREVITY (DEFAULT): By default, provide extremely short, concise answers (1-3 brief bullet points max). Do not write long paragraphs unless the recruiter explicitly asks for a "detailed", "comprehensive", or "full" explanation.
    
    Recruiter's Question: "{user_query}"
    
    --- START OF CANDIDATE DATA ---
    {context_text}
    --- END OF CANDIDATE DATA ---
    """
    
    # 4. Generate the response
    model = genai.GenerativeModel('gemini-2.5-flash')
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI Processing Error: {str(e)}"