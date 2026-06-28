import os
import re
import PyPDF2
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
from django.conf import settings
import json

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
try:
    from groq import Groq
except ImportError:
    Groq = None

# --- ChromaDB: lazy-initialized, cloud-aware ---
# Connects to ChromaDB Cloud when CHROMA_HOST + CHROMA_API_KEY are present,
# falls back to local PersistentClient for development.
_chroma_collection = None

def _get_chroma_client():
    host = os.getenv('CHROMA_HOST')
    api_key = os.getenv('CHROMA_API_KEY')
    if host and api_key:
        return chromadb.HttpClient(
            host=host,
            headers={"X-Chroma-Token": api_key}
        )
    return chromadb.PersistentClient(path=os.path.join(settings.BASE_DIR, "chroma_db"))

def _get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        client = _get_chroma_client()
        _chroma_collection = client.get_or_create_collection(name="resumes")
    return _chroma_collection

# --- AI Clients ---
ai_client = genai.Client(
    api_key=os.getenv('GEMINI_API_KEY'),
    http_options=types.HttpOptions(timeout=60000)
)
groq_api_key = os.getenv('GROQ_API_KEY')
groq_client = Groq(api_key=groq_api_key) if Groq and groq_api_key else None

# --- Google Embeddings (replaces local SentenceTransformer + torch) ---
def _embed_texts(texts: list) -> list:
    """Batch-embeds strings via Google text-embedding-004.
    Returns list of 768-dim float vectors (one per input string)."""
    response = ai_client.models.embed_content(
        model='text-embedding-004',
        contents=texts
    )
    return [e.values for e in response.embeddings]


def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + " "
        return text
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None

def get_ats_score(resume_text, job_text):
    """Embeds both texts via Google and returns cosine similarity as a percentage."""
    vectors = _embed_texts([resume_text, job_text])
    similarity = cosine_similarity([vectors[0]], [vectors[1]])[0][0]
    return round(max(0, float(similarity) * 100), 1)

def chunk_text(text, chunk_size=150, overlap=30):
    """Sliding-window word chunker to stay within embedding token limits."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks

def scrub_pii(text):
    """Redacts emails, phone numbers, and LinkedIn URLs before any AI processing."""
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '[REDACTED EMAIL]', text)
    text = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[REDACTED PHONE]', text)
    text = re.sub(r'linkedin\.com/in/[a-zA-Z0-9_-]+', '[REDACTED LINKEDIN]', text)
    return text

def save_to_vector_db(application_id, job_id, student_name, resume_text):
    """Chunks, scrubs PII, embeds via Google, and upserts into ChromaDB."""
    safe_text = scrub_pii(resume_text)
    chunks = chunk_text(safe_text)

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

    embeddings = _embed_texts(chunks)  # list[list[float]], 768-dim each

    _get_collection().upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=chunks
    )

def generate_resume_feedback(prompt_context, similarity_score):
    """Uses Gemini to return a 5-axis radar chart score and text feedback."""
    trimmed_context = (prompt_context or "")[:2000]
    prompt = f"""
You are an expert AI Technical Recruiter. Generate data for a candidate evaluation Radar Chart.

CONTEXT & ANCHOR SCORE:
- The system calculated this candidate's Overall ATS Match Score: {similarity_score}%
- Candidate & Job Description Data: {trimmed_context}

YOUR INSTRUCTIONS:
1. Review the provided resume and job description.
2. Find specific strengths and weaknesses to distribute scores across 5 categories.
3. CRITICAL RULE: The scores you assign MUST average out to roughly {similarity_score}%.
4. Identify strengths/improvements (max 15 words per detail).

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
            config=types.GenerateContentConfig(temperature=0.0)
        )
        clean_json = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_json)
    except Exception as e:
        print(f"AI Sandbox Error: {e}")
        safe_score = int(similarity_score) if similarity_score else 0
        return {
            "radar_metrics": [
                {"category": "Core Tech Skills", "score": safe_score},
                {"category": "Quantifiable Impact", "score": max(0, safe_score - 10)},
                {"category": "Tool & Framework Stack", "score": safe_score},
                {"category": "Domain Expertise", "score": max(0, safe_score - 5)},
                {"category": "Project Complexity", "score": max(0, safe_score - 8)}
            ],
            "strengths": [{"category": "System Status", "detail": "Match scored via vector DB. AI feedback is busy."}],
            "improvements": [{"category": "System Status", "detail": "Click calculate again to retry AI insights."}]
        }

def chat_with_resumes(job_id, user_query):
    """True RAG: embeds query via Google, retrieves ChromaDB chunks, answers with Groq."""
    from .models import Application, Job

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return "Error: Could not find the job posting details."

    clean_query = (user_query or "").strip()
    greeting_query = re.sub(r'[^a-z\s]', '', clean_query.lower()).strip()
    if greeting_query in {"hi", "hello", "hey", "hii", "hai", "good morning", "good afternoon", "good evening"}:
        return "Hi! I'm **ResumeLens AI**. How can I help you?"

    if not clean_query:
        return "Hi! Ask me a question about this job's candidates and I'll help."

    # 1. Embed query — extract inner 1D vector so ChromaDB shape contract is satisfied
    query_vector = _embed_texts([clean_query])[0]  # [768 floats]

    # 2. Retrieve top 7 semantically relevant chunks scoped to this job
    results = _get_collection().query(
        query_embeddings=[query_vector],  # ChromaDB expects list[list[float]]
        n_results=7,
        where={"job_id": str(job_id)}
    )

    if not results['documents'][0]:
        return "I don't have enough resume data to answer that question."

    ranked_apps = list(
        Application.objects.filter(job=job)
        .select_related('student__user')
        .order_by('-ai_similarity_score', 'id')
    )
    rank_lookup = {str(app.id): rank for rank, app in enumerate(ranked_apps, start=1)}
    name_lookup = {
        str(app.id): (
            app.student.user.get_full_name().strip()
            or app.student.user.first_name
            or app.student.user.username
        )
        for app in ranked_apps
    }

    # 3. Build RAG context from retrieved chunks
    retrieved_context = ""
    unique_app_ids = set()
    for i, chunk in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        app_id = meta['application_id']
        student_name = name_lookup.get(app_id, meta['student_name'])
        rank = rank_lookup.get(app_id)
        candidate_label = f"{student_name} (#{rank})" if rank else student_name
        unique_app_ids.add(app_id)
        retrieved_context += f"--- MATCHING RESUME SNIPPET FROM: {candidate_label} ---\n{chunk}\n\n"

    # 4. Relational metadata for retrieved candidates only
    relational_context = ""
    for app in [a for a in ranked_apps if str(a.id) in unique_app_ids]:
        app_id = str(app.id)
        relational_context += (
            f"Candidate: {name_lookup.get(app_id, app.student.user.first_name)} "
            f"(#{rank_lookup[app_id]}) | ATS Score: {app.ai_similarity_score}% | Status: {app.status}\n"
        )

    # 5. Generate answer with Groq
    system_prompt = f"""
You are ResumeLens AI, a friendly recruitment co-pilot.
1. ZERO HALLUCINATION: Answer strictly from the provided candidate metadata and anonymized resume snippets.
2. NO ASSUMPTIONS: If a skill, project, or experience is not written, say it is not found.
3. BEST FIT: Combine ATS score with explicit resume evidence; give a clear recommendation.
4. RANKS ONLY: On each candidate's first mention, write Full Name (#N). After that, use only the name. Never use IDs.
5. READABILITY: Use markdown bullets when they improve clarity, and use bolding appropriately for candidate names/ranks, important skills, project names, scores, and final decisions. Do not over-bold every line.
6. LENGTH CONTROL: Match the depth to the question. Keep simple questions concise, but if asked for candidate details, comparisons, or resume-based summaries, include all key relevant details from the provided resumes and metadata.
7. TONE: Be warm, direct, and helpful like a chatbot, but stay professional.
8. LINK: Final line must be exactly: [ View on Leaderboard](/job/{job.id}/leaderboard/)
9. QUESTION-ONLY: Answer only what the recruiter actually asked. Do not add extra candidate summaries, comparisons, or overall reviews unless requested.
10. NATURAL STYLE: Sound conversational and human. Avoid robotic phrasing, canned intros, and repetitive labels.
11. NO OVER-EXPLAINING: Keep the response focused. If the question is narrow, give a narrow answer.
"""
    user_prompt = f"""
Recruiter question: "{clean_query}"

--- TARGET JOB DETAILS ---
Job Title: {job.title}
Job Description: {job.description}

--- RELEVANT CANDIDATE METADATA ---
{relational_context}

--- RETRIEVED RESUME SNIPPETS ---
{retrieved_context}
"""

    try:
        if not groq_client:
            raise ValueError("GROQ_API_KEY is not configured.")
        response = groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI chat error: {e}")
        return "AI Service temporarily busy. Please try again."
