"""
Pydantic models for PersonaPreparation API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime


class ResearchRequest(BaseModel):
    """Request model for person research."""
    person_name: str = Field(..., min_length=1, max_length=200, description="Name of the person to research")
    meeting_context: Optional[str] = Field(None, max_length=500, description="Optional context about the meeting")


class ResearchResponse(BaseModel):
    """Response model for research results."""
    success: bool = Field(..., description="Whether the research was successful")
    brief: Optional[str] = Field(None, description="The generated meeting brief in markdown format")
    person_name: str = Field(..., description="Name of the person researched")
    timestamp: str = Field(..., description="ISO 8601 timestamp of when the research was completed")
    iteration_count: Optional[int] = Field(None, description="Number of tool iterations used")
    error_message: Optional[str] = Field(None, description="Error message if the research failed")


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
