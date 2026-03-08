"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, Eye, EyeOff, KeyRound, Loader2, X } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  disambiguatePerson,
  generateBriefStream,
  type AgentEvent,
  type IdentityCandidate,
  type SelectedIdentity,
} from "@/lib/api";

const STORAGE_KEY = "persona_anthropic_api_key";

const navItems = [
  { label: "Home", href: "#" },
  { label: "Use Cases", href: "#usecases" },
  { label: "Blog", href: "#blog" },
  { label: "Contact", href: "#contact" },
];

const getToolLabel = (toolName: string) => {
  if (toolName === "tavily_search") return "Searching with Tavily";
  if (toolName === "brave_search") return "Searching with Brave";
  if (toolName === "firecrawl_scrape") return "Scraping webpage";
  return toolName;
};

export default function LandingPage() {
  const [personName, setPersonName] = useState("");
  const [context, setContext] = useState("");
  const [output, setOutput] = useState(
    "Tap Generate to craft a briefing in seconds."
  );
  const [isLoading, setIsLoading] = useState(false);
  const [currentStatus, setCurrentStatus] = useState("");
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<IdentityCandidate[]>([]);
  const [candidateNote, setCandidateNote] = useState("");

  // API key state
  const [apiKey, setApiKey] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [keySaved, setKeySaved] = useState(false);

  // Load key from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setApiKey(stored);
      setKeySaved(true);
    }
  }, []);

  const handleSaveKey = useCallback(() => {
    const trimmed = apiKey.trim();
    if (trimmed) {
      localStorage.setItem(STORAGE_KEY, trimmed);
      setApiKey(trimmed);
      setKeySaved(true);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      setApiKey("");
      setKeySaved(false);
    }
  }, [apiKey]);

  const handleClearKey = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setApiKey("");
    setKeySaved(false);
    setShowKey(false);
  }, []);

  const formDisabled = useMemo(
    () => !personName || !context || isLoading,
    [personName, context, isLoading]
  );

  const currentApiKey = apiKey.trim() || undefined;

  const startStreamingResearch = async (
    selectedIdentity?: SelectedIdentity,
    continueAnyway = false
  ) => {
    setIsLoading(true);
    setActivityLog([]);
    setCurrentStatus("Starting research...");

    await generateBriefStream(
      personName,
      context,
      (event: AgentEvent) => {
        if (event.event_type === "start") {
          setCurrentStatus(`Researching ${event.data.person_name}...`);
          setActivityLog((prev) => [
            ...prev,
            `Started research for ${event.data.person_name}`,
          ]);
        } else if (event.event_type === "thinking") {
          setCurrentStatus(event.data.message || "Processing...");
        } else if (event.event_type === "tool_call") {
          const toolLabel = getToolLabel(event.data.tool_name);
          setCurrentStatus(`${toolLabel}...`);

          let searchQuery = "";
          if (event.data.tool_input?.query) {
            searchQuery = `: "${event.data.tool_input.query}"`;
          } else if (event.data.tool_input?.url) {
            searchQuery = `: ${event.data.tool_input.url}`;
          }

          setActivityLog((prev) => [...prev, `${toolLabel}${searchQuery}`]);
        } else if (event.event_type === "tool_result") {
          const summary = event.data.result_summary;
          if (summary?.success) {
            setActivityLog((prev) => [...prev, `+ ${summary.message}`]);
          } else if (summary?.error) {
            setActivityLog((prev) => [...prev, `x ${summary.error}`]);
          }
        }
      },
      (brief: string) => {
        setCurrentStatus("Research complete!");
        setOutput(brief);
        setCandidates([]);
        setCandidateNote("");
        setIsLoading(false);
      },
      (error: string) => {
        setCurrentStatus("Error occurred");
        setOutput(`Error: ${error}`);
        setIsLoading(false);
      },
      { selectedIdentity, continueAnyway, anthropicApiKey: currentApiKey }
    );
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setOutput("");
    setActivityLog([]);
    setCandidates([]);
    setCandidateNote("");
    setCurrentStatus("Checking identity...");

    try {
      const disambiguation = await disambiguatePerson(personName, context, currentApiKey);

      if (disambiguation.status === "ambiguous" && disambiguation.candidates.length > 0) {
        setCandidates(disambiguation.candidates);
        setCandidateNote(disambiguation.recommendation);
        setCurrentStatus("Multiple people found. Select the correct one.");
        setOutput("Select the correct person, or continue anyway.");
        setIsLoading(false);
        return;
      }

      if (disambiguation.status === "no_match") {
        setCandidates([]);
        setCandidateNote(disambiguation.recommendation);
        setCurrentStatus("No confident match found.");
        setOutput("No confident match found. Refine details or continue anyway.");
        setIsLoading(false);
        return;
      }

      const selectedFromDirect =
        disambiguation.status === "direct" && disambiguation.candidates.length > 0
          ? disambiguation.candidates[0]
          : undefined;
      await startStreamingResearch(selectedFromDirect, false);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong while researching.";
      setOutput(`Error: ${message}`);
      setCurrentStatus("");
      setIsLoading(false);
    }
  };

  const handleCandidateSelect = async (candidate: IdentityCandidate) => {
    setOutput("");
    setCandidateNote(`Selected: ${candidate.name}`);
    setCandidates([]);

    try {
      await startStreamingResearch(candidate, false);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong while researching.";
      setOutput(`Error: ${message}`);
      setCurrentStatus("");
      setIsLoading(false);
    }
  };

  const handleContinueAnyway = async () => {
    setOutput("");
    setCandidates([]);

    try {
      await startStreamingResearch(undefined, true);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong while researching.";
      setOutput(`Error: ${message}`);
      setCurrentStatus("");
      setIsLoading(false);
    }
  };

  const hasDisambiguationChoices = candidates.length > 0 || !!candidateNote;

  const maskedKey = apiKey
    ? `${apiKey.slice(0, 7)}${"*".repeat(Math.max(0, apiKey.length - 11))}${apiKey.slice(-4)}`
    : "";

  return (
    <main className="relative isolate w-full overflow-hidden rounded-[32px] border border-[#d8d4c7] bg-gradient-to-b from-[#fdfcf8] to-[#f2efe8] shadow-soft">
      <div className="absolute inset-0 opacity-60" aria-hidden>
        <div className="h-full w-full bg-[radial-gradient(circle_at_top,_rgba(255,255,255,.9),_rgba(255,255,255,0))]" />
      </div>
      <div className="relative z-10 w-full max-w-5xl px-6 py-8 sm:px-10 lg:px-16">
        <header className="flex flex-col items-center justify-between gap-6 pb-12 text-[#1c1915] sm:flex-row">
          <div className="text-xl font-semibold tracking-[0.2em]">
            PersonaPreparation
          </div>
          <div className="flex items-center gap-6">
            <nav className="flex gap-6 text-sm font-semibold uppercase tracking-[0.2em]">
              {navItems.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  className="transition hover:text-black"
                >
                  {item.label}
                </a>
              ))}
            </nav>
            <button
              type="button"
              onClick={() => setShowSettings((prev) => !prev)}
              className={`group relative flex h-9 w-9 items-center justify-center rounded-full border transition-all duration-300 ${
                showSettings
                  ? "border-[#1c1915] bg-[#1c1915] text-[#f9f7f2]"
                  : keySaved
                    ? "border-emerald-400/60 bg-emerald-50 text-emerald-700 hover:border-emerald-500"
                    : "border-[#d8d4c7] bg-white/80 text-[#7a7666] hover:border-[#1c1915]/40 hover:text-[#1c1915]"
              }`}
              aria-label="API Settings"
            >
              <KeyRound className="h-4 w-4" />
              {keySaved && !showSettings && (
                <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-500" />
              )}
            </button>
          </div>
        </header>

        {/* API Key Settings Panel */}
        <div
          className={`overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            showSettings ? "mb-8 max-h-[300px] opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <div className="rounded-[24px] border border-[#c8b89a]/40 bg-gradient-to-br from-[#faf8f3] via-white to-[#f5f0e6] p-6 shadow-panel">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-[#1c1915] to-[#3d3730] text-[#f9f7f2] shadow-md">
                  <KeyRound className="h-4.5 w-4.5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-wide text-[#1c1915]">
                    Anthropic API Key
                  </h3>
                  <p className="mt-0.5 text-xs text-[#7a7666]">
                    Your key is stored locally in your browser and sent only to the PersonaPreparation backend when you run research.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowSettings(false)}
                className="flex h-7 w-7 items-center justify-center rounded-full text-[#7a7666] transition hover:bg-[#1c1915]/5 hover:text-[#1c1915]"
                aria-label="Close settings"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-5 flex items-center gap-3">
              <div className="relative flex-1">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setKeySaved(false);
                  }}
                  placeholder="sk-ant-api03-..."
                  className="h-11 w-full rounded-2xl border border-[#1a1814]/20 bg-white/90 pl-5 pr-12 font-mono text-sm text-[#1c1915] shadow-inner placeholder:text-[#a09b90] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1c1915]/15"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  onClick={() => setShowKey((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-[#7a7666] transition hover:text-[#1c1915]"
                  aria-label={showKey ? "Hide key" : "Show key"}
                >
                  {showKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>

              <Button
                type="button"
                onClick={handleSaveKey}
                disabled={!apiKey.trim() || keySaved}
                className="h-11 px-6"
                size="sm"
              >
                {keySaved ? "Saved" : "Save"}
              </Button>

              {keySaved && (
                <button
                  type="button"
                  onClick={handleClearKey}
                  className="text-xs font-medium text-[#7a7666] underline decoration-[#7a7666]/30 underline-offset-2 transition hover:text-red-600 hover:decoration-red-400"
                >
                  Clear
                </button>
              )}
            </div>

            {keySaved && (
              <div className="mt-3 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <p className="text-xs font-medium text-emerald-700">
                  Key active &mdash; {maskedKey}
                </p>
              </div>
            )}

            {!keySaved && !apiKey && (
              <p className="mt-3 text-xs text-[#9a9589]">
                Get your key from{" "}
                <span className="font-medium text-[#5a574f]">
                  console.anthropic.com
                </span>
              </p>
            )}
          </div>
        </div>

        <section className="space-y-5 pb-10 text-center sm:text-left">
          <p className="text-sm uppercase tracking-[0.4em] text-[#7a7666]">
            AI Meeting Intelligence
          </p>
          <h1 className="font-serif text-4xl font-semibold leading-tight text-[#14120f] sm:text-5xl">
            Never walk into a meeting unprepared again
          </h1>
          <p className="text-lg text-[#3b382f] sm:text-xl">
            PersonaPreparation researches any person in sixty seconds-
            distilling roles, priorities, and personalized conversation starters
            so you can own the room, not the prep.
          </p>
        </section>

        <section className="flex flex-col gap-6">
          <form
            onSubmit={handleSubmit}
            className="space-y-6 rounded-[32px] border border-[#dcd8cd] bg-white/90 p-8 shadow-panel"
          >
            <div className="space-y-3">
              <Label htmlFor="person-name">Type person name</Label>
              <Input
                id="person-name"
                placeholder="e.g. Abdul Hannan Chowdhury, VC at NSU"
                value={personName}
                onChange={(event) => setPersonName(event.target.value)}
              />
            </div>
            <div className="space-y-3">
              <Label htmlFor="meeting-context">
                Person background &amp; why you&apos;re meeting
              </Label>
              <Textarea
                id="meeting-context"
                rows={4}
                placeholder="Pitch review, exploring partnership, interviewing candidate..."
                value={context}
                onChange={(event) => setContext(event.target.value)}
              />
            </div>
            <Button type="submit" disabled={formDisabled} className="w-full">
              {isLoading ? "Researching..." : "Generate Meeting Brief"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <p className="text-xs text-[#6a675c]">
              We scan trusted public sources only. No scraping of private data
              or inboxes.
            </p>
          </form>

          {hasDisambiguationChoices ? (
            <section className="rounded-[28px] border border-[#dcd8cd] bg-white/90 p-5 shadow-panel">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#7a7666]">
                Identity Check
              </p>
              {candidateNote ? (
                <p className="mt-2 text-sm text-[#3b382f]">{candidateNote}</p>
              ) : null}

              {candidates.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {candidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className="rounded-xl border border-[#e5e0d4] bg-[#fbfaf5] p-4"
                    >
                      <p className="font-semibold text-[#1f1d18]">{candidate.name}</p>
                      <p className="text-sm text-[#4d4a43]">
                        {[candidate.title, candidate.organization]
                          .filter(Boolean)
                          .join(" at ") || "Role unknown"}
                      </p>
                      {candidate.summary ? (
                        <p className="mt-1 text-sm text-[#5b584f]">{candidate.summary}</p>
                      ) : null}
                      {candidate.profile_url ? (
                        <p className="mt-1 break-all text-xs text-[#6a675c]">
                          {candidate.profile_url}
                        </p>
                      ) : null}
                      <div className="mt-3">
                        <Button
                          type="button"
                          onClick={() => handleCandidateSelect(candidate)}
                          className="h-8 px-3 text-xs"
                        >
                          Select this person
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="mt-4">
                <Button type="button" variant="outline" onClick={handleContinueAnyway}>
                  Continue anyway
                </Button>
              </div>
            </section>
          ) : null}

          <section className="rounded-[40px] border border-[#dcd8cd] bg-white/85 p-6 shadow-panel">
            <p className="text-sm font-medium uppercase tracking-[0.4em] text-[#7a7666]">
              Instant output
            </p>

            {isLoading && (
              <div className="mt-4 rounded-[28px] border border-[#e5e0d4] bg-gradient-to-br from-white to-[#f7f5ee] p-6 shadow-inner">
                <div className="mb-4 flex items-center gap-3">
                  <Loader2 className="h-5 w-5 animate-spin text-[#7a7666]" />
                  <p className="text-base font-medium text-[#1f1d18]">
                    {currentStatus}
                  </p>
                </div>

                {activityLog.length > 0 && (
                  <div className="mt-4 max-h-[200px] space-y-2 overflow-y-auto">
                    {activityLog.map((activity, index) => (
                      <div
                        key={index}
                        className="animate-in slide-in-from-left-2 fade-in flex items-start gap-2 text-sm text-[#4d4a43] duration-300"
                      >
                        <span className="mt-0.5 text-[#7a7666]">*</span>
                        <span>{activity}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!isLoading && (
              <div className="prose prose-sm prose-stone mt-4 h-[280px] max-w-none overflow-y-auto rounded-[28px] border border-[#e5e0d4] bg-gradient-to-br from-white to-[#f7f5ee] p-6 text-base leading-relaxed text-[#1f1d18] shadow-inner">
                <ReactMarkdown>{output}</ReactMarkdown>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-4 text-sm text-[#4d4a43]">
              <span className="rounded-full border border-[#d8d4c7] px-4 py-2 shadow-sm">
                Conversation starters
              </span>
              <span className="rounded-full border border-[#d8d4c7] px-4 py-2 shadow-sm">
                Talking points
              </span>
              <span className="rounded-full border border-[#d8d4c7] px-4 py-2 shadow-sm">
                What to do and what to avoid
              </span>
            </div>
          </section>
        </section>

        <section className="mt-12 flex flex-col items-center gap-5 rounded-[28px] border border-[#d8d4c7] bg-white/80 px-8 py-6 text-center shadow-panel">
          <p className="text-sm uppercase tracking-[0.4em] text-[#7a7666]">
            Why teams love us
          </p>
          <p className="max-w-3xl text-base text-[#3a382f]">
            Get to know anyone in minutes, not hours. Sales, recruiting, and
            founder teams use PersonaPreparation to research people fast, no
            more juggling dozens of browser tabs. Connect our API and every
            brief is automatically saved and ready to add to your CRM.
          </p>
        </section>
      </div>
    </main>
  );
}
