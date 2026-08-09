# Saathi Swasthya 🩺 

**A multilingual Voice-First Health Navigation and Triage Assistant for Bharat.**

Built with **LiveKit Agents**, **Murf Falcon TTS**, and **Gemini 3.5**, Saathi Swasthya is designed to help users from rural and semi-urban India navigate their health concerns using natural voice in their native languages.

---

## 🌟 The Problem
Navigating healthcare in India is challenging. High patient-to-doctor ratios, low digital literacy, and language barriers mean many people delay seeking care or rely on unverified advice. Text-based chatbots are inaccessible to millions who cannot read or write fluently.

## 🚀 The Solution
Saathi Swasthya uses state-of-the-art voice AI to provide a deeply empathetic, voice-first health navigator. Users can simply speak in Hindi, Gujarati, or English. Saathi listens, asks intelligent follow-up questions, assesses urgency, and provides safe guidance on the next steps—whether that's visiting a local Primary Health Center or calling an ambulance.

> **Crucial Safety Guardrails:** Saathi is NOT a doctor. It strictly refuses to diagnose diseases or prescribe medicine. Its sole purpose is triage and navigation.

---

## 🏆 10 Days of Voice Agents Challenge Progress

*   **Day 1:** Core LiveKit & Murf TTS pipeline established.
*   **Day 2:** Healthcare System Prompt, Guardrails (Triage & Escalation tools), and automated LLM-as-a-judge tests implemented.
*   **Day 3:** Personalized Health Access Frontend added with:
    *   **5 Distinct Voice States:** Ready, Connecting, Listening, Speaking, and Call Ended.
    *   **Premium Transcript:** Code-mixed support displaying exact script (English, Hindi, Gujarati) with clear Speaker Identity.
    *   **Graceful Error Handling:** Handled microphone permission denials clearly.
    *   **Multilingual Support:** Dynamic language matching in Gujarati, Hindi, and English using Deepgram's multi-language STT and Gemini's language mirroring.
*   **Day 4:** Persistent Caller Memory & Proactive Privacy Consent added with:
    *   **SQLite Database Layer (`backend/src/db.py`)**: Stores long-term caller profiles (`caller_id`, `name`, `age_band`, `language_preference`, `ongoing_condition`, `last_triage_outcome`).
    *   **Cookie-Based Stable Identity (`frontend/app/api/token/route.ts`)**: Generates and persists a stable caller identity across repeat calls via HTTP cookies.
    *   **Caller Memory Tools (`backend/src/tools/memory.py`)**: `@function_tool` methods `lookup_caller_memory` & `save_caller_memory` integrated into the LiveKit Assistant.
    *   **Proactive Privacy & Consent Engine**: Turn completion handler dynamically detects personal info and strictly enforces consent guardrails—never saving data unless the user explicitly grants permission.
    *   **Memory Integration Tests (`backend/tests/test_memory.py` & `backend/src/test_db.py`)**: Verification scripts for database operations, memory persistence, and consent control flow.

---

## 🎙️ Voice Architecture

```mermaid
graph TD
    User((User Voice)) -->|WebRTC| LiveKit[LiveKit Server]
    LiveKit -->|Audio Stream| STT[Multilingual Deepgram STT]
    STT -->|Transcript| LLM[Gemini 3.5 Flash Lite]
    LLM -->|Function Calling| Tools[Triage, Escalation & Memory Tools]
    Tools <--> DB[(SQLite Persistent Memory)]
    LLM -->|Text| TTS[Murf Falcon TTS]
    TTS -->|Synthesized Audio| LiveKit
    LiveKit -->|WebRTC| UserEar((User Audio))
```

## 🛠️ Tech Stack
*   **Backend:** Python, LiveKit Agents SDK (`livekit-agents ~1.4`)
*   **Speech-to-Text (STT):** Deepgram Nova-3 (Multilingual & dual-stream Gujarati/Hindi script matching)
*   **Intelligence (LLM):** Google Gemini 3.5 Flash Lite
*   **Text-to-Speech (TTS):** Murf Falcon API (Locale: en-IN, Voice: Anisha, Style: Conversation)
*   **Database & Memory:** SQLite + `aiosqlite` (Async persistent caller profile database)
*   **Frontend:** Next.js, React, Tailwind CSS, LiveKit Agents UI Components

---

## 🚦 Safety & Guardrails
Medical AI carries immense responsibility. We have implemented a multi-layered safety architecture:
1.  **Prompt-Level Restraints:** The system prompt strictly prohibits diagnosis and prescription.
2.  **Urgency Detection:** The agent actively monitors for keywords (e.g., "chest pain", "unconscious") to immediately escalate to emergency services (108 / 112).
3.  **LLM-as-Judge Evals:** Our test suite uses automated LLM evaluation to prove the agent refuses harmful medical requests and diagnoses.
4.  **Proactive Privacy & Consent:** Personal health and demographic details are saved ONLY when explicit user consent is given, respecting caller privacy.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ and `uv` package manager
- Node.js and `pnpm`
- API Keys: LiveKit, Murf, Deepgram, Google Gemini

### 1. Start the Backend
```bash
cd backend
cp .env.example .env.local # Fill in your API keys
uv sync
uv run python src/agent.py dev
```

### 2. Start the Frontend
```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

---

## 🔮 Future Roadmap
*   **Phase 2:** Integrate with verified open health databases for accurate symptom mapping.
*   **Phase 3:** SMS integration to send the user a summary of the call and local clinic addresses.
*   **Phase 4:** Support for 10+ regional Indian languages.
