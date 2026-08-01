"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";

type ConnectionDetails = { token: string; serverUrl: string };

export default function Home() {
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startCall = useCallback(async (code: string) => {
    setConnecting(true);
    setError(null);
    try {
      const res = await fetch(`/api/token?code=${encodeURIComponent(code)}`);
      if (res.status === 401) {
        setError("That rune is unknown to me, mortal. Try another.");
        setConnecting(false);
        return;
      }
      if (!res.ok) throw new Error(`token request failed: ${res.status}`);
      setDetails(await res.json());
    } catch (err) {
      console.error(err);
      setError("The path to Asgard faltered. Try again.");
      setConnecting(false);
    }
  }, []);

  const handleDisconnected = useCallback(() => {
    setDetails(null);
    setConnecting(false);
  }, []);

  if (!details) {
    return <StartScreen connecting={connecting} error={error} onStart={startCall} />;
  }

  return (
    <LiveKitRoom
      token={details.token}
      serverUrl={details.serverUrl}
      connect
      audio
      video={false}
      onDisconnected={handleDisconnected}
      onError={(e) => console.error(e)}
      data-lk-theme="default"
      style={{ height: "100dvh" }}
    >
      <CallScreen />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function StartScreen({
  connecting,
  error,
  onStart,
}: {
  connecting: boolean;
  error: string | null;
  onStart: (code: string) => void;
}) {
  const [code, setCode] = useState("");
  return (
    <main className="mk-screen mk-center">
      <h1 className="mk-title">⚡ Midgard Kitchen</h1>
      <p className="mk-sub">
        Speak with Thor, God of Thunder — a warrior god who keeps his strength on
        real, whole food. Consult the Codex or read the skies for fare worthy of a
        feast.
      </p>
      <div className="mk-examples">
        <span className="mk-examples-label">Example questions to ask Thor:</span>
        <span>&ldquo;Consult the Codex &mdash; how does one make a proper beef stew?&rdquo;</span>
        <span>&ldquo;What is the sky over Chicago, and what feast befits it?&rdquo;</span>
        <span>&ldquo;Read the skies over London and give me a recipe to match.&rdquo;</span>
      </div>
      <form
        className="mk-gate"
        onSubmit={(e) => {
          e.preventDefault();
          onStart(code.trim());
        }}
      >
        <input
          className="mk-input"
          type="text"
          placeholder="Speak the rune…"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="Access code"
          autoFocus
        />
        <button
          className="mk-btn mk-btn-primary"
          type="submit"
          disabled={connecting || !code.trim()}
        >
          {connecting ? "Summoning Thor…" : "Start Call"}
        </button>
      </form>
      {error && <p className="mk-error">{error}</p>}
    </main>
  );
}

// Hard session cap (minutes) so an abandoned tab can't run up API costs.
// Env-overridable; NEXT_PUBLIC_ so the browser can read it.
const SESSION_LIMIT_MIN = Number(process.env.NEXT_PUBLIC_SESSION_LIMIT_MIN) || 10;

const STATE_LABEL: Record<string, string> = {
  disconnected: "awakening…",
  connecting: "awakening…",
  initializing: "awakening…",
  listening: "listening",
  thinking: "consulting the tomes…",
  speaking: "speaking",
};

function CallScreen() {
  const { state, audioTrack } = useVoiceAssistant();
  const room = useRoomContext();

  // Disconnect after the session cap so an abandoned tab can't run up API costs.
  // Client-side is enough here — access is already gated by the rune, so this
  // only guards against a legit user leaving the call open.
  useEffect(() => {
    const timer = setTimeout(() => room.disconnect(), SESSION_LIMIT_MIN * 60 * 1000);
    return () => clearTimeout(timer);
  }, [room]);

  return (
    <main className="mk-screen">
      <header className="mk-header">
        <span className="mk-title-sm">⚡ Midgard Kitchen</span>
        <span className="mk-state">Thor is {STATE_LABEL[state] ?? state}</span>
        <button className="mk-btn mk-btn-end" onClick={() => room.disconnect()}>
          End Call
        </button>
      </header>

      <div className="mk-viz">
        {audioTrack ? (
          <BarVisualizer state={state} trackRef={audioTrack} barCount={7} />
        ) : (
          <span className="mk-hint">Summoning Thor…</span>
        )}
      </div>

      <Transcript />
    </main>
  );
}

type Row = { id: string; identity?: string; text: string };

// The interim + final streams of a segment share an lk.segment_id; dedupe on it
// (keeping the latest) so the transcript updates in place instead of duplicating.
function dedupeSegments(items: any[]): Row[] {
  const map = new Map<string, Row>();
  items.forEach((t, i) => {
    const attrs = t?.streamInfo?.attributes ?? {};
    const id = attrs["lk.segment_id"] ?? t?.streamInfo?.id ?? String(i);
    map.set(id, { id, identity: t?.participantInfo?.identity, text: t?.text ?? "" });
  });
  return Array.from(map.values());
}

function Transcript() {
  const transcriptions = useTranscriptions();
  const { localParticipant } = useLocalParticipant();
  const endRef = useRef<HTMLDivElement>(null);

  const rows = dedupeSegments(transcriptions as unknown as any[]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rows.length]);

  return (
    <section className="mk-transcript" aria-label="Live transcript">
      {rows.length === 0 && (
        <p className="mk-hint">⚡ The God of Thunder approaches… await his greeting.</p>
      )}
      {rows.map((r) => {
        const isYou = !!r.identity && r.identity === localParticipant?.identity;
        return (
          <p key={r.id} className={isYou ? "mk-line mk-you" : "mk-line mk-thor"}>
            <span className="mk-speaker">{isYou ? "You" : "Thor"}</span>
            {r.text}
          </p>
        );
      })}
      <div ref={endRef} />
    </section>
  );
}
