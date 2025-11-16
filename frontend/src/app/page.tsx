"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Search, Globe, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { generateBriefStream, type AgentEvent } from "@/lib/api";

const navItems = [
  { label: "Home", href: "#" },
  { label: "Use Cases", href: "#usecases" },
  { label: "Blog", href: "#blog" },
  { label: "Contact", href: "#contact" },
];

const getToolIcon = (toolName: string) => {
  if (toolName === "tavily_search") return <Search className="h-4 w-4" />;
  if (toolName === "brave_search") return <Search className="h-4 w-4" />;
  if (toolName === "firecrawl_scrape") return <Globe className="h-4 w-4" />;
  return <FileText className="h-4 w-4" />;
};

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

  const formDisabled = useMemo(
    () => !personName || !context || isLoading,
    [personName, context, isLoading]
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setOutput("");
    setActivityLog([]);
    setCurrentStatus("Starting research...");

    try {
      await generateBriefStream(
        personName,
        context,
        (event: AgentEvent) => {
          // Handle each event
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

            // Format tool input for display
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
              setActivityLog((prev) => [...prev, `✓ ${summary.message}`]);
            } else if (summary?.error) {
              setActivityLog((prev) => [...prev, `✗ ${summary.error}`]);
            }
          }
        },
        (brief: string) => {
          // Handle completion
          setCurrentStatus("Research complete!");
          setOutput(brief);
          setIsLoading(false);
        },
        (error: string) => {
          // Handle error
          setCurrentStatus("Error occurred");
          setOutput(`Error: ${error}`);
          setIsLoading(false);
        }
      );
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
        </header>

        <section className="space-y-5 pb-10 text-center sm:text-left">
          <p className="text-sm uppercase tracking-[0.4em] text-[#7a7666]">
            AI Meeting Intelligence
          </p>
          <h1 className="font-serif text-4xl font-semibold leading-tight text-[#14120f] sm:text-5xl">
            Never walk into a meeting unprepared again
          </h1>
          <p className="text-lg text-[#3b382f] sm:text-xl">
            PersonaPreparation researches any person in sixty seconds—
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
                Person background & why you're meeting
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

          <section className="rounded-[40px] border border-[#dcd8cd] bg-white/85 p-6 shadow-panel">
            <p className="text-sm font-medium uppercase tracking-[0.4em] text-[#7a7666]">
              Instant output
            </p>

            {isLoading && (
              <div className="mt-4 rounded-[28px] border border-[#e5e0d4] bg-gradient-to-br from-white to-[#f7f5ee] p-6 shadow-inner">
                <div className="flex items-center gap-3 mb-4">
                  <Loader2 className="h-5 w-5 animate-spin text-[#7a7666]" />
                  <p className="text-base font-medium text-[#1f1d18]">
                    {currentStatus}
                  </p>
                </div>

                {activityLog.length > 0 && (
                  <div className="space-y-2 mt-4 max-h-[200px] overflow-y-auto">
                    {activityLog.map((activity, index) => (
                      <div
                        key={index}
                        className="text-sm text-[#4d4a43] flex items-start gap-2 animate-in fade-in slide-in-from-left-2 duration-300"
                      >
                        <span className="text-[#7a7666] mt-0.5">•</span>
                        <span>{activity}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!isLoading && (
              <div className="mt-4 h-[280px] rounded-[28px] border border-[#e5e0d4] bg-gradient-to-br from-white to-[#f7f5ee] p-6 text-base leading-relaxed text-[#1f1d18] shadow-inner overflow-y-auto">
                {output.split("\n").map((line, index) => (
                  <p
                    key={index}
                    className={index === 0 ? "font-semibold" : "mt-2"}
                  >
                    {line}
                  </p>
                ))}
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
            founder teams use PersonaPreparation to research people fast ,no
            more juggling dozens of browser tabs. Connect our API and every
            brief is automatically saved and ready to add to your CRM.
          </p>
        </section>
      </div>
    </main>
  );
}
