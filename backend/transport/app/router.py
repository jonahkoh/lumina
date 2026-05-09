import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

import redis.asyncio as aioredis

from app import dashboard as dash
from app.config import settings
from app.kafka_client import publish
from app.matching import match_trip, pop_next_driver, pop_next_escort
from app.schemas import (
    MatchResult,
    ReachingBody,
    TripRequest,
    TripStatusResponse,
)

router = APIRouter()


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ── MET Engine → Transport ────────────────────────────────────────────────────

@router.post("/trips", status_code=202)
async def submit_trip(body: TripRequest):
    publish("trip.requested", body.model_dump(mode="json"))
    return {"trip_id": str(body.trip_id), "status": "matching_in_progress"}


@router.get("/trips/{trip_id}/status", response_model=TripStatusResponse)
async def trip_status(trip_id: uuid.UUID):
    async with _redis() as r:
        has_driver = await r.exists(f"candidates:driver:{trip_id}")
        has_escort = await r.exists(f"candidates:escort:{trip_id}")
        confirmed = await r.exists(f"confirmed:{trip_id}")
    return TripStatusResponse(
        trip_id=trip_id,
        has_candidates=bool(has_driver or has_escort),
        confirmed=bool(confirmed),
    )


@router.post("/trips/{trip_id}/cancel")
async def cancel_trip(trip_id: uuid.UUID):
    async with _redis() as r:
        await r.delete(f"candidates:driver:{trip_id}")
        await r.delete(f"candidates:escort:{trip_id}")
    publish(
        "trip.cancelled",
        {"trip_id": str(trip_id), "cancelled_at": datetime.now(timezone.utc).isoformat()},
    )
    return {"trip_id": str(trip_id), "cancelled_at": datetime.now(timezone.utc).isoformat()}


@router.post("/trips/{trip_id}/reaching")
async def trip_reaching(trip_id: uuid.UUID, body: ReachingBody):
    if body.actor_type == "driver":
        topic = "trip.driver_reaching"
        payload = {
            "trip_id": str(trip_id),
            "driver_id": str(body.actor_id),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    elif body.actor_type == "escort":
        topic = "trip.escort_reaching"
        payload = {
            "trip_id": str(trip_id),
            "escort_id": str(body.actor_id),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        raise HTTPException(status_code=400, detail="actor_type must be 'driver' or 'escort'")
    publish(topic, payload)
    return {"status": "ok"}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard_data(
    role: str = Query(...),
    id: Optional[uuid.UUID] = Query(default=None),
    provider_id: Optional[uuid.UUID] = Query(default=None),
):
    if role == "admin":
        return await dash.admin_dashboard(provider_id)
    if role == "driver":
        if not id:
            raise HTTPException(status_code=400, detail="id required for driver role")
        return await dash.driver_dashboard(id)
    if role == "escort":
        if not id:
            raise HTTPException(status_code=400, detail="id required for escort role")
        return await dash.escort_dashboard(id)
    raise HTTPException(status_code=400, detail="role must be admin, driver, or escort")


@router.get("/dashboard/page", response_class=HTMLResponse)
async def dashboard_page(
    role: str = Query(...),
    id: Optional[str] = Query(default=None),
):
    return HTMLResponse(content=_render_dashboard(role, id))


def _render_dashboard(role: str, actor_id: Optional[str]) -> str:
    id_param = f"&id={actor_id}" if actor_id else ""
    api_url = f"/transport/dashboard?role={role}{id_param}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Lumina Dashboard — {role.capitalize()}</title>
  <style>
    body {{ font-family: sans-serif; padding: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
    th {{ background: #f0f0f0; }}
    button {{ margin: 0.2rem; padding: 0.3rem 0.7rem; cursor: pointer; }}
    .section {{ margin-bottom: 2rem; }}
    #last-updated {{ color: #888; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>Lumina — {role.capitalize()} Dashboard</h1>
  <p id="last-updated">Loading...</p>
  <div id="content">Loading data...</div>

  <script>
    const API_URL = "{api_url}";
    const ROLE = "{role}";
    const ACTOR_ID = "{actor_id or ''}";

    function renderTable(headers, rows) {{
      if (!rows || rows.length === 0) return "<em>No records</em>";
      const ths = headers.map(h => `<th>${{h}}</th>`).join("");
      const trs = rows.map(r =>
        "<tr>" + headers.map(h => `<td>${{r[h] ?? ""}}</td>`).join("") + "</tr>"
      ).join("");
      return `<table><thead><tr>${{ths}}</tr></thead><tbody>${{trs}}</tbody></table>`;
    }}

    function renderDriverRow(d) {{
      const trips = (d.future_trip_ids || []).map(tid =>
        `<span>${{tid}}</span>
         <button onclick="accept('${{d.driver_id}}','${{tid}}')">Accept</button>
         <button onclick="reject('${{d.driver_id}}','${{tid}}')">Reject</button>`
      ).join("<br>");
      const reaching = d.status === "BUSY"
        ? `<button onclick="reaching('${{d.driver_id}}', 'driver')">I am reaching</button>` : "";
      return `<tr>
        <td>${{d.driver_id}}</td><td>${{d.status}}</td><td>${{d.provider_name || ""}}</td>
        <td>${{trips || "—"}}</td><td>${{reaching}}</td>
      </tr>`;
    }}

    function renderEscortRow(e) {{
      const trips = (e.future_trip_ids || []).map(tid =>
        `<span>${{tid}}</span>
         <button onclick="acceptEscort('${{e.escort_id}}','${{tid}}')">Accept</button>
         <button onclick="rejectEscort('${{e.escort_id}}','${{tid}}')">Reject</button>`
      ).join("<br>");
      const reaching = e.status === "BUSY"
        ? `<button onclick="reaching('${{e.escort_id}}', 'escort')">I am reaching</button>` : "";
      return `<tr>
        <td>${{e.escort_id}}</td><td>${{e.status}}</td><td>${{e.provider_name || ""}}</td>
        <td>${{trips || "—"}}</td><td>${{reaching}}</td>
      </tr>`;
    }}

    async function fetchAndRender() {{
      try {{
        const res = await fetch(API_URL);
        const data = await res.json();
        let html = "";

        if (ROLE === "admin") {{
          html += `<div class="section"><h2>Drivers</h2>
            <table><thead><tr><th>ID</th><th>Status</th><th>Provider</th><th>Upcoming</th><th></th></tr></thead>
            <tbody>${{(data.drivers || []).map(renderDriverRow).join("")}}</tbody></table></div>`;
          html += `<div class="section"><h2>Escorts</h2>
            <table><thead><tr><th>ID</th><th>Status</th><th>Provider</th><th>Upcoming</th><th></th></tr></thead>
            <tbody>${{(data.escorts || []).map(renderEscortRow).join("")}}</tbody></table></div>`;
          html += `<div class="section"><h2>Past Trips</h2>
            ${{renderTable(["trip_id","outcome","completed_at","provider_name"], data.past_trips || [])}}</div>`;
        }} else if (ROLE === "driver") {{
          const d = data.driver || {{}};
          html += `<div class="section"><h2>Profile</h2>
            <p><b>Status:</b> ${{d.status}} &nbsp; <b>Vehicle:</b> ${{d.vehicle_type}}</p></div>`;
          html += `<div class="section"><h2>Upcoming Trips</h2>
            ${{(data.upcoming_trips || []).map(tid =>
              `<div>${{tid}}
               <button onclick="accept('${{ACTOR_ID}}','${{tid}}')">Accept</button>
               <button onclick="reject('${{ACTOR_ID}}','${{tid}}')">Reject</button>
               ${{d.status === "BUSY" ? `<button onclick="reaching('${{ACTOR_ID}}', 'driver')">I am reaching</button>` : ""}}
               </div>`).join("") || "<em>None</em>"}}</div>`;
          html += `<div class="section"><h2>Past Trips</h2>
            ${{renderTable(["trip_id","outcome","completed_at"], data.past_trips || [])}}</div>`;
        }} else if (ROLE === "escort") {{
          const e = data.escort || {{}};
          html += `<div class="section"><h2>Profile</h2>
            <p><b>Status:</b> ${{e.status}}</p></div>`;
          html += `<div class="section"><h2>Upcoming Trips</h2>
            ${{(data.upcoming_trips || []).map(tid =>
              `<div>${{tid}}
               <button onclick="acceptEscort('${{ACTOR_ID}}','${{tid}}')">Accept</button>
               <button onclick="rejectEscort('${{ACTOR_ID}}','${{tid}}')">Reject</button>
               ${{e.status === "BUSY" ? `<button onclick="reaching('${{ACTOR_ID}}', 'escort')">I am reaching</button>` : ""}}
               </div>`).join("") || "<em>None</em>"}}</div>`;
          html += `<div class="section"><h2>Past Trips</h2>
            ${{renderTable(["trip_id","outcome","completed_at"], data.past_trips || [])}}</div>`;
        }}

        document.getElementById("content").innerHTML = html;
        document.getElementById("last-updated").textContent =
          "Last updated: " + new Date().toLocaleTimeString();
      }} catch (err) {{
        document.getElementById("content").innerHTML = "<p style='color:red'>Failed to load: " + err + "</p>";
      }}
    }}

    async function post(url, body) {{
      await fetch(url, {{ method: "POST", headers: {{"Content-Type":"application/json"}}, body: JSON.stringify(body) }});
      fetchAndRender();
    }}

    function accept(driverId, tripId) {{
      post(`/drivers/${{driverId}}/trips/${{tripId}}/accept`, {{}});
    }}
    function reject(driverId, tripId) {{
      post(`/drivers/${{driverId}}/trips/${{tripId}}/reject`, {{}});
    }}
    function acceptEscort(escortId, tripId) {{
      post(`/escorts/${{escortId}}/trips/${{tripId}}/accept`, {{}});
    }}
    function rejectEscort(escortId, tripId) {{
      post(`/escorts/${{escortId}}/trips/${{tripId}}/reject`, {{}});
    }}
    function reaching(actorId, actorType) {{
      const tripId = prompt("Enter trip ID:");
      if (!tripId) return;
      post(`/transport/trips/${{tripId}}/reaching`, {{ actor_id: actorId, actor_type: actorType }});
    }}

    fetchAndRender();
    setInterval(fetchAndRender, 10000);
  </script>
</body>
</html>"""
