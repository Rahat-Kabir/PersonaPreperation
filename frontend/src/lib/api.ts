const API_ACCESS_TOKEN = process.env.NEXT_PUBLIC_API_ACCESS_TOKEN;

function getApiBaseUrl() {
  const resolvedBaseUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!resolvedBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_URL is not configured. Set it to your backend URL.");
  }

  return resolvedBaseUrl;
}

interface ResearchResponse {
  success: boolean;
  brief?: string | null;
  person_name: string;
  timestamp: string;
  error_message?: string | null;
  disambiguation_status?: "direct" | "ambiguous" | "no_match" | null;
  selected_identity_name?: string | null;
}

export interface SelectedIdentity {
  name: string;
  title?: string | null;
  organization?: string | null;
  location?: string | null;
  profile_url?: string | null;
}

export interface IdentityCandidate extends SelectedIdentity {
  id: string;
  summary?: string | null;
  reason: string;
  confidence: number;
}

export interface DisambiguationResponse {
  needs_disambiguation: boolean;
  status: "direct" | "ambiguous" | "no_match";
  query: string;
  candidates: IdentityCandidate[];
  recommendation: string;
}

export interface AgentEvent {
  event_type: "start" | "tool_call" | "tool_result" | "thinking" | "complete" | "error";
  data: Record<string, any>;
  timestamp: string;
  iteration: number | null;
}

function buildHeaders(): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (API_ACCESS_TOKEN) {
    headers["X-API-Key"] = API_ACCESS_TOKEN;
  }
  return headers;
}

export async function exportBriefPDF(brief: string, personName: string): Promise<Blob> {
  const apiBaseUrl = getApiBaseUrl();

  const response = await fetch(`${apiBaseUrl}/api/export/pdf`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ brief, person_name: personName }),
  });

  if (!response.ok) {
    throw new Error("Unable to generate PDF. Please try again.");
  }

  return response.blob();
}


export async function generateBrief(
  personName: string,
  meetingContext: string,
  anthropicApiKey?: string
) {
  const apiBaseUrl = getApiBaseUrl();

  const response = await fetch(`${apiBaseUrl}/api/research`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({
      person_name: personName,
      meeting_context: meetingContext,
      anthropic_api_key: anthropicApiKey || undefined,
    })
  });

  if (!response.ok) {
    throw new Error("Unable to generate meeting brief. Please try again.");
  }

  const data = (await response.json()) as ResearchResponse;

  if (!data.success || !data.brief) {
    throw new Error(data.error_message || "Research did not return a brief.");
  }

  return data.brief;
}

export async function disambiguatePerson(
  personName: string,
  meetingContext: string,
  anthropicApiKey?: string
): Promise<DisambiguationResponse> {
  const apiBaseUrl = getApiBaseUrl();

  const response = await fetch(`${apiBaseUrl}/api/research/disambiguate`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({
      person_name: personName,
      meeting_context: meetingContext,
      anthropic_api_key: anthropicApiKey || undefined,
    })
  });

  if (!response.ok) {
    throw new Error("Unable to disambiguate person. Please try again.");
  }

  return (await response.json()) as DisambiguationResponse;
}

export async function generateBriefStream(
  personName: string,
  meetingContext: string,
  onEvent: (event: AgentEvent) => void,
  onComplete: (brief: string) => void,
  onError: (error: string) => void,
  options?: {
    selectedIdentity?: SelectedIdentity;
    continueAnyway?: boolean;
    anthropicApiKey?: string;
  }
): Promise<void> {
  try {
    const apiBaseUrl = getApiBaseUrl();

    const response = await fetch(`${apiBaseUrl}/api/research/stream`, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({
        person_name: personName,
        meeting_context: meetingContext,
        selected_identity: options?.selectedIdentity,
        continue_anyway: options?.continueAnyway || false,
        anthropic_api_key: options?.anthropicApiKey || undefined,
      })
    });

    if (!response.ok) {
      let detail = "Unable to connect to research service. Please try again.";
      try {
        const data = await response.json();
        if (data?.detail) {
          detail = data.detail;
        }
      } catch {
        // Keep default message if response is non-JSON.
      }
      throw new Error(detail);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Unable to read response stream.");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || ""; // Keep incomplete message in buffer

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          // Parse SSE format: "event: <type>\ndata: <json>"
          const eventMatch = line.match(/event:\s*(\w+)\ndata:\s*([\s\S]+)/);
          if (eventMatch) {
            const [, eventType, eventData] = eventMatch;
            const event: AgentEvent = JSON.parse(eventData);

            // Call event handler
            onEvent(event);

            // Handle completion
            if (event.event_type === "complete" && event.data.brief) {
              onComplete(event.data.brief);
            }

            // Handle errors
            if (event.event_type === "error") {
              const errorMsg = event.data.error || "An error occurred during research";
              onError(errorMsg);
            }
          }
        } catch (parseError) {
          console.error("Error parsing SSE event:", parseError, line);
        }
      }
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error occurred";
    onError(errorMessage);
    throw error;
  }
}
