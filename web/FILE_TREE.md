# File tree

```
web/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── CheckPrice.tsx
│   ├── ConfirmForm.tsx
│   ├── DemoBadge.tsx
│   ├── FabMenu.tsx
│   ├── Hero.tsx
│   ├── MyLocation.tsx
│   ├── Navbar.tsx
│   ├── NearMandi.tsx
│   ├── VerdictCard.tsx
│   └── WeatherOutlook.tsx
├── context/
│   └── AppProvider.tsx
├── hooks/
│   ├── useGeolocation.ts
│   └── useI18n.tsx
├── i18n/
│   ├── en.ts
│   ├── index.ts
│   └── ur.ts          # TODO: native Urdu speaker review
├── lib/
│   ├── api.ts         # only place to swap real endpoints
│   ├── geo.ts         # AMIS markets + haversine × 1.3
│   └── storage.ts
├── mock/
│   ├── analyze.ts
│   ├── prices.ts
│   └── weather.ts
├── types/
│   └── domain.ts      # mirrors ../schema.py
├── .env.example
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```
