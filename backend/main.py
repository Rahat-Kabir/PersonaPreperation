"""
FastAPI wrapper for PersonaPreparation agent.
Provides HTTP endpoints for the research agent functionality.
"""

import asyncio
import os
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from anthropic import Anthropic
import json

from models import (
    ResearchRequest,
    ResearchResponse,
    HealthResponse,
    AgentEvent,
    DisambiguationResponse,
)
from agent import research_person_with_tools, research_person_with_tools_stream, disambiguate_person_name
from tools import ToolExecutor
from utils import validate_person_name

# Load environment variables
load_dotenv()

# Security & rate limit configuration
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN")
RATE_LIMIT_REQUESTS = int(os.getenv("API_RATE_LIMIT", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("API_RATE_WINDOW_SECONDS", "60"))

# In-memory request tracking
rate_limit_lock = asyncio.Lock()
request_logs: dict[str, deque[float]] = defaultdict(deque)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PersonaPreparation API",
    description="AI-powered meeting preparation assistant with real-time web research",
    version="1.0.0"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Anthropic client and tool executor
anthropic_client: Optional[Anthropic] = None
tool_executor: Optional[ToolExecutor] = None


async def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """Ensure the caller provided a valid API key."""
    if not API_AUTH_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="API authentication token is not configured on the server"
        )
    if not x_api_key or x_api_key != API_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def enforce_rate_limit(request: Request) -> None:
    """Simple in-memory rate limiting per client IP."""
    if RATE_LIMIT_REQUESTS <= 0:
        return

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    async with rate_limit_lock:
        timestamps = request_logs[client_ip]
        while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

        timestamps.append(now)


def get_anthropic_client(user_api_key: Optional[str] = None) -> Anthropic:
    """Return an Anthropic client using the user-provided key or the server default."""
    key = user_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(
            status_code=400,
            detail="No Anthropic API key available. Provide one via the settings panel or configure ANTHROPIC_API_KEY on the server.",
        )
    return Anthropic(api_key=key)


@app.on_event("startup")
async def startup_event():
    """Initialize API clients on startup."""
    global anthropic_client, tool_executor

    logger.info("Initializing PersonaPreparation API...")

    if not API_AUTH_TOKEN:
        logger.error("API_AUTH_TOKEN not found in environment variables")
        raise RuntimeError("API_AUTH_TOKEN is required for authenticated access")

    # Initialize default Anthropic client (optional – users can supply their own key)
    env_key = os.getenv("ANTHROPIC_API_KEY")
    if env_key:
        anthropic_client = Anthropic(api_key=env_key)
        logger.info("Default Anthropic client initialized from environment.")
    else:
        logger.warning("ANTHROPIC_API_KEY not set – users must supply their own key.")

    # Initialize tool executor
    tool_executor = ToolExecutor()

    logger.info("API initialized successfully")


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "PersonaPreparation API",
        "version": "1.0.0",
        "description": "AI-powered meeting preparation assistant",
        "endpoints": {
            "health": "/api/health",
            "research": "/api/research (POST)",
            "research_stream": "/api/research/stream (POST)",
            "disambiguate": "/api/research/disambiguate (POST)",
        }
    }


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/research", response_model=ResearchResponse)
async def research_person(
    request: ResearchRequest,
    _: None = Depends(verify_api_key),
    __: None = Depends(enforce_rate_limit)
):
    """
    Research a person and generate a meeting brief.

    Args:
        request: ResearchRequest containing person_name and optional meeting_context

    Returns:
        ResearchResponse with the generated brief or error information
    """
    logger.info("Research request received.")

    # Validate person name
    is_valid, error_msg = validate_person_name(request.person_name)
    if not is_valid:
        logger.warning(f"Invalid person name: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    if not tool_executor:
        logger.error("Tool executor not initialized")
        raise HTTPException(status_code=500, detail="API not properly initialized")

    client = get_anthropic_client(request.anthropic_api_key)

    try:
        selected_identity_dict = request.selected_identity.model_dump() if request.selected_identity else None
        disambiguation = None
        if not selected_identity_dict:
            disambiguation = await disambiguate_person_name(
                tool_executor=tool_executor,
                person_name=request.person_name,
                meeting_context=request.meeting_context or "",
            )
            status = disambiguation["status"]
            if status in ("ambiguous", "no_match") and not request.continue_anyway:
                return ResearchResponse(
                    success=False,
                    brief=None,
                    person_name=request.person_name,
                    timestamp=datetime.now().isoformat(),
                    error_message=(
                        "Identity is ambiguous or not confidently found. "
                        "Call /api/research/disambiguate and select a candidate, "
                        "or set continue_anyway=true."
                    ),
                    disambiguation_status=status,
                )
            if status == "direct" and disambiguation.get("candidates"):
                selected_identity_dict = disambiguation["candidates"][0]

        # Perform research
        logger.info("Starting research workflow.")
        brief = await research_person_with_tools(
            client=client,
            tool_executor=tool_executor,
            person_name=request.person_name,
            meeting_context=request.meeting_context or "",
            selected_identity=selected_identity_dict,
            continue_anyway=request.continue_anyway,
        )

        if brief:
            logger.info("Research completed successfully.")
            return ResearchResponse(
                success=True,
                brief=brief,
                person_name=request.person_name,
                timestamp=datetime.now().isoformat(),
                iteration_count=None,
                disambiguation_status=(disambiguation["status"] if disambiguation else None),
                selected_identity_name=(selected_identity_dict.get("name") if selected_identity_dict else None),
            )
        else:
            logger.warning("Research failed to generate a brief.")
            return ResearchResponse(
                success=False,
                brief=None,
                person_name=request.person_name,
                timestamp=datetime.now().isoformat(),
                error_message="Research failed to generate a brief",
                disambiguation_status=(disambiguation["status"] if disambiguation else None),
            )

    except Exception as e:
        logger.error(f"Error during research: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during research: {str(e)}"
        )


@app.post("/api/research/stream")
async def research_person_stream(
    request: ResearchRequest,
    _: None = Depends(verify_api_key),
    __: None = Depends(enforce_rate_limit)
):
    """
    Research a person and generate a meeting brief with real-time SSE updates.

    Args:
        request: ResearchRequest containing person_name and optional meeting_context

    Returns:
        StreamingResponse with Server-Sent Events containing agent updates
    """
    logger.info("Streaming research request received.")

    # Validate person name
    is_valid, error_msg = validate_person_name(request.person_name)
    if not is_valid:
        logger.warning(f"Invalid person name: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    if not tool_executor:
        logger.error("Tool executor not initialized")
        raise HTTPException(status_code=500, detail="API not properly initialized")

    client = get_anthropic_client(request.anthropic_api_key)

    selected_identity_dict = request.selected_identity.model_dump() if request.selected_identity else None
    disambiguation = None
    if not selected_identity_dict:
        disambiguation = await disambiguate_person_name(
            tool_executor=tool_executor,
            person_name=request.person_name,
            meeting_context=request.meeting_context or "",
        )
        status = disambiguation["status"]
        if status in ("ambiguous", "no_match") and not request.continue_anyway:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Identity is ambiguous or not confidently found. "
                    "Call /api/research/disambiguate and select a candidate, "
                    "or set continue_anyway=true."
                ),
            )
        if status == "direct" and disambiguation.get("candidates"):
            selected_identity_dict = disambiguation["candidates"][0]

    async def event_generator():
        """Generate Server-Sent Events from agent updates."""
        try:
            logger.info("Starting streaming research workflow.")

            # Stream events from the agent
            async for event_dict in research_person_with_tools_stream(
                client=client,
                tool_executor=tool_executor,
                person_name=request.person_name,
                meeting_context=request.meeting_context or "",
                selected_identity=selected_identity_dict,
                continue_anyway=request.continue_anyway,
            ):
                # Validate event with Pydantic model
                event = AgentEvent(**event_dict)

                # Format as SSE
                # SSE format: "event: <event_type>\ndata: <json_data>\n\n"
                sse_data = json.dumps(event.model_dump())
                yield f"event: {event.event_type}\ndata: {sse_data}\n\n"

                logger.debug(f"Sent SSE event: {event.event_type}")

        except Exception as e:
            logger.error(f"Error during streaming research: {str(e)}", exc_info=True)
            # Send error event
            error_event = AgentEvent(
                event_type="error",
                data={"error": f"Internal server error: {str(e)}"},
                timestamp=datetime.now().isoformat(),
                iteration=None
            )
            yield f"event: error\ndata: {json.dumps(error_event.model_dump())}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )


@app.post("/api/research/disambiguate", response_model=DisambiguationResponse)
async def research_person_disambiguate(
    request: ResearchRequest,
    _: None = Depends(verify_api_key),
    __: None = Depends(enforce_rate_limit)
):
    """Run a quick low-cost disambiguation search before deep research."""
    logger.info("Disambiguation request received.")

    is_valid, error_msg = validate_person_name(request.person_name)
    if not is_valid:
        logger.warning(f"Invalid person name: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    if not tool_executor:
        logger.error("Tool executor not initialized")
        raise HTTPException(status_code=500, detail="API not properly initialized")

    result = await disambiguate_person_name(
        tool_executor=tool_executor,
        person_name=request.person_name,
        meeting_context=request.meeting_context or "",
    )
    return DisambiguationResponse(**result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
