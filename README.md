# LexiDrill

A lightweight English word training and dictation app powered by **FastAPI + React (Vite)**.  
Supports **custom dictionaries**, **audio playback**, **quiz mode**, and **Anki export** — perfect for daily English practice.

---

## Features

-  Listening & dictation — play `.mp3` audio for each word  
-  Typing quiz — instant ✅ / ❌ feedback  
-  Progress tracking — correct / wrong stats  
-  Custom dictionaries — load JSON + MP3 from `dictionarys/`  
-  Mobile-friendly — responsive full-screen layout  
-  Desktop app — one-file build via PyInstaller  
-  Anki export — generate `.apkg` decks  

---

##  Project Structure

```
LexiDrill/
├── app.py                 # FastAPI backend
├── run.py                 # entry point
├── dictionarys/           # user-provided wordbooks
├── sessions/              # runtime session data
├── frontend/              # React + Vite + TypeScript + Ant Design frontend
│   ├── src/
│   └── dist/              # built static files
└── README.md
```

---

##  Setup

### Backend

```bash
pip install fastapi uvicorn pydantic
python app.py
```

API available at: http://127.0.0.1:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Default dev server: http://localhost:5173

---

## Build

To build standalone executable (Windows):

```bash
pyinstaller run.py --onefile --add-data "frontend/dist;frontend/dist"
```

---

## Dictionary Format

Example folder structure:

```
dictionarys/
└── Part1/
    ├── List1/
    │   ├── words.json
    │   └── voices/
    │       ├── word_1.mp3
    │       ├── word_2.mp3
    │       └── ...
    └── List2/
```

---

## API Summary

| Endpoint | Method | Description |
|-----------|--------|-------------|
| `/api/dictionaries` | GET | Get dictionary tree |
| `/api/course` | POST | Start quiz session |
| `/api/voice` | GET | Stream MP3 audio |
| `/api/report` | POST | Submit answer or finalize session |

---

## License

MIT License © 2025
