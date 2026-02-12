import { GoogleGenerativeAI } from '@google/generative-ai';
import type { Message } from '../types';

const API_KEY = import.meta.env.VITE_GEMINI_API_KEY || '';
const MODEL = import.meta.env.VITE_MODEL || 'gemini-3-flash';

// Initialize the Gemini AI client
const genAI = new GoogleGenerativeAI(API_KEY);

export interface StreamResponse {
  chunk: string;
  done: boolean;
}

export async function* streamChat(
  messages: Message[]
): AsyncGenerator<StreamResponse, void, undefined> {
  try {
    if (!API_KEY) {
      throw new Error('Gemini API key is not configured. Please set VITE_GEMINI_API_KEY in your .env file.');
    }

    // Get the generative model
    const model = genAI.getGenerativeModel({ model: MODEL });

    // Convert messages to Gemini format
    // Gemini expects alternating user/model messages
    const history = messages.slice(0, -1).map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }],
    }));

    const lastMessage = messages[messages.length - 1];

    // Start a chat session with history
    const chat = model.startChat({
      history,
    });

    // Stream the response
    const result = await chat.sendMessageStream(lastMessage.content);

    // Yield chunks as they arrive
    for await (const chunk of result.stream) {
      const text = chunk.text();
      if (text) {
        yield { chunk: text, done: false };
      }
    }

    // Signal completion
    yield { chunk: '', done: true };
  } catch (error) {
    console.error('Gemini API error:', error);
    throw error;
  }
}

// Fallback non-streaming function
export async function sendMessage(messages: Message[]): Promise<string> {
  try {
    if (!API_KEY) {
      throw new Error('Gemini API key is not configured. Please set VITE_GEMINI_API_KEY in your .env file.');
    }

    const model = genAI.getGenerativeModel({ model: MODEL });

    // Convert messages to Gemini format
    const history = messages.slice(0, -1).map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }],
    }));

    const lastMessage = messages[messages.length - 1];

    const chat = model.startChat({
      history,
    });

    const result = await chat.sendMessage(lastMessage.content);
    const response = await result.response;
    return response.text();
  } catch (error) {
    console.error('Gemini API error:', error);
    throw error;
  }
}
