# KIRA — Solar System UI | Full Build Prompt (Web Version)

## Project Context
KIRA is a personal AI assistant. The current UI is a basic chat 
interface running as a web app. We are replacing it entirely with 
an interactive solar system where every planet represents a service. 
This is not a reskin — it is a complete frontend rebuild.

The backend (FastAPI server on laptop, Ollama phi3:mini) already 
exists and is working. This prompt is purely about the web frontend, 
served from the same FastAPI server and accessed via browser on 
phone or laptop.

---

## Core Concept
KIRA is the Sun at the center of the screen — always glowing, always 
present. Every service she has access to is a planet orbiting her. The 
user always starts at the solar system overview. When they speak, KIRA 
identifies the intent and the camera flies to the relevant planet. The 
response is delivered from that planet's surface. When done, camera 
pulls back to the solar system view.

The universe is never static — planets reflect real live data at all 
times without the user asking.

---

## Planet Map

| Planet | Service | Base Color | Orbit Speed |
|--------|---------|------------|-------------|
| Sun | KIRA (core AI) | White-gold | Stationary |
| Earth | General conversation | Blue-green | Medium |
| Mars | Productivity monitor | Red-orange | Fast |
| Saturn | Google Calendar | Gold-beige | Slow |
| Europa | GitHub search | Ice blue | Medium-fast |
| Jupiter | Gemini fallback | Brown-orange | Very slow |

---

## Planet Behaviors (Live Data)

### Sun — KIRA Core
- Idle: slow golden pulse, corona rays extending and retracting
- Listening: solar flare erupts outward, voice waveform radiates 
  from surface as rings
- Thinking: rapid flickering corona, intense brightness
- Speaking: steady bright glow, response text radiates from center

### Earth — General Conversation
- Idle: slow rotation, cloud cover drifting, city lights on dark side
- Active: camera zooms into atmosphere, response appears as cloud 
  formations spelling out text, dissolves when done
- Voice waveform wraps around equator as a glowing band while 
  user is speaking

### Mars — Productivity Monitor
- Productive state: calm reddish surface, minimal storm activity, 
  slight green atmospheric tint
- Distracted state (YouTube/games detected): violent red storms 
  form, atmosphere darkens, surface erupts
- Alert trigger: Mars visibly explodes with storm activity from 
  the solar system view — visible without zooming in
- Zoomed in: weather map of surface shows distraction duration 
  as storm intensity

### Saturn — Google Calendar
- Rings represent days — today's ring is brightest
- Ring particles are calendar events — labeled, glowing dots
- Idle: slow majestic ring rotation
- Adding reminder: new particle launches from surface and joins 
  the correct ring with a trail
- Reading schedule: camera orbits through the rings, events 
  float toward camera as readable cards, dissolve after reading
- Busier days = denser rings — visible from solar system view

### Europa — GitHub
- Surface covered in hexagonal ice grid pattern
- Idle: cold blue glow, slow surface shimmer
- Search active: surface cracks open, results rise as glowing 
  ice pillars — each pillar shows repo name, stars, language
- Pillar click: opens GitHub link in new tab
- More stars = taller pillar
- Empty search result: surface stays frozen, single crack forms

### Jupiter — Gemini Fallback
- Always the biggest, most distant, most imposing planet
- Idle: slow storm bands rotating, red spot visible
- Permission request: camera begins flying toward Jupiter, 
  KIRA voice says "this needs Gemini, should I proceed?"
- User says yes: camera arrives, storm intensifies, response 
  delivered from cloud surface
- User says no: camera pulls back, Jupiter recedes
- This planet should feel like a big decision every time

---

## Camera System (Most Important Part)

The camera is the soul of this UI. Every transition must feel like 
actual space travel — smooth, weighted, with a sense of distance.

### Camera States
1. OVERVIEW — pulled back, full solar system visible, all planets 
   orbiting, user can see everything at once
2. APPROACH — camera accelerating toward a planet, stars 
   streaking slightly, planet growing rapidly
3. ORBIT — camera circling the planet at medium distance, 
   surface details visible
4. SURFACE — camera very close, planet fills screen, 
   interaction happening

### Camera Transition Rules
- OVERVIEW → APPROACH: triggered by KIRA identifying intent
- APPROACH → ORBIT: automatic, takes 1.2 seconds
- ORBIT → SURFACE: triggered when response is ready to deliver
- SURFACE → OVERVIEW: triggered when response is fully delivered, 
  3 second delay so user can read/absorb
- All transitions use spring-based easing, never linear
- Stars in background have subtle parallax during camera movement

### Camera should NEVER cut — always travel

---

## Voice Interaction Flow

1. User clicks/holds anywhere on the Sun (mousedown/touchstart 
   for mobile browser support)
2. Sun erupts — voice waveform radiates outward as solar rings
3. User speaks — Web Audio API captures amplitude in real time, 
   waveform reacts visually
4. User releases — Sun pulses once (processing indicator)
5. Audio sent to KIRA server via existing /voice endpoint
6. KIRA identifies intent — camera begins flying to correct planet
7. Camera arrives — response delivered from planet surface
8. Response audio plays via HTML5 Audio / Web Speech API
9. After delivery, 3 second hold, then camera returns to overview

### Text Display Rules
- No chat bubbles anywhere in this UI
- Text emerges FROM the planet surface — not overlaid on top
- Each word fades in sequentially, not all at once
- After delivery, text dissolves back into the planet
- Font: monospace for GitHub/technical, rounded sans for everything else
- Max visible text at once: 3 lines

---

## Persistent Solar System Elements

### Always visible from overview
- Sun pulsing gently at center
- All planets orbiting at their respective speeds
- Mars color visible — changes with productivity state
- Saturn ring density — changes with calendar fullness
- A subtle star field background with very slow parallax drift
- Small status dot near Sun: green (online), red (offline), 
  yellow (thinking)

### Ambient sounds (optional but recommended)
- Low space hum in background (looping audio file)
- Whoosh during camera travel
- Planet-specific ambient when zoomed in 
  (wind on Mars, ice creak on Europa, deep rumble on Jupiter)
- Must respect browser autoplay policies — sound starts only 
  after first user interaction

---

## Build Phases

---

### Phase 1 — Static Solar System (No interaction yet)
**Goal: Get the visual foundation right before adding any logic**

Build the solar system as a pure visual scene using HTML5 Canvas:
- Full screen dark space background with star field 
  (600+ dots, varying opacity, rendered once to offscreen canvas 
  for performance)
- Sun at center with animated corona glow (radial gradient + 
  animated rings, redrawn each frame)
- 5 planets rendered as circles with distinct colors and gradient 
  textures
- Planets orbit the sun using trigonometry 
  (x = cx + r*cos(angle), y = cy + r*sin(angle))
- Each planet has its own orbit radius and speed
- Saturn has visible rings (ellipse drawn behind and in front 
  of planet using clipping)
- Canvas resizes responsively to viewport (handle window resize)
- No camera movement yet — fixed overview perspective
- No interaction yet — pure animation via requestAnimationFrame

**Deliverables:**
- SolarSystem.jsx — main canvas component with animation loop
- Planet.js — planet rendering logic with color, size, orbit 
  radius, orbit speed config
- StarField.js — background star layer (separate canvas layer 
  or pre-rendered)
- usePlanetOrbit.js — custom hook for orbit position calculation

**Success check:** Open in browser, see a living solar system with 
all 5 planets orbiting the sun smoothly at 60fps, responsive to 
window resizing.

---

### Phase 2 — Camera System
**Goal: Camera can fly from overview to any planet and back**

- Implement camera as a transform state — translateX, translateY, 
  scale applied to the canvas drawing context
- OVERVIEW state: zoomed out, all planets visible
- APPROACH + ORBIT + SURFACE states per planet
- Smooth spring/easing animation between camera states 
  (use a tween library or custom easing functions with 
  requestAnimationFrame)
- Stars have parallax offset during camera movement (move 
  slower than planets)
- Add planet click interaction — click any planet to fly to it
- Add an "escape" key or back button overlay to return to overview
- No KIRA logic yet — purely navigation

**Deliverables:**
- useCamera.js — camera state machine and animation logic
- Camera transform applied via ctx.translate/ctx.scale in 
  render loop
- Each planet gets a click handler (hit-test based on canvas 
  coordinates) that triggers camera fly

**Success check:** Click Earth, camera flies smoothly to Earth, 
press back, camera returns to overview. Repeat for all planets.

---

### Phase 3 — Voice Input Layer
**Goal: Mic interaction on Sun, waveform animation, send to backend**

- Click and hold Sun to activate mic (mousedown/touchstart)
- Sun animates into listening state (solar flare + waveform rings)
- Record audio using MediaRecorder API (getUserMedia)
- Show real-time amplitude as animated rings radiating from Sun 
  using AnalyserNode from Web Audio API
- On release, send audio blob to KIRA server 
  (POST /voice endpoint, same as current backend)
- Show thinking state on Sun while waiting for response
- Response comes back as JSON with text + intent field
- No planet routing yet — just log the intent to console
- TTS: play response audio returned from server using 
  HTML5 Audio element

**Deliverables:**
- useMic.js — MediaRecorder setup, amplitude tracking via 
  AnalyserNode, send to server
- SunInteraction.js — press handler, listening animation state
- useKIRA.js — fetch/axios hook, manages loading/response state

**Success check:** Hold Sun, speak "what is python", release, 
hear KIRA respond, see intent logged in console. Test on both 
desktop Chrome and mobile browser.

---

### Phase 4 — Intent Routing to Planets
**Goal: KIRA's response automatically flies camera to correct planet**

The server response must include an intent field:
- "general" → Earth
- "productivity" → Mars  
- "calendar" → Saturn
- "github" → Europa
- "gemini" → Jupiter

On response received:
- Camera automatically flies to the correct planet
- Response text delivers from that planet's surface
- After 3 seconds, camera returns to overview

**Backend change needed:** Add intent classification to server 
response JSON. KIRA already knows which tool was called — map 
tool name to intent string and include in response.

**Deliverables:**
- intentToPlanet.js — mapping object + routing logic
- PlanetResponse.js — text delivery animation per planet, 
  rendered as canvas text or HTML overlay positioned over canvas
- Update useKIRA.js to trigger camera on intent received

**Success check:** Say "schedule gym at 6pm", camera flies to 
Saturn, confirmation text appears on Saturn's surface, camera 
returns. Say "search github for voice assistants", camera flies 
to Europa, results appear as pillars.

---

### Phase 5 — Live Planet Data
**Goal: Planets visually reflect real data without user asking**

- Mars: poll /productivity endpoint every 30 seconds, update 
  storm intensity based on distraction time
- Saturn: poll /calendar endpoint on page load, render ring 
  particle count based on today's events
- Europa: store last GitHub search results in state, show faint 
  pillar outlines on surface even from overview
- Sun: pulse speed reflects server response time (faster = 
  server is quick today)

**Deliverables:**
- useProductivityData.js — polling hook for Mars state
- useCalendarData.js — polling hook for Saturn ring density
- Each planet's render function accepts a data parameter that 
  drives visuals

**Success check:** Have 3 events in Google Calendar, open app, 
Saturn's rings visibly have 3 brighter particles without asking 
anything.

---

### Phase 6 — Polish and Planet Personalities
**Goal: Each planet feels completely unique and alive**

- Earth: add cloud layer that drifts independently of planet 
  rotation, city lights flicker on night side
- Mars: add dust particle system that intensifies with 
  distraction level, surface crack animations on alert
- Saturn: ring particles glow brighter as their event time 
  approaches, click a particle to hear the event name (text-to-speech)
- Europa: hexagonal ice grid on surface, crack animation on 
  search, pillar click opens GitHub link in new tab
- Jupiter: red spot animated, storm bands move at different 
  speeds, planet grows slightly larger during Gemini permission 
  request to feel imposing
- Ambient audio layer per planet (HTML5 Audio, looping, 
  crossfade on transitions)
- Subtle screen vibration on mobile via Vibration API on 
  planet arrival

---

## Tech Stack

| Need | Library |
|------|---------|
| Rendering | HTML5 Canvas API (2D context) |
| Camera animations | Custom easing functions + requestAnimationFrame, 
  or framer-motion for overlay elements |
| Mic recording | MediaRecorder API + getUserMedia |
| Audio analysis | Web Audio API (AnalyserNode) |
| TTS playback | HTML5 Audio element (server-returned audio) or 
  Web Speech API as fallback |
| Particle systems | Custom canvas particle engine |
| Haptics | Vibration API (mobile browsers) |
| HTTP to KIRA server | axios or fetch |
| Framework | React (Vite) — served as static build from FastAPI |

---

## Browser Compatibility Notes
- MediaRecorder and getUserMedia require HTTPS in production 
  (Ngrok provides this automatically)
- Autoplay audio policies mean ambient sound must start after 
  first user gesture
- Test primarily on mobile Chrome since phone is the main device, 
  but ensure desktop Chrome also works for development

---

## Absolute Rules

1. NO chat bubbles anywhere — ever
2. NO flat buttons — all interactions are gestures on canvas objects
3. Camera NEVER cuts — always travels
4. Text always emerges FROM planets — never overlaid in boxes
5. The solar system must always be moving — nothing is ever 
   completely static
6. Mars weather must reflect real productivity state
7. Saturn rings must reflect real calendar data
8. Jupiter must always feel like the last resort

---

## Starting instruction
Begin with Phase 1 only. Do not skip ahead.
Set up the React + Vite project structure, install dependencies, 
and build the static solar system scene with all 5 planets 
orbiting the sun at 60fps on Canvas before touching any 
interaction logic.
Ask me before moving to Phase 2.