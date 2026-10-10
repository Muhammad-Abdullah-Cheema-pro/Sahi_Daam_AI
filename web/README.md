# Sahi Daam AI — Web (Next.js)

Urdu-first (RTL) fair-price and sell-or-move advisor UI for Punjab farmers.
Aligned with the Python Streamlit backend types in `../schema.py` and AMIS markets in `../geo.py`.

**All data is MOCK** via `lib/api.ts` → `mock/*`. No network calls unless you set `NEXT_PUBLIC_API_URL`.

## Run

```powershell
cd web
copy .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

- Default language: **Urdu (RTL)** — toggle English in the navbar.
- Theme: light / dark (class strategy).
- `NEXT_PUBLIC_SIMULATE_GEO=1` makes “Use my location” use Okara demo coordinates (useful when the browser blocks geolocation).

## Swap to real API later

Only change `lib/api.ts` (and set `NEXT_PUBLIC_API_URL`). Call sites stay the same:

- `parseInput(text)`
- `analyze(request)`
- `getWeather(location)`
- `getMandis(origin)`

## Layout order

1. Sticky navbar  
2. Hero (location + weather)  
3. My Location  
4. Check My Price  
5. Near Mandi  
6. Weather & Harvest Outlook  
7. Footer  

## Accessibility / RTL notes

- Logical Tailwind utilities (`ms-`, `me-`, `ps-`, `pe-`, `text-start`, `end-`).
- Tap targets ≥ 48px, focus-visible rings, skip link, `aria-live` for location status.
- Risk badges always include text + icon (never colour alone).
- Forbidden broker-accusation words are not used in copy.

## Relation to Streamlit app

The Python app in the repo root remains the hackathon demo engine. This `web/` folder is the production-oriented UI shell with the same domain model.
