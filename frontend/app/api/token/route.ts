import { AccessToken } from "livekit-server-sdk";
import { RoomAgentDispatch, RoomConfiguration } from "@livekit/protocol";
import { NextResponse } from "next/server";

// Must match the agent's registered agent_name (backend settings.agent_name).
// Env-overridable so the deployed agent's name can change without a code edit.
const AGENT_NAME = process.env.LIVEKIT_AGENT_NAME ?? "midgard-kitchen";

// Room token generation + explicit agent dispatch (design-plan D3 + Step 4).
// The API secret stays server-side and is never shipped to the browser; the
// client receives only a short-lived JWT + the LiveKit server URL. The
// RoomConfiguration tells LiveKit to dispatch Thor into the room on creation.
export async function GET(request: Request) {
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const serverUrl = process.env.LIVEKIT_URL;

  if (!apiKey || !apiSecret || !serverUrl) {
    return NextResponse.json(
      { error: "LiveKit server env vars are not set" },
      { status: 500 },
    );
  }

  const { searchParams } = new URL(request.url);

  // Shared access-code gate. Active only when ACCESS_CODE is set (local dev stays
  // open); on the public deploy it stops randoms from burning API credits — the
  // token endpoint is the choke point: no token → no room → no agent → no cost.
  const requiredCode = process.env.ACCESS_CODE;
  if (requiredCode && searchParams.get("code") !== requiredCode) {
    return NextResponse.json({ error: "Invalid access code" }, { status: 401 });
  }

  // Fresh room per call → the room is "created" each time, so explicit dispatch fires.
  const room =
    searchParams.get("room") ??
    `midgard-kitchen-${Math.random().toString(36).slice(2, 10)}`;
  const identity =
    searchParams.get("identity") ??
    `mortal-${Math.random().toString(36).slice(2, 8)}`;

  const at = new AccessToken(apiKey, apiSecret, { identity });
  at.addGrant({ roomJoin: true, room, canPublish: true, canSubscribe: true });
  at.roomConfig = new RoomConfiguration({
    agents: [new RoomAgentDispatch({ agentName: AGENT_NAME })],
  });

  const token = await at.toJwt();
  return NextResponse.json({ token, serverUrl });
}
