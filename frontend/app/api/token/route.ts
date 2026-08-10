import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { randomUUID } from 'crypto';
import { AccessToken, type AccessTokenOptions, type VideoGrant } from 'livekit-server-sdk';
import { RoomConfiguration } from '@livekit/protocol';

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
};

// NOTE: you are expected to define the following environment variables in `.env.local`:
const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const AGENT_NAME = process.env.AGENT_NAME;

// don't cache the results
export const revalidate = 0;

export async function POST(req: Request) {
  try {
    if (LIVEKIT_URL === undefined) {
      throw new Error('LIVEKIT_URL is not defined');
    }
    if (API_KEY === undefined) {
      throw new Error('LIVEKIT_API_KEY is not defined');
    }
    if (API_SECRET === undefined) {
      throw new Error('LIVEKIT_API_SECRET is not defined');
    }

    // Parse room config from request body (if provided).
    const body = await req.json().catch(() => ({}));
    let roomConfig: RoomConfiguration | undefined;
    if (body?.room_config) {
      roomConfig = RoomConfiguration.fromJson(body.room_config, { ignoreUnknownFields: true });
    } else if (AGENT_NAME) {
      // When AGENT_NAME is set, configure explicit agent dispatch so the named
      // agent worker picks up the job when a user joins the room.
      roomConfig = RoomConfiguration.fromJson(
        { agents: [{ agentName: AGENT_NAME }] },
        { ignoreUnknownFields: true }
      );
    }

    // ---- STABLE CALLER IDENTITY (Day 4) ----
    // Priority:
    //   1. `caller_id` sent by the client (persisted in localStorage and reused
    //      across calls — this is the source of truth).
    //   2. `caller_identity` cookie set on a previous call.
    //   3. Mint a strong UUID and persist it in BOTH the cookie and (via response)
    //      the client's localStorage.
    // The same stable ID must reach Call 2 so `lookup_caller_memory` can find
    // the record saved during Call 1. We never use a random per-call identity.
    const cookieStore = await cookies();
    const cookieIdentity = cookieStore.get('caller_identity')?.value;
    // Validate the client-supplied caller_id: safe charset + length cap (the DB
    // column is VARCHAR(255) and the value becomes the LiveKit participant identity).
    const rawBodyId = typeof body?.caller_id === 'string' ? body.caller_id.trim() : '';
    const bodyIdentity =
      rawBodyId.length > 0 &&
      rawBodyId.length <= 100 &&
      /^[a-zA-Z0-9_-]+$/.test(rawBodyId)
        ? rawBodyId
        : '';

    const participantIdentity =
      bodyIdentity || cookieIdentity || `saathi_${randomUUID()}`;
    const isNewIdentity = !cookieIdentity || cookieIdentity !== participantIdentity;

    const participantName = 'user';
    const roomName = `voice_assistant_room_${Math.floor(Math.random() * 10_000)}`;

    const participantToken = await createParticipantToken(
      { identity: participantIdentity, name: participantName },
      roomName,
      roomConfig
    );

    // Return connection details
    const data: ConnectionDetails = {
      serverUrl: LIVEKIT_URL,
      roomName,
      participantName,
      participantToken,
    };

    const headers = new Headers({
      'Cache-Control': 'no-store',
    });
    const response = NextResponse.json(data, { headers });

    // Keep the cookie in sync so the identity also survives localStorage clears
    // and works for browsers where the client-side storage is unavailable.
    if (isNewIdentity) {
      response.cookies.set('caller_identity', participantIdentity, {
        path: '/',
        maxAge: 60 * 60 * 24 * 365, // 1 year
        sameSite: 'lax',
      });
    }

    return response;
  } catch (error) {
    if (error instanceof Error) {
      console.error(error);
      return new NextResponse(error.message, { status: 500 });
    }
  }
}

function createParticipantToken(
  userInfo: AccessTokenOptions,
  roomName: string,
  roomConfig?: RoomConfiguration
): Promise<string> {
  const at = new AccessToken(API_KEY, API_SECRET, {
    ...userInfo,
    ttl: '15m',
  });
  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canPublishData: true,
    canSubscribe: true,
  };
  at.addGrant(grant);

  if (roomConfig) {
    at.roomConfig = roomConfig;
  }

  return at.toJwt();
}
