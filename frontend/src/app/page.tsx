"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ClipboardCopy,
  Download,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Loader2,
  RotateCcw,
  Search,
  Brain,
  X,
  ChevronLeft,
  Clock,
  Trash2,
  RefreshCw,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  deleteHistoryItem,
  disambiguatePerson,
  exportBriefPDF,
  generateBriefStream,
  getHistory,
  getHistoryItem,
  type AgentEvent,
  type HistoryItem,
  type IdentityCandidate,
  type SelectedIdentity,
} from "@/lib/api";

const STORAGE_KEY = "persona_anthropic_api_key";

type AppState = "input" | "disambiguation" | "researching" | "result" | "history";

const getToolIcon = (toolName: string) => {
  if (toolName === "tavily_search" || toolName === "brave_search") return "search";
  if (toolName === "firecrawl_scrape") return "globe";
  return "brain";
};

const getToolLabel = (toolName: string) => {
  if (toolName === "tavily_search") return "Searching with Tavily";
  if (toolName === "brave_search") return "Searching with Brave";
  if (toolName === "firecrawl_scrape") return "Scraping webpage";
  return toolName;
};

/* ──────────────────────── Progress Ring SVG ──────────────────────── */

function ProgressRing({ iteration, max = 15 }: { iteration: number; max?: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(iteration / max, 1);
  const offset = circumference * (1 - progress);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" viewBox="0 0 120 120" className="-rotate-90">
        {/* Track */}
        <circle
          cx="60" cy="60" r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth="4"
        />
        {/* Fill */}
        <circle
          cx="60" cy="60" r={radius}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
          style={{ filter: "drop-shadow(0 0 6px rgba(232, 200, 114, 0.4))" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-serif text-[var(--accent)]">{iteration}</span>
        <span className="text-xs text-[var(--text-tertiary)]">/ {max}</span>
      </div>
    </div>
  );
}

/* ──────────────────────── Main Page ──────────────────────── */

export default function LandingPage() {
  const [appState, setAppState] = useState<AppState>("input");
  const [personName, setPersonName] = useState("");
  const [context, setContext] = useState("");
  const [output, setOutput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentStatus, setCurrentStatus] = useState("");
  const [activityLog, setActivityLog] = useState<{ text: string; icon: string }[]>([]);
  const [currentIteration, setCurrentIteration] = useState(0);
  const [candidates, setCandidates] = useState<IdentityCandidate[]>([]);
  const [candidateNote, setCandidateNote] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);

  // History tab state
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [pendingIdentity, setPendingIdentity] = useState<SelectedIdentity | null>(null);

  // API key state
  const [apiKey, setApiKey] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [keySaved, setKeySaved] = useState(false);

  const activityEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    activityEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activityLog]);

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
    setCurrentIteration(0);
    setCurrentStatus("Starting research...");
    setAppState("researching");

    await generateBriefStream(
      personName,
      context,
      (event: AgentEvent) => {
        if (event.iteration) setCurrentIteration(event.iteration);

        if (event.event_type === "start") {
          setCurrentStatus(`Researching ${event.data.person_name}...`);
          setActivityLog((prev) => [
            ...prev,
            { text: `Started research for ${event.data.person_name}`, icon: "brain" },
          ]);
        } else if (event.event_type === "thinking") {
          setCurrentStatus(event.data.message || "Processing...");
        } else if (event.event_type === "tool_call") {
          const toolLabel = getToolLabel(event.data.tool_name);
          const icon = getToolIcon(event.data.tool_name);
          setCurrentStatus(`${toolLabel}...`);

          let searchQuery = "";
          if (event.data.tool_input?.query) {
            searchQuery = `: "${event.data.tool_input.query}"`;
          } else if (event.data.tool_input?.url) {
            searchQuery = `: ${event.data.tool_input.url}`;
          }

          setActivityLog((prev) => [...prev, { text: `${toolLabel}${searchQuery}`, icon }]);
        } else if (event.event_type === "tool_result") {
          const summary = event.data.result_summary;
          if (summary?.success) {
            setActivityLog((prev) => [...prev, { text: summary.message, icon: "check" }]);
          } else if (summary?.error) {
            setActivityLog((prev) => [...prev, { text: summary.error, icon: "error" }]);
          }
        }
      },
      (brief: string) => {
        setCurrentStatus("Research complete!");
        setOutput(brief);
        setCandidates([]);
        setCandidateNote("");
        setIsLoading(false);
        setAppState("result");
      },
      (error: string) => {
        setCurrentStatus("Error occurred");
        setOutput(`Error: ${error}`);
        setIsLoading(false);
        setAppState("result");
      },
      { selectedIdentity, continueAnyway, anthropicApiKey: currentApiKey, forceRefresh }
    );
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setOutput("");
    setActivityLog([]);
    setCandidates([]);
    setCandidateNote("");
    setSelectedCandidateId(null);
    setCurrentStatus("Checking identity...");

    try {
      // If the user came from "Research fresh" in history, skip disambiguation —
      // we already know who they meant. Clear the pending identity after using it.
      if (pendingIdentity) {
        const identityToUse = pendingIdentity;
        setPendingIdentity(null);
        await startStreamingResearch(identityToUse, false);
        return;
      }

      const disambiguation = await disambiguatePerson(personName, context, currentApiKey, forceRefresh);

      if (disambiguation.status === "ambiguous" && disambiguation.candidates.length > 0) {
        setCandidates(disambiguation.candidates);
        setCandidateNote(disambiguation.recommendation);
        setCurrentStatus("");
        setIsLoading(false);
        setAppState("disambiguation");
        return;
      }

      if (disambiguation.status === "no_match") {
        setCandidates([]);
        setCandidateNote(disambiguation.recommendation);
        setCurrentStatus("");
        setIsLoading(false);
        setAppState("disambiguation");
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
      setAppState("result");
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
      setAppState("result");
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
      setAppState("result");
    }
  };

  const handleNewResearch = () => {
    setAppState("input");
    setOutput("");
    setActivityLog([]);
    setCandidates([]);
    setCandidateNote("");
    setCurrentStatus("");
    setCurrentIteration(0);
    setSelectedCandidateId(null);
    setCopied(false);
    setForceRefresh(false);
    setPendingIdentity(null);
  };

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const result = await getHistory(50, 0);
      setHistoryItems(result.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load history.";
      setHistoryError(message);
      setHistoryItems([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleOpenHistoryTab = async () => {
    setAppState("history");
    await loadHistory();
  };

  const handleOpenHistoryItem = async (item: HistoryItem) => {
    try {
      const full = item.brief ? item : await getHistoryItem(item.id);
      if (!full.brief) {
        throw new Error("Saved brief is empty.");
      }
      setPersonName(full.person_name);
      setContext(full.meeting_context || "");
      setOutput(full.brief);
      setActivityLog([]);
      setCurrentStatus("");
      setCurrentIteration(0);
      setCandidates([]);
      setCandidateNote("");
      setSelectedCandidateId(null);
      setAppState("result");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not open saved brief.";
      setHistoryError(message);
    }
  };

  const handleDeleteHistoryItem = async (id: number) => {
    try {
      await deleteHistoryItem(id);
      setHistoryItems((prev) => prev.filter((item) => item.id !== id));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to delete saved brief.";
      setHistoryError(message);
    }
  };

  const handleResearchFreshFromHistory = (item: HistoryItem) => {
    setPersonName(item.person_name);
    setContext(item.meeting_context || "");
    setForceRefresh(true);
    setPendingIdentity(item.selected_identity ?? null);
    setOutput("");
    setActivityLog([]);
    setCandidates([]);
    setCandidateNote("");
    setSelectedCandidateId(null);
    setHistoryError("");
    setAppState("input");
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPDF = async () => {
    setPdfDownloading(true);
    try {
      const { blob, filename } = await exportBriefPDF(output, personName);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("PDF download failed:", error);
    } finally {
      setPdfDownloading(false);
    }
  };

  const maskedKey = apiKey
    ? `${apiKey.slice(0, 7)}${"*".repeat(Math.max(0, apiKey.length - 11))}${apiKey.slice(-4)}`
    : "";

  const ActivityIcon = ({ icon }: { icon: string }) => {
    if (icon === "search") return <Search className="h-3.5 w-3.5 text-[var(--accent)]" />;
    if (icon === "globe") return <Globe className="h-3.5 w-3.5 text-[var(--accent)]" />;
    if (icon === "check") return <Check className="h-3.5 w-3.5 text-[var(--success)]" />;
    if (icon === "error") return <X className="h-3.5 w-3.5 text-[var(--error)]" />;
    return <Brain className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />;
  };

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden bg-[var(--bg-primary)]">
      {/* Gradient mesh background */}
      <div className="pointer-events-none fixed inset-0" aria-hidden>
        <div className="absolute -left-1/4 -top-1/4 h-[600px] w-[600px] rounded-full bg-[radial-gradient(circle,rgba(232,200,114,0.04),transparent_70%)]" />
        <div className="absolute -bottom-1/4 -right-1/4 h-[500px] w-[500px] rounded-full bg-[radial-gradient(circle,rgba(232,200,114,0.03),transparent_70%)]" />
      </div>

      {/* ─── Header ─── */}
      <header className="relative z-20 flex shrink-0 items-center justify-between px-6 pb-4 pt-6 sm:px-12 sm:pb-5 sm:pt-10 lg:px-16 lg:pt-12">
        <button
          type="button"
          onClick={handleNewResearch}
          className="text-base font-medium tracking-[0.08em] text-[var(--text-primary)] transition-colors hover:text-[var(--accent)]"
        >
          Persona<span className="text-[var(--accent)]">Prep</span>
        </button>

        <div className="flex items-center gap-3">
          {appState !== "history" && (
            <button
              type="button"
              onClick={handleOpenHistoryTab}
              className="flex items-center gap-1.5 rounded-full border border-[var(--border)] px-4 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)]"
            >
              <Clock className="h-3 w-3" />
              History
            </button>
          )}
          {appState !== "input" && (
            <button
              type="button"
              onClick={handleNewResearch}
              className="flex items-center gap-1.5 rounded-full border border-[var(--border)] px-4 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)]"
            >
              <RotateCcw className="h-3 w-3" />
              New
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowSettings((prev) => !prev)}
            className={`relative flex h-9 w-9 items-center justify-center rounded-full border transition-all duration-200 ${
              showSettings
                ? "border-[var(--accent)]/40 bg-[var(--accent-dim)] text-[var(--accent)]"
                : keySaved
                  ? "border-[var(--success)]/30 bg-[var(--success)]/5 text-[var(--success)]"
                  : "border-[var(--border)] text-[var(--text-tertiary)] hover:border-[var(--border-hover)] hover:text-[var(--text-secondary)]"
            }`}
            aria-label="API Settings"
          >
            <KeyRound className="h-4 w-4" />
            {keySaved && !showSettings && (
              <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-[var(--success)]" />
            )}
          </button>
        </div>
      </header>

      {/* ─── API Key Settings Dropdown ─── */}
      <div
        className={`relative z-20 shrink-0 overflow-hidden transition-all duration-400 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          showSettings ? "max-h-[260px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="mx-6 mb-6 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 sm:mx-10">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent-dim)] text-[var(--accent)]">
                <KeyRound className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-[var(--text-primary)]">Anthropic API Key</h3>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  Your key is stored locally in your browser and sent only to the PersonaPreparation backend when you run research.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowSettings(false)}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-tertiary)] transition hover:bg-white/5 hover:text-[var(--text-secondary)]"
              aria-label="Close settings"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <div className="relative flex-1">
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setKeySaved(false); }}
                placeholder="sk-ant-api03-..."
                className="h-10 w-full rounded-xl border border-[var(--border)] bg-[var(--bg-input)] pl-4 pr-10 font-mono text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:border-[var(--accent)]/40"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowKey((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] transition hover:text-[var(--text-secondary)]"
                aria-label={showKey ? "Hide key" : "Show key"}
              >
                {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <Button type="button" onClick={handleSaveKey} disabled={!apiKey.trim() || keySaved} size="sm">
              {keySaved ? "Saved" : "Save"}
            </Button>
            {keySaved && (
              <button
                type="button"
                onClick={handleClearKey}
                className="text-xs text-[var(--text-tertiary)] underline underline-offset-2 transition hover:text-[var(--error)]"
              >
                Clear
              </button>
            )}
          </div>

          {keySaved && (
            <div className="mt-3 flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
              <p className="text-xs text-[var(--success)]">Key active &mdash; {maskedKey}</p>
            </div>
          )}
          {!keySaved && !apiKey && (
            <p className="mt-3 text-xs text-[var(--text-tertiary)]">
              Get your key from <span className="text-[var(--text-secondary)]">console.anthropic.com</span>
            </p>
          )}
        </div>
      </div>

      {/* ─── State Container (fills remaining viewport) ─── */}
      <div className="relative z-10 min-h-0 flex-1">

      {/* ═══════════════════════ STATE: INPUT ═══════════════════════ */}
      <div
        className={`absolute inset-0 flex flex-col items-center justify-center px-6 transition-all duration-500 ${
          appState === "input" ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none -translate-y-8 opacity-0"
        }`}
      >
        <div className="w-full max-w-xl stagger-children">
          <div className="mb-10 text-center animate-fade-up" style={{ animationFillMode: "both" }}>
            <h1 className="font-serif text-5xl leading-[1.1] text-[var(--text-primary)] sm:text-6xl">
              Never meet a<br />
              <span className="italic text-[var(--accent)]">stranger</span>
            </h1>
            <p className="mt-4 text-base text-[var(--text-secondary)]">
              AI-powered dossiers in 60 seconds. Know their priorities,<br className="hidden sm:block" />
              craft your talking points, own the room.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5 animate-fade-up" style={{ animationDelay: "150ms", animationFillMode: "both" }}>
            <div className="space-y-2">
              <Label htmlFor="person-name">Who are you meeting?</Label>
              <Input
                id="person-name"
                placeholder="e.g. Abdul Hannan Chowdhury, VC at NSU"
                value={personName}
                onChange={(event) => {
                  setPersonName(event.target.value);
                  // Editing the name means the saved identity from "Re-run" no
                  // longer applies — drop it so we go through disambiguation again.
                  if (pendingIdentity) setPendingIdentity(null);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="meeting-context">Context</Label>
              <Textarea
                id="meeting-context"
                rows={3}
                placeholder="Pitch review, exploring partnership, interviewing candidate..."
                value={context}
                onChange={(event) => {
                  setContext(event.target.value);
                  if (pendingIdentity) setPendingIdentity(null);
                }}
              />
            </div>
            <Button type="submit" disabled={formDisabled} className="w-full">
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking...
                </>
              ) : (
                <>
                  Prepare Briefing
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
            <label className="flex cursor-pointer items-center justify-center gap-2 text-xs text-[var(--text-tertiary)] transition hover:text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={forceRefresh}
                onChange={(e) => setForceRefresh(e.target.checked)}
                className="h-3.5 w-3.5 cursor-pointer accent-[var(--accent)]"
              />
              Force fresh research (skip cache)
            </label>
            <p className="text-center text-xs text-[var(--text-tertiary)]">
              Scans trusted public sources only. No private data or inboxes.
            </p>
          </form>
        </div>
      </div>

      {/* ═══════════════════════ STATE: DISAMBIGUATION ═══════════════════════ */}
      <div
        className={`absolute inset-0 flex flex-col items-center overflow-y-auto px-6 pb-12 pt-8 transition-all duration-500 ${
          appState === "disambiguation" ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none translate-y-8 opacity-0"
        }`}
      >
        <div className="w-full max-w-xl">
          <button
            type="button"
            onClick={handleNewResearch}
            className="mb-6 flex items-center gap-1.5 text-sm text-[var(--text-tertiary)] transition hover:text-[var(--text-secondary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </button>

          <div className="mb-6">
            <h2 className="font-serif text-2xl text-[var(--text-primary)]">
              We found multiple people matching
            </h2>
            <p className="mt-1 font-serif text-2xl italic text-[var(--accent)]">
              &ldquo;{personName}&rdquo;
            </p>
            {candidateNote && (
              <p className="mt-3 text-sm text-[var(--text-secondary)]">{candidateNote}</p>
            )}
          </div>

          {candidates.length > 0 && (
            <div className="space-y-1 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] overflow-hidden">
              {candidates.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => setSelectedCandidateId(
                    selectedCandidateId === candidate.id ? null : candidate.id
                  )}
                  className={`flex w-full items-start gap-4 p-4 text-left transition-all duration-200 ${
                    selectedCandidateId === candidate.id
                      ? "border-l-2 border-l-[var(--accent)] bg-[var(--accent-dim)]"
                      : "border-l-2 border-l-transparent hover:bg-white/[0.02]"
                  }`}
                >
                  <div
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all ${
                      selectedCandidateId === candidate.id
                        ? "border-[var(--accent)] bg-[var(--accent)]"
                        : "border-[var(--border-hover)]"
                    }`}
                  >
                    {selectedCandidateId === candidate.id && (
                      <Check className="h-3 w-3 text-[var(--bg-primary)]" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-[var(--text-primary)]">{candidate.name}</p>
                    <p className="text-sm text-[var(--text-secondary)]">
                      {[candidate.title, candidate.organization].filter(Boolean).join(" at ") || "Role unknown"}
                    </p>
                    {candidate.summary && (
                      <p className="mt-1 text-sm text-[var(--text-tertiary)]">{candidate.summary}</p>
                    )}
                    {candidate.profile_url && (
                      <p className="mt-1 truncate text-xs text-[var(--accent)] opacity-60">{candidate.profile_url}</p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="mt-5 flex gap-3">
            {selectedCandidateId && (
              <Button
                type="button"
                onClick={() => {
                  const c = candidates.find((c) => c.id === selectedCandidateId);
                  if (c) handleCandidateSelect(c);
                }}
                className="flex-1"
              >
                Confirm &amp; Research
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
            <Button type="button" variant="outline" onClick={handleContinueAnyway} className={selectedCandidateId ? "" : "flex-1"}>
              Skip &mdash; research without selecting
            </Button>
          </div>
        </div>
      </div>

      {/* ═══════════════════════ STATE: RESEARCHING ═══════════════════════ */}
      <div
        className={`absolute inset-0 flex flex-col items-center justify-center px-6 transition-all duration-500 ${
          appState === "researching" ? "pointer-events-auto scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0"
        }`}
      >
        <div className="flex w-full max-w-lg flex-col items-center overflow-hidden">
          <div className="shrink-0">
            <ProgressRing iteration={currentIteration} />
          </div>

          <p className="mt-4 shrink-0 text-center text-lg text-[var(--text-primary)]">{currentStatus}</p>
          <p className="mt-1 shrink-0 text-center text-sm text-[var(--text-tertiary)]">
            Researching <span className="text-[var(--text-secondary)]">{personName}</span>
          </p>

          {/* Activity Feed */}
          {activityLog.length > 0 && (
            <div className="mt-6 w-full min-h-0 flex-1 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.15em] text-[var(--text-tertiary)]">
                Live Activity
              </p>
              <div className="max-h-[200px] space-y-2 overflow-y-auto pr-1">
                {activityLog.map((item, index) => (
                  <div
                    key={index}
                    className="animate-slide-in-right flex items-start gap-2.5 text-sm"
                    style={{ animationDelay: `${index * 30}ms`, animationFillMode: "both" }}
                  >
                    <span className="mt-0.5 shrink-0">
                      <ActivityIcon icon={item.icon} />
                    </span>
                    <span className="font-mono text-xs leading-relaxed text-[var(--text-secondary)]">
                      {item.text}
                    </span>
                  </div>
                ))}
                <div ref={activityEndRef} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ═══════════════════════ STATE: RESULT ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-y-auto px-6 pb-12 pt-4 transition-all duration-500 ${
          appState === "result" ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none translate-y-8 opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-3xl">
          {/* Dossier Header */}
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--text-tertiary)]">
                Briefing
              </p>
              <h2 className="font-serif text-2xl text-[var(--text-primary)]">{personName}</h2>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)]"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-[var(--success)]" /> : <ClipboardCopy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={handleDownloadPDF}
                disabled={pdfDownloading}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
              >
                {pdfDownloading
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <Download className="h-3.5 w-3.5" />}
                {pdfDownloading ? "Generating…" : "PDF"}
              </button>
              <button
                type="button"
                onClick={handleNewResearch}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)]"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                New
              </button>
            </div>
          </div>

          {/* Dossier Body */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-panel sm:p-8">
            <div className="prose prose-sm prose-dossier max-w-none text-base leading-relaxed">
              <ReactMarkdown>{output}</ReactMarkdown>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════ STATE: HISTORY ═══════════════════════ */}
      <div
        className={`absolute inset-0 flex flex-col items-center overflow-y-auto px-6 pb-12 pt-8 transition-all duration-500 ${
          appState === "history" ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none translate-y-8 opacity-0"
        }`}
      >
        <div className="w-full max-w-2xl">
          <button
            type="button"
            onClick={handleNewResearch}
            className="mb-6 flex items-center gap-1.5 text-sm text-[var(--text-tertiary)] transition hover:text-[var(--text-secondary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </button>

          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <h2 className="font-serif text-3xl text-[var(--text-primary)]">Saved briefs</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Every brief you generate is kept here until you delete it.
              </p>
            </div>
            <button
              type="button"
              onClick={loadHistory}
              disabled={historyLoading}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
            >
              {historyLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Refresh
            </button>
          </div>

          {historyError && (
            <div className="mb-4 rounded-lg border border-[var(--error)]/30 bg-[var(--error)]/5 px-4 py-3 text-sm text-[var(--error)]">
              {historyError}
            </div>
          )}

          {historyLoading && historyItems.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-sm text-[var(--text-tertiary)]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading saved briefs…
            </div>
          ) : historyItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--border)] py-16 text-center text-sm text-[var(--text-tertiary)]">
              No saved briefs yet. Generate one and it&apos;ll appear here.
            </div>
          ) : (
            <ul className="space-y-3">
              {historyItems.map((item) => {
                const created = new Date(item.created_at * 1000);
                const dateLabel = created.toLocaleString(undefined, {
                  year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                });
                return (
                  <li
                    key={item.id}
                    className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 transition hover:border-[var(--border-hover)]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-[var(--text-primary)]">{item.person_name}</p>
                        {item.meeting_context && (
                          <p className="mt-0.5 line-clamp-2 text-sm text-[var(--text-secondary)]">
                            {item.meeting_context}
                          </p>
                        )}
                        <p className="mt-1 text-xs text-[var(--text-tertiary)]">{dateLabel}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleOpenHistoryItem(item)}
                          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResearchFreshFromHistory(item)}
                          className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-all hover:border-[var(--border-hover)] hover:text-[var(--text-primary)]"
                          title="Prefill the form with this person + context and check 'Force fresh research'"
                        >
                          <RefreshCw className="h-3 w-3" />
                          Re-run
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteHistoryItem(item.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-tertiary)] transition hover:bg-[var(--error)]/10 hover:text-[var(--error)]"
                          aria-label="Delete saved brief"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      </div>{/* end state container */}
    </div>
  );
}
