"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ClipboardCopy,
  Download,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  RotateCcw,
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
  parseBriefSources,
  type AgentEvent,
  type HistoryItem,
  type IdentityCandidate,
  type SelectedIdentity,
} from "@/lib/api";

const STORAGE_KEY = "persona_anthropic_api_key";

type AppState = "input" | "disambiguation" | "researching" | "result" | "history";

const CHAPTER: Record<AppState, { num: string; title: string }> = {
  input:          { num: "01", title: "SUBJECT" },
  disambiguation: { num: "02", title: "IDENTITY" },
  researching:    { num: "03", title: "RESEARCH" },
  result:         { num: "04", title: "BRIEFING" },
  history:        { num: "—",  title: "ARCHIVE" },
};

const getToolLabel = (toolName: string) => {
  if (toolName === "tavily_search") return "tavily.search";
  if (toolName === "brave_search") return "brave.search";
  if (toolName === "firecrawl_scrape") return "firecrawl.scrape";
  return toolName;
};

const formatElapsed = (ms: number) => {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
};

const formatDateStamp = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y} · ${m} · ${day}`;
};

/* ──────────────────────── Chapter eyebrow ──────────────────────── */

function ChapterMark({ state }: { state: AppState }) {
  const { num, title } = CHAPTER[state];
  return (
    <div className="flex items-baseline gap-3 select-none">
      <span className="chapter-num text-[15px]">{num}</span>
      <span className="h-px w-6 bg-[var(--rule-strong)]" />
      <span className="eyebrow">{title}</span>
    </div>
  );
}

/* ──────────────────────── Confidence bar ──────────────────────── */

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-[3px] w-20 bg-[var(--rule)]">
        <div
          className="absolute inset-y-0 left-0 bg-[var(--text-primary)]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[10px] tabular-nums text-[var(--text-tertiary)]">
        {Math.round(pct)}
      </span>
    </div>
  );
}

/* ──────────────────────── Page ──────────────────────── */

export default function LandingPage() {
  const [appState, setAppState] = useState<AppState>("input");
  const [personName, setPersonName] = useState("");
  const [context, setContext] = useState("");
  const [output, setOutput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentStatus, setCurrentStatus] = useState("");
  const [activityLog, setActivityLog] = useState<{ text: string; tool: string; kind: "call" | "result" | "info" | "error"; ts: number }[]>([]);
  const [currentIteration, setCurrentIteration] = useState(0);
  const [maxIteration] = useState(15);
  const [candidates, setCandidates] = useState<IdentityCandidate[]>([]);
  const [candidateNote, setCandidateNote] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [researchStartedAt, setResearchStartedAt] = useState<number | null>(null);
  const [researchFinishedAt, setResearchFinishedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());

  // History
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [pendingIdentity, setPendingIdentity] = useState<SelectedIdentity | null>(null);

  // API key
  const [apiKey, setApiKey] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [keySaved, setKeySaved] = useState(false);

  const activityEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    activityEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activityLog]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setApiKey(stored);
      setKeySaved(true);
    }
  }, []);

  // Tick a clock while researching for the elapsed counter
  useEffect(() => {
    if (appState !== "researching") return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [appState]);

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

  const elapsed = researchStartedAt
    ? (researchFinishedAt ?? now) - researchStartedAt
    : 0;

  const startStreamingResearch = async (
    selectedIdentity?: SelectedIdentity,
    continueAnyway = false
  ) => {
    setIsLoading(true);
    setActivityLog([]);
    setCurrentIteration(0);
    setCurrentStatus("Initializing research…");
    setResearchStartedAt(Date.now());
    setResearchFinishedAt(null);
    setAppState("researching");

    const pushLog = (text: string, tool: string, kind: "call" | "result" | "info" | "error") =>
      setActivityLog((prev) => [...prev, { text, tool, kind, ts: Date.now() }]);

    await generateBriefStream(
      personName,
      context,
      (event: AgentEvent) => {
        if (event.iteration) setCurrentIteration(event.iteration);

        if (event.event_type === "start") {
          setCurrentStatus(`Researching ${event.data.person_name}`);
          pushLog(`session.start — ${event.data.person_name}`, "system", "info");
        } else if (event.event_type === "thinking") {
          setCurrentStatus(event.data.message || "Thinking…");
        } else if (event.event_type === "tool_call") {
          const toolLabel = getToolLabel(event.data.tool_name);
          setCurrentStatus(`${toolLabel}`);

          let detail = "";
          if (event.data.tool_input?.query) detail = `"${event.data.tool_input.query}"`;
          else if (event.data.tool_input?.url) detail = event.data.tool_input.url;

          pushLog(detail, toolLabel, "call");
        } else if (event.event_type === "tool_result") {
          const summary = event.data.result_summary;
          const toolLabel = getToolLabel(event.data.tool_name || "");
          if (summary?.success) pushLog(summary.message, toolLabel, "result");
          else if (summary?.error) pushLog(summary.error, toolLabel, "error");
        }
      },
      (brief: string) => {
        setCurrentStatus("Research complete");
        setOutput(brief);
        setCandidates([]);
        setCandidateNote("");
        setIsLoading(false);
        setResearchFinishedAt(Date.now());
        setAppState("result");
      },
      (error: string) => {
        setCurrentStatus("Error");
        setOutput(`Error: ${error}`);
        setIsLoading(false);
        setResearchFinishedAt(Date.now());
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
    setCurrentStatus("Resolving identity…");

    try {
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
        error instanceof Error ? error.message : "Something went wrong while researching.";
      setOutput(`Error: ${message}`);
      setCurrentStatus("");
      setIsLoading(false);
      setAppState("result");
    }
  };

  const handleCandidateSelect = async (candidate: IdentityCandidate) => {
    setOutput("");
    setCandidateNote(`Selected · ${candidate.name}`);
    setCandidates([]);

    try {
      await startStreamingResearch(candidate, false);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Something went wrong while researching.";
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
        error instanceof Error ? error.message : "Something went wrong while researching.";
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
    setResearchStartedAt(null);
    setResearchFinishedAt(null);
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
      if (!full.brief) throw new Error("Saved brief is empty.");
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

  const sourceCount = activityLog.filter((l) => l.kind === "result").length;

  const parsedBrief = useMemo(() => parseBriefSources(output), [output]);
  const citedSourceCount = parsedBrief.sources.length;

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden bg-[var(--bg-primary)]">
      {/* ─────────── Header ─────────── */}
      <header className="relative z-20 shrink-0 border-b border-[var(--rule)]">
        <div className="flex items-center justify-between px-6 py-4 sm:px-10 lg:px-14">
          <button
            type="button"
            onClick={handleNewResearch}
            className="group flex items-baseline gap-2 text-left"
            aria-label="PersonaPrep — start over"
          >
            <span className="font-serif-display text-[22px] leading-none">
              Persona<span className="italic text-[var(--accent)]">Prep</span>
            </span>
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--text-tertiary)] sm:inline">
              Meeting Intelligence · v1
            </span>
          </button>

          <div className="flex items-center gap-2">
            {appState !== "history" && (
              <button
                type="button"
                onClick={handleOpenHistoryTab}
                className="btn-ghost"
              >
                <Clock className="h-3 w-3" />
                Archive
              </button>
            )}
            {appState !== "input" && (
              <button
                type="button"
                onClick={handleNewResearch}
                className="btn-ghost"
              >
                <RotateCcw className="h-3 w-3" />
                New
              </button>
            )}
            <span className="mx-1 h-4 w-px bg-[var(--rule)]" />
            <button
              type="button"
              onClick={() => setShowSettings((p) => !p)}
              className={`relative flex h-8 w-8 items-center justify-center rounded-[2px] border transition-colors ${
                showSettings
                  ? "border-[var(--accent)] bg-[var(--accent-dim)] text-[var(--accent)]"
                  : keySaved
                    ? "border-[var(--rule-strong)] text-[var(--text-primary)]"
                    : "border-[var(--rule)] text-[var(--text-tertiary)] hover:border-[var(--rule-strong)] hover:text-[var(--text-primary)]"
              }`}
              aria-label="API key"
            >
              <KeyRound className="h-3.5 w-3.5" />
              {keySaved && !showSettings && (
                <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
              )}
            </button>
          </div>
        </div>

        {/* Chapter rule */}
        <div className="flex items-center justify-between border-t border-[var(--rule)] px-6 py-2.5 sm:px-10 lg:px-14">
          <ChapterMark state={appState} />
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
            {appState === "researching" && researchStartedAt ? (
              <span><span className="text-[var(--text-secondary)]">T+</span>{formatElapsed(elapsed)}</span>
            ) : appState === "result" && researchStartedAt && researchFinishedAt ? (
              <span>Compiled in {formatElapsed(researchFinishedAt - researchStartedAt)}</span>
            ) : (
              <span>{formatDateStamp(new Date())}</span>
            )}
          </div>
        </div>
      </header>

      {/* ─────────── API Key Drawer ─────────── */}
      <div
        className={`relative z-20 shrink-0 overflow-hidden border-b border-[var(--rule)] bg-[var(--bg-elevated)] transition-all duration-300 ${
          showSettings ? "max-h-[260px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-6 py-5 sm:px-10 lg:px-14">
          <div className="flex items-start justify-between gap-6">
            <div className="max-w-md">
              <p className="eyebrow">Anthropic Key</p>
              <p className="mt-2 font-serif-display text-[18px] leading-snug text-[var(--text-primary)]">
                Stored in your browser. Sent only to the PersonaPrep backend at request time.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowSettings(false)}
              className="flex h-7 w-7 items-center justify-center rounded-[2px] text-[var(--text-tertiary)] hover:bg-black/5 hover:text-[var(--text-primary)]"
              aria-label="Close"
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
                placeholder="sk-ant-api03-…"
                className="h-10 w-full rounded-none border-0 border-b border-[var(--rule-strong)] bg-transparent pl-0 pr-10 font-mono text-sm text-[var(--text-primary)] placeholder:text-[var(--text-quaternary)] focus-visible:outline-none focus-visible:border-[var(--accent)]"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowKey((p) => !p)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                aria-label={showKey ? "Hide" : "Show"}
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
                className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-tertiary)] hover:text-[var(--accent)]"
              >
                Clear
              </button>
            )}
          </div>

          {keySaved && (
            <p className="mt-3 font-mono text-[11px] text-[var(--text-tertiary)]">
              <span className="text-[var(--accent)]">●</span> active · {maskedKey}
            </p>
          )}
        </div>
      </div>

      {/* ─────────── State container ─────────── */}
      <div className="relative z-10 min-h-0 flex-1">

      {/* ═══════════════════════ INPUT ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-y-auto transition-opacity duration-400 ${
          appState === "input" ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto grid w-full max-w-6xl grid-cols-12 gap-8 px-6 py-12 sm:px-10 lg:px-14 lg:py-20">
          {/* Headline column */}
          <div className="col-span-12 lg:col-span-7 stagger-children">
            <p className="eyebrow animate-fade-up" style={{ animationFillMode: "both" }}>The Briefing</p>
            <h1
              className="mt-5 font-serif-display text-[64px] leading-[0.95] tracking-[-0.025em] text-[var(--text-primary)] sm:text-[88px] animate-fade-up"
              style={{ animationFillMode: "both" }}
            >
              Never meet
              <br />
              a <span className="italic text-[var(--accent)]">stranger</span>.
            </h1>
            <p
              className="mt-8 max-w-md font-serif-display text-[18px] leading-[1.55] text-[var(--text-secondary)] animate-fade-up"
              style={{ animationFillMode: "both" }}
            >
              Sixty seconds of editorial-grade research before you walk into the room.
              Their priorities, their record, their recent moves — distilled.
            </p>
            <div
              className="mt-10 flex items-center gap-4 animate-fade-up"
              style={{ animationFillMode: "both" }}
            >
              <span className="h-px w-12 bg-[var(--rule-strong)]" />
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                Public sources only
              </span>
            </div>
          </div>

          {/* Form column */}
          <div className="col-span-12 lg:col-span-5">
            <form
              onSubmit={handleSubmit}
              className="flex flex-col gap-7 border-l-0 lg:border-l lg:border-[var(--rule)] lg:pl-10 animate-fade-up"
              style={{ animationDelay: "180ms", animationFillMode: "both" }}
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="person-name">01 — Who</Label>
                <Input
                  id="person-name"
                  placeholder="Abdul Hannan Chowdhury, VC at NSU"
                  value={personName}
                  onChange={(event) => {
                    setPersonName(event.target.value);
                    if (pendingIdentity) setPendingIdentity(null);
                  }}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="meeting-context">02 — Context</Label>
                <Textarea
                  id="meeting-context"
                  rows={3}
                  placeholder="Pitch review, exploring partnership, interviewing candidate…"
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
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Resolving…
                  </>
                ) : (
                  <>
                    Prepare briefing
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>

              <label className="flex cursor-pointer items-center gap-2.5 self-start">
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                  className="h-3 w-3 cursor-pointer accent-[var(--accent)]"
                />
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
                  Bypass cache
                </span>
              </label>

              <p className="border-t border-[var(--rule)] pt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
                No private data · No inboxes · No surveillance
              </p>
            </form>
          </div>
        </div>
      </div>

      {/* ═══════════════════════ DISAMBIGUATION ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-y-auto transition-opacity duration-400 ${
          appState === "disambiguation" ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-4xl px-6 py-12 sm:px-10 lg:px-14">
          <button
            type="button"
            onClick={handleNewResearch}
            className="btn-ghost mb-8 -ml-3"
          >
            <ChevronLeft className="h-3 w-3" />
            Back
          </button>

          <div className="mb-10">
            <p className="eyebrow">Disambiguation</p>
            <h2 className="mt-3 font-serif-display text-[40px] leading-[1.05] text-[var(--text-primary)] sm:text-[52px]">
              Multiple subjects match
              <br />
              <span className="italic text-[var(--accent)]">&ldquo;{personName}&rdquo;</span>
            </h2>
            {candidateNote && (
              <p className="mt-5 max-w-2xl font-serif-display text-[17px] leading-relaxed text-[var(--text-secondary)]">
                {candidateNote}
              </p>
            )}
          </div>

          {candidates.length > 0 && (
            <div className="border-y border-[var(--rule-strong)]">
              {candidates.map((candidate, idx) => {
                const selected = selectedCandidateId === candidate.id;
                const num = String(idx + 1).padStart(2, "0");
                const conf = (candidate as IdentityCandidate & { confidence?: number }).confidence ?? 0;
                return (
                  <button
                    key={candidate.id}
                    type="button"
                    onClick={() =>
                      setSelectedCandidateId(selected ? null : candidate.id)
                    }
                    className={`group flex w-full items-start gap-6 border-t border-[var(--rule)] px-2 py-5 text-left transition-colors first:border-t-0 ${
                      selected ? "bg-[var(--accent-dim)]" : "hover:bg-black/[0.02]"
                    }`}
                  >
                    <div className="w-12 shrink-0 pt-1">
                      <span className={`font-mono text-[12px] tracking-[0.04em] ${selected ? "text-[var(--accent)]" : "text-[var(--text-tertiary)]"}`}>
                        {num}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-4">
                        <p className="font-serif-display text-[22px] leading-tight text-[var(--text-primary)]">
                          {candidate.name}
                        </p>
                        {conf > 0 && <ConfidenceBar value={conf} />}
                      </div>
                      <p className="mt-1.5 text-[15px] text-[var(--text-secondary)]">
                        {[candidate.title, candidate.organization].filter(Boolean).join(" · ") || "Role unknown"}
                      </p>
                      {candidate.summary && (
                        <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-[var(--text-tertiary)]">
                          {candidate.summary}
                        </p>
                      )}
                      {candidate.profile_url && (
                        <p className="mt-2 truncate font-mono text-[11px] text-[var(--accent)]/70">
                          {candidate.profile_url}
                        </p>
                      )}
                    </div>
                    <div className="w-6 shrink-0 pt-2 text-right">
                      {selected ? (
                        <Check className="ml-auto h-4 w-4 text-[var(--accent)]" />
                      ) : (
                        <span className="font-mono text-[12px] text-[var(--text-quaternary)] opacity-0 group-hover:opacity-100">→</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="mt-10 flex flex-wrap gap-3">
            {selectedCandidateId && (
              <Button
                type="button"
                onClick={() => {
                  const c = candidates.find((c) => c.id === selectedCandidateId);
                  if (c) handleCandidateSelect(c);
                }}
              >
                Confirm &amp; research
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
            <Button type="button" variant="outline" onClick={handleContinueAnyway}>
              Continue without selecting
            </Button>
          </div>
        </div>
      </div>

      {/* ═══════════════════════ RESEARCHING ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-hidden transition-opacity duration-400 ${
          appState === "researching" ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto grid h-full w-full max-w-6xl grid-cols-12 gap-0 px-6 py-10 sm:px-10 lg:px-14">
          {/* Left console */}
          <aside className="col-span-12 flex flex-col justify-between border-b border-[var(--rule)] pb-8 lg:col-span-5 lg:border-b-0 lg:border-r lg:border-[var(--rule)] lg:pb-0 lg:pr-10">
            <div>
              <p className="eyebrow">Subject</p>
              <p className="mt-3 font-serif-display text-[28px] leading-[1.1] text-[var(--text-primary)]">
                {personName}
              </p>
              {context && (
                <p className="mt-2 max-w-sm font-serif-display text-[15px] italic leading-snug text-[var(--text-secondary)]">
                  {context}
                </p>
              )}
            </div>

            <div className="mt-8 lg:mt-0">
              <div className="flex items-end justify-between border-b border-[var(--rule)] pb-3">
                <span className="eyebrow">Iteration</span>
                <span className="font-mono text-[11px] tabular-nums text-[var(--text-tertiary)]">
                  {String(currentIteration).padStart(2, "0")} / {maxIteration}
                </span>
              </div>

              <div className="mt-4 flex items-baseline gap-4">
                <span className="font-mono text-[88px] leading-none tabular-nums text-[var(--text-primary)] sm:text-[112px]">
                  {String(currentIteration).padStart(2, "0")}
                </span>
                <div className="flex flex-col">
                  <span className="font-mono text-[12px] tabular-nums text-[var(--text-tertiary)]">
                    of {maxIteration}
                  </span>
                  <span className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
                    Research depth
                  </span>
                </div>
              </div>

              {/* Segmented progress bar */}
              <div className="mt-5 flex gap-[3px]">
                {Array.from({ length: maxIteration }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-2 flex-1 transition-colors ${
                      i < currentIteration ? "bg-[var(--text-primary)]" : "bg-[var(--rule)]"
                    }`}
                  />
                ))}
              </div>

              <div className="mt-6 border-t border-[var(--rule)] pt-4">
                <p className="font-serif-display text-[17px] leading-snug text-[var(--text-primary)] cursor-blink">
                  {currentStatus || "Awaiting…"}
                </p>
                <div className="mt-4 flex items-center gap-6 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
                  <span><span className="text-[var(--text-secondary)]">elapsed</span> {formatElapsed(elapsed)}</span>
                  <span><span className="text-[var(--text-secondary)]">sources</span> {String(sourceCount).padStart(2, "0")}</span>
                </div>
              </div>
            </div>
          </aside>

          {/* Right log */}
          <section className="col-span-12 mt-8 flex min-h-0 flex-col lg:col-span-7 lg:mt-0 lg:pl-10">
            <div className="flex items-center justify-between border-b border-[var(--rule-strong)] pb-3">
              <p className="eyebrow">Live transcript</p>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
                {String(activityLog.length).padStart(3, "0")} entries
              </p>
            </div>

            <div className="mt-2 min-h-0 flex-1 overflow-y-auto pr-2">
              {activityLog.length === 0 ? (
                <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-quaternary)]">
                  Awaiting first agent action…
                </p>
              ) : (
                <ul>
                  {activityLog.map((item, index) => {
                    const t = new Date(item.ts);
                    const stamp = `${String(t.getMinutes()).padStart(2, "0")}:${String(t.getSeconds()).padStart(2, "0")}.${String(Math.floor(t.getMilliseconds() / 100))}`;
                    const colorClass =
                      item.kind === "error" ? "text-[var(--accent)]"
                      : item.kind === "result" ? "text-[var(--text-primary)]"
                      : item.kind === "info" ? "text-[var(--text-secondary)]"
                      : "text-[var(--text-secondary)]";
                    const marker =
                      item.kind === "call" ? "▸"
                      : item.kind === "result" ? "✓"
                      : item.kind === "error" ? "✕"
                      : "·";
                    return (
                      <li
                        key={index}
                        className="animate-slide-in-right grid grid-cols-[64px_18px_1fr] gap-x-3 border-b border-[var(--rule-soft)] py-2.5"
                        style={{ animationDelay: `${Math.min(index * 30, 200)}ms`, animationFillMode: "both" }}
                      >
                        <span className="font-mono text-[10px] tabular-nums text-[var(--text-quaternary)]">
                          {stamp}
                        </span>
                        <span className={`font-mono text-[12px] ${colorClass}`}>{marker}</span>
                        <div className="min-w-0">
                          <span className="mr-2 font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--text-tertiary)]">
                            {item.tool}
                          </span>
                          <span className={`font-mono text-[12px] leading-snug ${colorClass}`}>
                            {item.text}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                  <div ref={activityEndRef} />
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* ═══════════════════════ RESULT ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-y-auto transition-opacity duration-400 ${
          appState === "result" ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-6xl px-6 py-10 sm:px-10 lg:px-14 lg:py-14">
          {/* Masthead */}
          <header className="border-b border-[var(--text-primary)] pb-6">
            <div className="flex items-center justify-between">
              <p className="eyebrow">Briefing No. {String(currentIteration || 1).padStart(3, "0")}</p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="btn-ghost"
                  aria-label="Copy"
                >
                  {copied ? <Check className="h-3 w-3 text-[var(--accent)]" /> : <ClipboardCopy className="h-3 w-3" />}
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  type="button"
                  onClick={handleDownloadPDF}
                  disabled={pdfDownloading}
                  className="btn-ghost"
                >
                  {pdfDownloading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
                  {pdfDownloading ? "PDF…" : "PDF"}
                </button>
                <button
                  type="button"
                  onClick={handleNewResearch}
                  className="btn-ghost"
                >
                  <RotateCcw className="h-3 w-3" />
                  New
                </button>
              </div>
            </div>

            <h1 className="mt-4 font-serif-display text-[56px] leading-[0.98] tracking-[-0.025em] text-[var(--text-primary)] sm:text-[72px]">
              {personName}
            </h1>

            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
              {context && (
                <span className="text-[var(--text-secondary)]">
                  <span className="text-[var(--text-tertiary)]">Re ·</span> {context}
                </span>
              )}
              <span>{formatDateStamp(new Date())}</span>
              {researchStartedAt && researchFinishedAt && (
                <span>compiled · {formatElapsed(researchFinishedAt - researchStartedAt)}</span>
              )}
              {(citedSourceCount || sourceCount) > 0 && (
                <span>
                  {String(citedSourceCount || sourceCount).padStart(2, "0")} sources
                </span>
              )}
            </div>
          </header>

          {/* Body + Sources */}
          <div className="mt-10 grid grid-cols-12 gap-10">
            <article className="prose-dossier col-span-12 max-w-[680px] lg:col-span-8">
              <ReactMarkdown>{parsedBrief.body}</ReactMarkdown>
            </article>

            <aside className="col-span-12 lg:col-span-4">
              <div className="lg:sticky lg:top-6">
                <div className="flex items-baseline justify-between border-b border-[var(--text-primary)] pb-2">
                  <p className="eyebrow">Sources</p>
                  <span className="font-mono text-[10px] tabular-nums text-[var(--text-tertiary)]">
                    {String(citedSourceCount).padStart(2, "0")}
                  </span>
                </div>
                {citedSourceCount === 0 ? (
                  <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-quaternary)]">
                    No cited sources in this brief.
                  </p>
                ) : (
                  <ol className="mt-3">
                    {parsedBrief.sources.map((source, idx) => (
                      <li
                        key={source.url}
                        className="group grid grid-cols-[28px_1fr] gap-x-2 border-b border-[var(--rule-soft)] py-2.5"
                      >
                        <span className="pt-0.5 font-mono text-[10px] tabular-nums text-[var(--text-quaternary)]">
                          {String(idx + 1).padStart(2, "0")}
                        </span>
                        <div className="min-w-0">
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block truncate text-[13px] leading-snug text-[var(--text-primary)] hover:text-[var(--accent)]"
                            title={source.title}
                          >
                            {source.title}
                          </a>
                          <p className="mt-0.5 truncate font-mono text-[10px] text-[var(--text-tertiary)]">
                            {source.hostname}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </aside>
          </div>

          {/* Colophon */}
          <footer className="mt-16 border-t border-[var(--rule)] pt-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
              End of brief · PersonaPrep · For preparation use only · Verify critical facts
            </p>
          </footer>
        </div>
      </div>

      {/* ═══════════════════════ HISTORY ═══════════════════════ */}
      <div
        className={`absolute inset-0 overflow-y-auto transition-opacity duration-400 ${
          appState === "history" ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="mx-auto w-full max-w-4xl px-6 py-12 sm:px-10 lg:px-14">
          <button
            type="button"
            onClick={handleNewResearch}
            className="btn-ghost mb-8 -ml-3"
          >
            <ChevronLeft className="h-3 w-3" />
            Back
          </button>

          <div className="mb-10 flex items-end justify-between gap-6 border-b border-[var(--text-primary)] pb-6">
            <div>
              <p className="eyebrow">The Archive</p>
              <h2 className="mt-3 font-serif-display text-[44px] leading-[1.02] text-[var(--text-primary)] sm:text-[56px]">
                Past briefings.
              </h2>
              <p className="mt-3 max-w-md font-serif-display text-[16px] leading-relaxed text-[var(--text-secondary)]">
                Every brief you compile is kept here until you remove it.
              </p>
            </div>
            <button
              type="button"
              onClick={loadHistory}
              disabled={historyLoading}
              className="btn-ghost"
            >
              {historyLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              Refresh
            </button>
          </div>

          {historyError && (
            <div className="mb-6 border-l-2 border-[var(--accent)] bg-[var(--accent-dim)] px-4 py-3 font-mono text-[12px] text-[var(--accent)]">
              {historyError}
            </div>
          )}

          {historyLoading && historyItems.length === 0 ? (
            <div className="flex items-center justify-center py-16 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
              <Loader2 className="mr-3 h-3.5 w-3.5 animate-spin" />
              Loading archive…
            </div>
          ) : historyItems.length === 0 ? (
            <div className="border border-dashed border-[var(--rule-strong)] py-16 text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
                Archive empty
              </p>
              <p className="mt-3 font-serif-display text-[18px] italic text-[var(--text-secondary)]">
                Your compiled briefs will appear here.
              </p>
            </div>
          ) : (
            <ul className="border-t border-[var(--rule-strong)]">
              {historyItems.map((item, idx) => {
                const created = new Date(item.created_at * 1000);
                const dateStamp = formatDateStamp(created);
                const timeStamp = `${String(created.getHours()).padStart(2, "0")}:${String(created.getMinutes()).padStart(2, "0")}`;
                const num = String(idx + 1).padStart(3, "0");
                return (
                  <li
                    key={item.id}
                    className="group grid grid-cols-[42px_140px_1fr_auto] gap-x-5 border-b border-[var(--rule)] py-5 transition-colors hover:bg-black/[0.02]"
                  >
                    <span className="font-mono text-[10px] tabular-nums text-[var(--text-quaternary)] pt-1">
                      {num}
                    </span>
                    <div className="font-mono text-[11px] tabular-nums text-[var(--text-tertiary)] pt-1">
                      <div>{dateStamp}</div>
                      <div className="mt-0.5 text-[var(--text-quaternary)]">{timeStamp}</div>
                    </div>
                    <div className="min-w-0">
                      <button
                        type="button"
                        onClick={() => handleOpenHistoryItem(item)}
                        className="block w-full text-left font-serif-display text-[20px] leading-tight text-[var(--text-primary)] hover:text-[var(--accent)] truncate"
                      >
                        {item.person_name}
                      </button>
                      {item.meeting_context && (
                        <p className="mt-1 line-clamp-2 text-[14px] text-[var(--text-secondary)]">
                          {item.meeting_context}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-start gap-1 pt-1">
                      <button
                        type="button"
                        onClick={() => handleOpenHistoryItem(item)}
                        className="btn-ghost"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => handleResearchFreshFromHistory(item)}
                        className="btn-ghost"
                        title="Re-run research with cache bypassed"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Re-run
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteHistoryItem(item.id)}
                        className="flex h-7 w-7 items-center justify-center rounded-[2px] text-[var(--text-quaternary)] hover:bg-[var(--accent-dim)] hover:text-[var(--accent)]"
                        aria-label="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
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
