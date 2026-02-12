# SQL Assistant Chat Application

A modern chat application built with React, TypeScript, and Tailwind CSS. Features a claude.ai-inspired UI with streaming support for real-time AI responses.

## Features

- **Clean, Modern UI**: Dark sidebar with light chat area, similar to claude.ai
- **Real-time Streaming**: Token-by-token streaming of AI responses
- **Markdown Support**: Full markdown rendering with syntax-highlighted code blocks
- **Responsive Design**: Mobile-friendly with collapsible sidebar
- **Conversation Management**: Create and switch between multiple conversations
- **Code Block Features**: Copy button for code blocks, special styling for SQL queries
- **Auto-resizing Input**: Textarea that grows with content up to a maximum height
- **Type-safe**: Built entirely with TypeScript

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS v4** - Styling via @tailwindcss/vite plugin
- **react-markdown** - Markdown rendering
- **@google/generative-ai** - Official Gemini SDK for AI interactions

## Project Structure

```
src/
├── components/
│   ├── Chat/
│   │   ├── ChatArea.tsx          # Main chat container
│   │   ├── MessageList.tsx       # Scrollable message list
│   │   ├── MessageBubble.tsx     # Individual message with markdown
│   │   └── TypingIndicator.tsx   # Animated typing dots
│   ├── Input/
│   │   └── ChatInput.tsx         # Auto-resizing textarea + send button
│   ├── Layout/
│   │   └── AppLayout.tsx         # Main layout combining sidebar + chat
│   └── Sidebar/
│       ├── Sidebar.tsx           # Conversation list sidebar
│       └── ConversationItem.tsx  # Single conversation item
├── hooks/
│   ├── useChat.ts               # Chat state management and API calls
│   └── useAutoScroll.ts         # Auto-scroll to bottom on new messages
├── services/
│   └── api.ts                   # Streaming API service
├── types/
│   └── index.ts                 # TypeScript interfaces
├── App.tsx
├── main.tsx
└── index.css                    # Tailwind imports + global styles
```

## Getting Started

### Installation

```bash
npm install
```

### Configuration

Copy `.env.example` to `.env` and configure your API endpoint:

```bash
cp .env.example .env
```

Edit `.env`:
```
VITE_GEMINI_API_KEY=your_gemini_api_key_here
VITE_MODEL=gemini-3-flash
```

Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## API Integration

The application uses the official **Google Generative AI SDK** (`@google/generative-ai`) to communicate directly with Gemini.

**Features:**
- Direct integration with Gemini API (no backend required)
- Streaming responses using `sendMessageStream()`
- Conversation history management
- Automatic message format conversion (assistant → model role)

The implementation is in `src/services/api.ts`:
- Uses `GoogleGenerativeAI` client
- Converts chat history to Gemini's format
- Streams responses token-by-token
- Handles errors gracefully

**Models Supported:**
- `gemini-3-flash` (default)
- Any other Gemini model - just update `VITE_MODEL` in `.env`

## Keyboard Shortcuts

- **Enter**: Send message
- **Shift + Enter**: New line in message

## Customization

### Colors

Main colors can be adjusted in the components:
- Sidebar: `#1a1a2e` (dark navy)
- Chat area: `#f9f9f9` (light gray)
- User messages: `#e8e8f0` (subtle purple-gray)
- AI messages: `white`

### Sidebar Width

Default: `280px`. Modify in `src/components/Sidebar/Sidebar.tsx`

### Max Message Width

Default: `768px`. Modify in `src/components/Chat/MessageList.tsx` and `src/components/Input/ChatInput.tsx`

## TypeScript

The project uses strict TypeScript with no `any` types. All components are fully typed.

Key types are defined in `src/types/index.ts`:
- `Message`: Individual chat message
- `Conversation`: Collection of messages
- `ChatState`: Application state

## License

MIT
