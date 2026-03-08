"""
Pydantic models for PersonaPreparation API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal


DisambiguationStatus = Literal["direct", "ambiguous", "no_match"]


class SelectedIdentity(BaseModel):
    """Optional selected identity anchor supplied by the client."""
    name: str = Field(..., min_length=1, max_length=200)
    title: Optional[str] = Field(None, max_length=200)
    organization: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    profile_url: Optional[str] = Field(None, max_length=500)


class IdentityCandidate(BaseModel):
    """Candidate identity returned from quick disambiguation search."""
    id: str = Field(..., description="Stable candidate id for UI selection")
    name: str = Field(..., description="Best-guess display name")
    title: Optional[str] = Field(None, description="Likely title/role")
    organization: Optional[str] = Field(None, description="Likely company/organization")
    location: Optional[str] = Field(None, description="Location hint if found")
    profile_url: Optional[str] = Field(None, description="Primary profile URL for this candidate")
    summary: Optional[str] = Field(None, description="Short human-readable summary for disambiguation")
    reason: str = Field(..., description="Why this candidate matches the query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Heuristic confidence score")


class ResearchRequest(BaseModel):
    """Request model for person research."""
    person_name: str = Field(..., min_length=1, max_length=200, description="Name of the person to research")
    meeting_context: Optional[str] = Field(None, max_length=500, description="Optional context about the meeting")
    selected_identity: Optional[SelectedIdentity] = Field(
        None, description="Selected identity from disambiguation step"
    )
    continue_anyway: bool = Field(
        default=False,
        description="If true, continue deep research even when disambiguation is ambiguous or no-match",
    )
    anthropic_api_key: Optional[str] = Field(
        None,
        description="User-provided Anthropic API key. If set, overrides the server default.",
    )


class ResearchResponse(BaseModel):
    """Response model for research results."""
    success: bool = Field(..., description="Whether the research was successful")
    brief: Optional[str] = Field(None, description="The generated meeting brief in markdown format")
    person_name: str = Field(..., description="Name of the person researched")
    timestamp: str = Field(..., description="ISO 8601 timestamp of when the research was completed")
    iteration_count: Optional[int] = Field(None, description="Number of tool iterations used")
    error_message: Optional[str] = Field(None, description="Error message if the research failed")
    disambiguation_status: Optional[DisambiguationStatus] = Field(
        None, description="Disambiguation status used before deep research"
    )
    selected_identity_name: Optional[str] = Field(None, description="Identity name used for final research")


class DisambiguationResponse(BaseModel):
    """Response model for quick name disambiguation."""
    needs_disambiguation: bool = Field(..., description="True when user selection is required")
    status: DisambiguationStatus = Field(..., description="direct | ambiguous | no_match")
    query: str = Field(..., description="Original query name")
    candidates: list[IdentityCandidate] = Field(default_factory=list)
    recommendation: str = Field(..., description="Human-readable next step guidance")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="Current timestamp")


class AgentEvent(BaseModel):
    """Server-Sent Event model for real-time agent updates."""
    event_type: Literal["start", "tool_call", "tool_result", "thinking", "complete", "error"] = Field(
        ..., description="Type of event being emitted"
    )
    data: dict[str, Any] = Field(..., description="Event payload data")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the event")
    iteration: Optional[int] = Field(None, description="Current iteration number in the agent loop")
