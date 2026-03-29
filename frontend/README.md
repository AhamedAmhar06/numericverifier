# NumericVerifier Frontend

React + Vite + TypeScript frontend for NumericVerifier.

## Prerequisites

- Node.js 18+ (recommended)
- Backend running at `http://localhost:8001`

## Install

```bash
cd frontend
npm install
```

## Environment

Create `.env` in `frontend/`:

```bash
cp .env.example .env
```

Default:

```env
VITE_API_BASE_URL=http://localhost:8001
```

If unset, the app falls back to `http://localhost:8001`.

## Run (Development)

```bash
cd frontend
npm run dev
```

Open:

- `http://localhost:5173`

## Build

```bash
cd frontend
npm run build
```
