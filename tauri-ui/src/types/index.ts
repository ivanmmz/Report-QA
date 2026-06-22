export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export interface Citation {
  source: string;
  score: number;
  snippet: string;
}

export interface Report {
  title: string;
  content: string;
  savedAt: Date;
}

export interface Provider {
  name: string;
  baseUrl: string;
  apiKey: string;
  models: string[];
  isValid: boolean;
}
