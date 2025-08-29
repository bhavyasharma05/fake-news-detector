"""
FastAPI backend for Fake News Detection
Integrates multiple APIs for comprehensive content analysis.
"""

import os
import json
import asyncio
import aiohttp
import urllib.parse
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv  # <-- add this import
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()  # <-- add this line

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Fake News Detector API starting up")
    yield
    await analyzer.close_session()
    logger.info("Fake News Detector API shutting down")

app = FastAPI(
    title="Fake News Detector API",
    description="API for analyzing news content credibility with multiple AI services",
    version="2.0.0",
    lifespan=lifespan
)

# Custom error handler for invalid JSON
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Request validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request body. Please provide valid JSON with required fields.",
            "detail": exc.errors()
        }
    )

# Enable CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Configuration
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
FACTCHECK_KEY = os.getenv("FACTCHECK_KEY", "")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
GEMINI_KEY = os.getenv("GEMINI_KEY", "")

# Log loaded keys for debugging
logger.info(f"SERPAPI_KEY: {SERPAPI_KEY}")
logger.info(f"FACTCHECK_KEY: {FACTCHECK_KEY}")
logger.info(f"HUGGINGFACE_TOKEN: {HUGGINGFACE_TOKEN}")
logger.info(f"GEMINI_KEY: {GEMINI_KEY}")

# Request timeout settings
API_TIMEOUT = 8.0
TOTAL_TIMEOUT = 20.0

class AnalyzeRequest(BaseModel):
    text: str
    url: str

class Source(BaseModel):
    title: str
    url: str
    snippet: str

class AnalyzeResponse(BaseModel):
    credibility_score: int
    label: str  # "Fake" | "Real" | "Uncertain"
    explanation: str
    sources: List[Source]

class FakeNewsAnalyzer:
    """Multi-API fake news analyzer following exact workflow specification"""
    
    def __init__(self):
        self.session = None
        self.reputable_domains = {
            'reuters.com', 'bbc.com', 'ap.org', 'nytimes.com', 
            'guardian', 'washingtonpost', 'wsj.com'
        }
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def analyze_content(self, text: str, url: str) -> AnalyzeResponse:
        """
        Main analysis workflow following exact specification
        """
        try:
            session = await self.get_session()
            
            # Step 1: SerpAPI Google News search
            sources = await self.search_news_sources(session, text)
            
            # Step 2: Google Fact Check Tools
            fact_check_summary = await self.check_fact_check_tools(session, text)
            
            # Step 3: Hugging Face Inference API
            hf_label, hf_score = await self.analyze_with_huggingface(session, text)
            
            # Step 4: Gemini final reasoning
            try:
                result = await self.get_gemini_analysis(
                    session, text, sources, fact_check_summary, hf_label, hf_score
                )
                return result
            except Exception as e:
                logger.error(f"Gemini analysis failed: {e}")
                # Fallback to local merge
                return self.fallback_local_merge(
                    text, sources, fact_check_summary, hf_label, hf_score
                )
                
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            # Return fallback response
            return AnalyzeResponse(
                credibility_score=50,
                label="Uncertain",
                explanation="Analysis could not be completed due to technical issues.",
                sources=[]
            )
    
    async def search_news_sources(self, session: aiohttp.ClientSession, text: str) -> List[Source]:
        """Step 1: SerpAPI Google News search"""
        try:
            encoded_text = urllib.parse.quote(text[:200])  # Limit query length
            url = f"https://serpapi.com/search.json?q={encoded_text}&tbm=nws&num=5&api_key={SERPAPI_KEY}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    news_results = data.get('news_results', [])
                    
                    sources = []
                    for item in news_results[:5]:
                        sources.append(Source(
                            title=item.get('title', ''),
                            url=item.get('link', ''),
                            snippet=item.get('snippet', '')
                        ))
                    
                    logger.info(f"SerpAPI found {len(sources)} sources")
                    return sources
                else:
                    logger.warning(f"SerpAPI failed with status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []
    
    async def check_fact_check_tools(self, session: aiohttp.ClientSession, text: str) -> Optional[Dict]:
        """Step 2: Google Fact Check Tools"""
        try:
            if not FACTCHECK_KEY:
                logger.warning("FACTCHECK_KEY not provided")
                return None
                
            encoded_text = urllib.parse.quote(text[:200])
            url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={encoded_text}&languageCode=en&pageSize=3&key={FACTCHECK_KEY}"
            
            async with session.get(url) as response:
                logger.info(f"Fact Check Tools response status: {response.status}")
                data = await response.text()
                logger.info(f"Fact Check Tools response body: {data}")
                if response.status == 200:
                    data = json.loads(data)
                    claims = data.get('claims', [])
                    
                    if claims and len(claims) > 0:
                        claim = claims[0]
                        claim_review = claim.get('claimReview', [])
                        if claim_review and len(claim_review) > 0:
                            review = claim_review[0]
                            return {
                                'rating': review.get('textualRating', ''),
                                'url': review.get('url', '')
                            }
                    
                    logger.info("No fact-check claims found")
                    return None
                else:
                    logger.warning(f"Fact Check Tools failed with status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Fact Check Tools failed: {e}")
            return None
    
    async def analyze_with_huggingface(self, session: aiohttp.ClientSession, text: str) -> tuple[str, float]:
        """Step 3: Hugging Face Inference API"""
        try:
            url = "https://router.huggingface.co/hf-inference/models/mrm8488/bert-tiny-finetuned-fake-news-detection"
            headers = {
                "Authorization": f"Bearer {HUGGINGFACE_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {"inputs": text[:1000]}  # Limit text length
            
            async with session.post(url, headers=headers, json=payload) as response:
                logger.info(f"HuggingFace response status: {response.status}")
                data = await response.text()
                logger.info(f"HuggingFace response body: {data}")
                if response.status == 200:
                    data = json.loads(data)
                    
                    # Parse HF response format
                    if isinstance(data, list) and len(data) > 0:
                        result = data[0]
                        if isinstance(result, list):
                            # Find highest confidence prediction
                            best_pred = max(result, key=lambda x: x.get('score', 0))
                            label = best_pred.get('label', 'UNCERTAIN').upper()
                            score = best_pred.get('score', 0.5)
                            
                            # Normalize label
                            if 'FAKE' in label or 'FALSE' in label:
                                normalized_label = "Fake"
                            elif 'REAL' in label or 'TRUE' in label:
                                normalized_label = "Real"
                            else:
                                normalized_label = "Uncertain"
                            
                            logger.info(f"HuggingFace: {normalized_label} ({score:.2f})")
                            return normalized_label, float(score)
                    
                    logger.warning("Unexpected HuggingFace response format")
                    return "Uncertain", 0.5
                else:
                    logger.warning(f"HuggingFace failed with status {response.status}")
                    return "Uncertain", 0.5
                    
        except Exception as e:
            logger.error(f"HuggingFace analysis failed: {e}")
            return "Uncertain", 0.5
    
    async def get_gemini_analysis(
        self, 
        session: aiohttp.ClientSession, 
        text: str, 
        sources: List[Source], 
        fact_check_summary: Optional[Dict], 
        hf_label: str, 
        hf_score: float
    ) -> AnalyzeResponse:
        """Step 4: Gemini final reasoning and JSON generation"""
        
        # Prepare data for Gemini
        sources_json = [{"title": s.title, "url": s.url, "snippet": s.snippet} for s in sources]
        fact_check_json = fact_check_summary if fact_check_summary else None
        
        prompt = f"""INSTRUCTIONS: You are a fact-check assistant. Use only the input data to produce ONE valid JSON object and NOTHING ELSE. Return only JSON with keys: credibility_score, label, explanation, sources. INPUT: {{"text":"{text[:500]}", "sources":{json.dumps(sources_json)}, "fact_check":{json.dumps(fact_check_json)}, "hf_label":"{hf_label}", "hf_score":{hf_score}}}. TASK: 1) compute credibility_score (0-100), 2) pick label (Fake/Real/Uncertain), 3) short explanation (1-2 sentences) referencing which sources influenced the decision, 4) return sources array (title,url,snippet)."""
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
                # REMOVE temperature and maxOutputTokens
            }
            
            async with session.post(url, headers=headers, json=payload) as response:
                logger.info(f"Gemini response status: {response.status}")
                data = await response.text()
                logger.info(f"Gemini response body: {data}")
                if response.status == 200:
                    data = json.loads(data)
                    
                    # Extract text from Gemini response
                    candidates = data.get('candidates', [])
                    if candidates and len(candidates) > 0:
                        content = candidates[0].get('content', {})
                        parts = content.get('parts', [])
                        if parts and len(parts) > 0:
                            response_text = parts[0].get('text', '')
                            
                            # Robustly extract JSON from response
                            import re
                            clean_text = response_text.strip()
                            # Remove markdown code block if present
                            if clean_text.startswith('```json'):
                                clean_text = clean_text[7:]
                            if clean_text.startswith('```'):
                                clean_text = clean_text[3:]
                            if clean_text.endswith('```'):
                                clean_text = clean_text[:-3]
                            clean_text = clean_text.strip()
                            # Try to extract JSON object using regex if extra text is present
                            match = re.search(r'(\{.*\})', clean_text, re.DOTALL)
                            if match:
                                clean_text = match.group(1)
                            try:
                                result_json = json.loads(clean_text)
                                # Validate required keys
                                required_keys = ['credibility_score', 'label', 'explanation', 'sources']
                                if all(key in result_json for key in required_keys):
                                    # Convert sources to Source objects
                                    sources_list = []
                                    for src in result_json['sources']:
                                        sources_list.append(Source(
                                            title=src.get('title', ''),
                                            url=src.get('url', ''),
                                            snippet=src.get('snippet', '')
                                        ))
                                    
                                    return AnalyzeResponse(
                                        credibility_score=int(result_json['credibility_score']),
                                        label=result_json['label'],
                                        explanation=result_json['explanation'],
                                        sources=sources_list
                                    )
                                else:
                                    logger.warning("Gemini response missing required keys")
                            except Exception as e:
                                logger.warning(f"Failed to parse Gemini JSON: {e}")
                
                logger.warning("Invalid Gemini response format")
                raise Exception("Invalid Gemini response")
                
        except Exception as e:
            logger.error(f"Gemini API failed: {e}")
            raise e
    
    def fallback_local_merge(
        self, 
        text: str, 
        sources: List[Source], 
        fact_check_summary: Optional[Dict], 
        hf_label: str, 
        hf_score: float
    ) -> AnalyzeResponse:
        """Fallback local merge when Gemini fails"""
        
        score = 50  # Base score
        explanation_parts = []
        
        # Apply fact-check adjustments
        if fact_check_summary:
            rating = fact_check_summary.get('rating', '').lower()
            if 'false' in rating:
                score -= 40
                explanation_parts.append("fact-checkers found false claims")
            elif any(term in rating for term in ['true', 'mostly true']):
                score += 30
                explanation_parts.append("fact-checkers verified claims")
            elif any(term in rating for term in ['mixture', 'misleading']):
                score -= 10
                explanation_parts.append("fact-checkers found mixed accuracy")
        
        # Apply HuggingFace adjustments
        if hf_label == "Fake":
            adjustment = round(hf_score * 40)
            score -= adjustment
            explanation_parts.append(f"AI model detected fake content (confidence: {hf_score:.1f})")
        elif hf_label == "Real":
            adjustment = round(hf_score * 20)
            score += adjustment
            explanation_parts.append(f"AI model verified content (confidence: {hf_score:.1f})")
        
        # Apply source reputation adjustments
        reputable_count = 0
        for source in sources:
            if any(domain in source.url.lower() for domain in self.reputable_domains):
                reputable_count += 1
        
        if reputable_count > 0:
            reputation_bonus = min(reputable_count * 8, 24)
            score += reputation_bonus
            explanation_parts.append(f"found {reputable_count} reputable source(s)")
        elif len(sources) > 2:
            score -= 5
            explanation_parts.append("sources are from less established outlets")
        
        # Clamp score and determine label
        score = max(0, min(100, score))
        
        if score >= 70:
            label = "Real"
        elif score >= 40:
            label = "Uncertain"
        else:
            label = "Fake"
        
        # Build explanation
        if explanation_parts:
            explanation = f"Analysis based on: {', '.join(explanation_parts)}."
        else:
            explanation = "Limited data available for comprehensive analysis."
        
        return AnalyzeResponse(
            credibility_score=score,
            label=label,
            explanation=explanation,
            sources=sources
        )

# Initialize analyzer
analyzer = FakeNewsAnalyzer()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Fake News Detector API v2.0",
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "analyze": "/api/fakenews/analyze",
            "health": "/health"
        }
    }

@app.post("/api/fakenews/analyze", response_model=AnalyzeResponse)
async def analyze_fake_news(request: AnalyzeRequest):
    """
    Analyze content for fake news indicators using multiple AI services
    
    Workflow:
    1. SerpAPI Google News search for related sources
    2. Google Fact Check Tools for existing fact-checks
    3. Hugging Face AI model for content classification
    4. Gemini for final reasoning and JSON generation
    """
    try:
        # Log incoming request for debugging
        logger.info(f"Received analysis request: text='{request.text[:100]}', url='{request.url}'")
        
        # Validate input
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Lower minimum text length to 30
        if len(request.text) < 30:
            raise HTTPException(status_code=400, detail="Text too short for analysis")
        
        # Run analysis with timeout
        try:
            result = await asyncio.wait_for(
                analyzer.analyze_content(request.text, request.url),
                timeout=TOTAL_TIMEOUT
            )
            return result
            
        except asyncio.TimeoutError:
            logger.error("Analysis timed out")
            return AnalyzeResponse(
                credibility_score=50,
                label="Uncertain",
                explanation="Analysis timed out. Unable to complete verification within time limit.",
                sources=[]
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in analyze endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during analysis"
        )

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "service": "Fake News Detector API",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "apis": {
            "serpapi": "configured" if SERPAPI_KEY else "missing_key",
            "factcheck": "configured" if FACTCHECK_KEY else "missing_key",
            "huggingface": "configured" if HUGGINGFACE_TOKEN else "missing_key",
            "gemini": "configured" if GEMINI_KEY else "missing_key"
        }
    }

# Additional endpoint for backward compatibility
@app.post("/analyze")
async def analyze_legacy(request: dict):
    """Legacy endpoint for backward compatibility"""
    try:
        # Convert old format to new format
        content = request.get('content', '')
        url = request.get('url', '')
        if not content.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        if len(content) < 50:
            raise HTTPException(status_code=400, detail="Text too short for analysis")
        analyze_request = AnalyzeRequest(
            text=content,
            url=url
        )
        result = await analyze_fake_news(analyze_request)
        # Convert to old format for compatibility
        return {
            "score": result.credibility_score,
            "label": f"{result.label} {'✅' if result.label == 'Real' else '⚠️' if result.label == 'Uncertain' else '❌'}",
            "explanations": [
                {
                    "type": "analysis",
                    "title": "Credibility Analysis",
                    "description": result.explanation
                }
            ],
            "evidence_links": [
                {
                    "source": source.title,
                    "url": source.url,
                    "description": source.snippet
                }
                for source in result.sources[:3]
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legacy endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)