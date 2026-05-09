/**
 * MET Engine — Bot Webhook Notify (outbound HTTP POST)
 *
 * Env:
 *   BOT_WEBHOOK_URL       (required for production; logs to console if unset)
 *   BOT_WEBHOOK_SECRET    (optional; sent as X-Webhook-Secret header if set)
 */

import { BotNotificationPayload } from './types';

export async function notifyBot(payload: BotNotificationPayload): Promise<void> {
  const url = process.env.BOT_WEBHOOK_URL;
  const secret = process.env.BOT_WEBHOOK_SECRET;

  if (!url) {
    console.log(
      `[BOT-WEBHOOK-DEV] (no BOT_WEBHOOK_URL) trip=${payload.tripId} type=${payload.type}`
    );
    return;
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (secret) headers['X-Webhook-Secret'] = secret;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.text();
      console.error(`[BOT-WEBHOOK] ${res.status}: ${body.slice(0, 200)}`);
    }
  } catch (err) {
    console.error('[BOT-WEBHOOK] fetch failed:', err);
  }
}
