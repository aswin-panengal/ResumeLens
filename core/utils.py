import os
import json
import re
import PyPDF2
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
from django.conf import settings

from dotenv import load_dotenv
load_dotenv()

# Modern Google GenAI SDK Import
from google import genai 

# 1. Load the Local AI Embedding Model 
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Setup ChromaDB Vector Database
chroma_client = chromadb.PersistentClient(path=os.path.join(settings.BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection(name="resumes")

# 3. Setup the Gemini AI Client
ai_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))


def extract_text_from_pdf(pdf_file):
    """Reads the uploaded PDF and extracts the raw text with error handling."""
    text = ""
    try:
        # We try to read the PDF inside the safety net
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + " "
        return text
        
    except Exception as e:
        # If the PDF is corrupted, 0 bytes, or fake, it catches the crash here!
        print(f"⚠️ Error reading PDF: {e}")
        return None

def get_ats_score(resume_text, job_text):
    """Converts text to vectors and calculates the match percentage."""
    resume_vector = model.encode([resume_text])
    job_vector = model.encode([job_text])
    
    similarity = cosine_similarity(resume_vector, job_vector)[0][0]
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

import json

# FIX 1: Add similarity_score to the arguments
def generate_resume_feedback(prompt_context, similarity_score):
    """Uses GenAI to return a 5-point chart metric AND elite 3-point text analysis."""
    
    # FIX 2: Standardized the variable to {similarity_score} everywhere
    prompt = f"""
You are an expert AI Technical Recruiter. Your task is to generate the data for a candidate evaluation Radar Chart.

CONTEXT & ANCHOR SCORE:
- The system has already calculated this candidate's Overall ATS Match Score: {similarity_score}%
- Candidate & Job Description Data: {prompt_context}

YOUR INSTRUCTIONS:
1. Review the provided resume and job description.
2. Find the candidate's specific strengths and weaknesses to distribute the scores across the 5 categories below.
3. CRITICAL RULE: The scores you assign to the 5 metrics MUST average out to roughly the Overall Score of {similarity_score}%. 
   - Example: If the overall score is 63%, do not give them scores in the 30s. Find the areas they are strongest in (maybe a 75 in Domain Expertise) and weakest in (maybe a 45 in Project Complexity) so the chart accurately reflects the {similarity_score}% reality.

THE 5 EXACT METRICS TO GRADE (0-100 Scale):
1. Core Tech Skills
2. Quantifiable Impact
3. Tool & Framework Stack
4. Domain Expertise
5. Project Complexity

OUTPUT FORMAT:
Return ONLY raw, valid JSON. No markdown, no backticks, no conversational text. Use this exact structure:

{{
  "radar_metrics": [
    {{"category": "Core Tech Skills", "score": 0}},
    {{"category": "Quantifiable Impact", "score": 0}},
    {{"category": "Tool & Framework Stack", "score": 0}},
    {{"category": "Domain Expertise", "score": 0}},
    {{"category": "Project Complexity", "score": 0}}
  ],
  "strengths": [
    {{"category": "Core Competency", "detail": "Max 15 words explaining a specific strength found in the resume."}},
    {{"category": "Quantifiable Impact", "detail": "Max 15 words on measurable results."}},
    {{"category": "Domain Expertise", "detail": "Max 15 words on their industry alignment."}}
  ],
  "improvements": [
    {{"category": "Missing Core Proficiency", "detail": "Max 15 words on a missing skill."}},
    {{"category": "Scale/Complexity Gap", "detail": "Max 15 words on lack of experience."}},
    {{"category": "Actionable Next Step", "detail": "Max 15 words suggesting how to improve."}}
  ]
}}
"""
    
    try:
        # Modern generation syntax 
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'temperature': 0.0}
        )
        clean_json = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}
    

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
    from .models import Application, Job # Keeping this localized to avoid circular imports

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return "Error: Could not find the job posting details."
        
    # 1. FIX: Order the applications EXACTLY like the leaderboard
    applications = Application.objects.filter(job_id=job_id).select_related('student', 'student__user').order_by('-ai_similarity_score')
    
    if not applications.exists():
        return "There are no applicants for this job yet. I have no resumes to analyze."

    context_text = ""
    # 2. FIX: Use enumerate to generate a Rank (1, 2, 3...)
    for rank, app in enumerate(applications, start=1):
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
                
                first_name = app.student.user.first_name or "Candidate"
                last_initial = app.student.user.last_name[:1] + "." if app.student.user.last_name else ""
                candidate_identifier = f"{first_name} {last_initial}"
                
                # 3. FIX: Feed the Rank instead of the ID!
                context_text += f"--- CANDIDATE: {candidate_identifier} (Rank #{rank}) ---\n"
                context_text += f"ATS Vector Match Score: {score}%\n"
                context_text += f"Current System Status: {status}\n"
                context_text += f"Anonymized Resume Text:\n{safe_resume_text}\n\n"
                
            except Exception as e:
                print(f"CRITICAL ERROR reading resume for App ID {app.id}: {str(e)}")
                continue 

    if not context_text.strip():
        return "I couldn't read the text from the submitted resumes. Please ensure they are valid PDFs."

    # 3. The Friendly (but Strict) Recruiter Co-Pilot Prompt
    prompt = f"""
    You are ResumeLens AI, a friendly, insightful, and highly helpful Recruitment Co-pilot. 
    You are assisting a human recruiter in evaluating a pool of candidates for the following role. 
    Speak to the recruiter like a trusted, intelligent colleague using a warm, engaging, and professional tone (similar to a premium email AI assistant).
    
    --- TARGET JOB DETAILS ---
    Job Title: {job.title}
    Company: {job.company}
    Required Skills: {job.required_skills}
    Job Description & Requirements: {job.description}
    --------------------------
    
    Below is the extracted, anonymized data for all applicants. You have their 'ATS Vector Match Score' (calculated by a separate embedding model), their current pipeline status, and their resume text.
    
    CRITICAL RULES - DO NOT VIOLATE:
    1. ZERO HALLUCINATION: You must base your answers STRICTLY and ONLY on the provided "Anonymized Resume Text". 
    2. NO ASSUMPTIONS: If a skill or experience is not explicitly written, assume they do not have it.
    3. EVALUATING "BEST": Combine the ATS Vector Match Score with the specific skills in the text.
    4. BE DECISIVE: Give a clear recommendation or direct answer to the recruiter's question.
    5. USE RANKS, NOT IDS: Never mention an internal database ID. Refer to candidates by their Name and Leaderboard Rank (e.g., "Applicant Name (Rank #1)").
    6. PROFESSIONAL HYPERLINKS: At the end of your response, provide exactly ONE clickable action link formatted exactly like this: [ View on Leaderboard](/job/{job.id}/leaderboard/). 
    7. FORMATTING: Use markdown, bullet points, and bold text for readability. Avoid large blocks of text.
    8. STRICT BREVITY (DEFAULT): By default, provide extremely short, concise answers (1-3 brief bullet points max).
    
    Recruiter's Question: "{user_query}"
    
    --- START OF CANDIDATE DATA ---
    {context_text}
    --- END OF CANDIDATE DATA ---
    """
    
    try:
        # Modern generation syntax 
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"AI Processing Error: {str(e)}"