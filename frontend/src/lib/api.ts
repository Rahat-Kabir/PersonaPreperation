const resolvedBaseUrl = process.env.NEXT_PUBLIC_API_URL;
const API_ACCESS_TOKEN = process.env.NEXT_PUBLIC_API_ACCESS_TOKEN;

if (!resolvedBaseUrl) {
  throw new Error("NEXT_PUBLIC_API_URL is not configured. Set it to your backend URL.");
}

const API_BASE_URL = resolvedBaseUrl;

interface ResearchResponse {
  success: boolean;
  brief?: string | null;
  person_name: string;
  timestamp: string;
  error_message?: string | null;
}

export interface AgentEvent {
  event_type: "start" | "tool_call" | "tool_result" | "thinking" | "complete" | "error";
  data: Record<string, any>;
  timestamp: string;
  iteration: number | null;
}

const sanitizeBrief = (text: string) => {
  if (!text) return "";
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, "$1")
    .replace(/^[#>]+\s*/gm, "")
    .replace(/^-\s+/gm, "• ")
    .replace(/^\*\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
};

export async function generateBrief(personName: string, meetingContext: string) {
  const headers: HeadersInit = {
    "Content-Type": "application/json"
  };

  if (API_ACCESS_TOKEN) {
    headers["X-API-Key"] = API_ACCESS_TOKEN;
  }

  const response = await fetch(`${API_BASE_URL}/api/research`, {
    method: "POST",
    headers,
    body: JSON.stringify({ person_name: personName, meeting_context: meetingContext })
  });

  if (!response.ok) {
    throw new Error("Unable to generate meeting brief. Please try again.");
  }

  const data = (await response.json()) as ResearchResponse;

  if (!data.success || !data.brief) {
    throw new Error(data.error_message || "Research did not return a brief.");
  }

  return sanitizeBrief(data.brief);
}

export async function generateBriefStream(
  personName: string,
  meetingContext: string,
  onEvent: (event: AgentEvent) => void,
  onComplete: (brief: string) => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const headers: HeadersInit = {
      "Content-Type": "application/json"
    };

    if (API_ACCESS_TOKEN) {
      headers["X-API-Key"] = API_ACCESS_TOKEN;
    }

    const response = await fetch(`${API_BASE_URL}/api/research/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ person_name: personName, meeting_context: meetingContext })
    });

    if (!response.ok) {
      throw new Error("Unable to connect to research service. Please try again.");
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
          const eventMatch = line.match(/event:\s*(\w+)\ndata:\s*(.+)/s);
          if (eventMatch) {
            const [, eventType, eventData] = eventMatch;
            const event: AgentEvent = JSON.parse(eventData);

            // Call event handler
            onEvent(event);

            // Handle completion
            if (event.event_type === "complete" && event.data.brief) {
              onComplete(sanitizeBrief(event.data.brief));
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
