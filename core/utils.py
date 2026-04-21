import os
import re
import PyPDF2
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
from django.conf import settings
import json

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
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + " "
        return text
    except Exception as e:
        print(f"⚠️ Error reading PDF: {e}")
        return None

def get_ats_score(resume_text, job_text):
    """Converts text to vectors and calculates the match percentage."""
    resume_vector = model.encode([resume_text])
    job_vector = model.encode([job_text])
    
    similarity = cosine_similarity(resume_vector, job_vector)[0][0]
    match_percentage = max(0, float(similarity) * 100)
    return round(match_percentage, 1)

def chunk_text(text, chunk_size=150, overlap=30):
    """Splits text into overlapping word chunks to bypass model token limits."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks

def scrub_pii(text):
    """Privacy Filter: Redacts emails, phone numbers, and LinkedIn URLs."""
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '[REDACTED EMAIL]', text)
    text = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[REDACTED PHONE]', text)
    text = re.sub(r'linkedin\.com/in/[a-zA-Z0-9_-]+', '[REDACTED LINKEDIN]', text)
    return text

def save_to_vector_db(application_id, job_id, student_name, resume_text):
    """Chunks the resume and saves multiple vectors to ChromaDB."""
    safe_text = scrub_pii(resume_text) 
    chunks = chunk_text(safe_text)
    
    # Create unique IDs and Metadata for each chunk
    ids = [f"app_{application_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "application_id": str(application_id), 
            "job_id": str(job_id), 
            "student_name": student_name,
            "chunk_index": i
        } 
        for i in range(len(chunks))
    ]
    
    embeddings = model.encode(chunks).tolist()
    
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=chunks
    )

def generate_resume_feedback(prompt_context, similarity_score):
    """Uses GenAI to return a 5-point chart metric AND text analysis."""
    prompt = f"""
You are an expert AI Technical Recruiter. Generate data for a candidate evaluation Radar Chart.

CONTEXT & ANCHOR SCORE:
- The system calculated this candidate's Overall ATS Match Score: {similarity_score}%
- Candidate & Job Description Data: {prompt_context}

YOUR INSTRUCTIONS:
1. Review the provided resume and job description.
2. Find specific strengths and weaknesses to distribute scores across 5 categories.
3. CRITICAL RULE: The scores you assign MUST average out to roughly {similarity_score}%. 

THE 5 EXACT METRICS TO GRADE (0-100 Scale):
1. Core Tech Skills
2. Quantifiable Impact
3. Tool & Framework Stack
4. Domain Expertise
5. Project Complexity

OUTPUT FORMAT:
Return ONLY raw, valid JSON. No markdown. Use this structure:
{{
  "radar_metrics": [
    {{"category": "Core Tech Skills", "score": 0}},
    {{"category": "Quantifiable Impact", "score": 0}},
    {{"category": "Tool & Framework Stack", "score": 0}},
    {{"category": "Domain Expertise", "score": 0}},
    {{"category": "Project Complexity", "score": 0}}
  ],
  "strengths": [
    {{"category": "Core Competency", "detail": "Max 15 words explaining a specific strength."}}
  ],
  "improvements": [
    {{"category": "Missing Skill", "detail": "Max 15 words on a missing skill."}}
  ]
}}
"""
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'temperature': 0.0}
        )
        clean_json = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_json)
    except Exception as e:
        return {"error": str(e)}

def chat_with_resumes(job_id, user_query):
    """True RAG: Embeds the query, retrieves chunks, and generates an answer."""
    from .models import Application, Job

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return "Error: Could not find the job posting details."

    # 1. Embed the Recruiter's Query
    query_vector = model.encode([user_query]).tolist()

    # 2. Retrieve the top 7 most relevant chunks from ChromaDB for THIS specific job
    results = collection.query(
        query_embeddings=query_vector,
        n_results=7, 
        where={"job_id": str(job_id)} 
    )

    if not results['documents'][0]:
        return "I don't have enough resume data to answer that question."

    # 3. Build the RAG Context using only the retrieved chunks
    retrieved_context = ""
    unique_app_ids = set()

    for i, chunk_text in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        app_id = meta['application_id']
        student_name = meta['student_name']
        unique_app_ids.add(app_id)
        
        retrieved_context += f"--- MATCHING RESUME SNIPPET FROM: {student_name} ---\n"
        retrieved_context += f"{chunk_text}\n\n"

    # 4. Fetch relational data for ONLY the retrieved candidates
    relational_context = ""
    relevant_apps = Application.objects.filter(id__in=unique_app_ids)
    for app in relevant_apps:
        relational_context += f"Candidate: {app.student.user.first_name} | ATS Score: {app.ai_similarity_score}% | Status: {app.status}\n"

    # 5. Send to Gemini
    prompt = f"""
    You are ResumeLens AI, a Recruitment Co-pilot. 
    A recruiter asked: "{user_query}"
    
    --- TARGET JOB DETAILS ---
    Job Title: {job.title}
    Job Description: {job.description}
    
    --- RELEVANT CANDIDATE METADATA ---
    {relational_context}
    
    --- RETRIEVED RESUME SNIPPETS ---
    {retrieved_context}
    
CRITICAL RULES - DO NOT VIOLATE:

    1. ZERO HALLUCINATION: You must base your answers STRICTLY and ONLY on the provided "Anonymized Resume Text".
    2. NO ASSUMPTIONS: If a skill or experience is not explicitly written, assume they do not have it.
    3. EVALUATING "BEST": Combine the ATS Vector Match Score with the specific skills in the text.
    4. BE DECISIVE: Give a clear recommendation or direct answer to the recruiter's question.
    5. USE RANKS, NOT IDS: Never mention an internal database ID. Refer to candidates by their Name and Leaderboard Rank (e.g., "Applicant Name (Rank #1)").
    6. PROFESSIONAL HYPERLINKS: At the end of your response, provide exactly ONE clickable action link formatted exactly like this: [ View on Leaderboard](/job/{job.id}/leaderboard/).
    7. FORMATTING: Use markdown, bullet points, and bold text for readability. Avoid large blocks of text.
    8. STRICT BREVITY (DEFAULT): By default, provide extremely short, concise answers (1-3 brief bullet points max).
    """
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'temperature': 0.1}
        )
        return response.text.strip()
    except Exception as e:
        return f"AI Processing Error: {str(e)}"