// src/api/client.ts
import axios from "axios";

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8001";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export interface EmailEvent {
  id: string;
  status: "inbox" | "approval" | "done";
  title: string;
  from: string | null;
  description: string;
  snippet: string;
  draft_response: string | null;
  final_response: string | null;
  summary: string | null;
  db_status: string;
}

interface EmailBuckets {
  inbox: EmailEvent[];
  approval: EmailEvent[];
  done: EmailEvent[];
}

export async function fetchEmails(userId: string): Promise<EmailBuckets> {
  const { data } = await api.get<EmailBuckets>("/emails", {
    params: { user_id: userId },
  });
  return data;
}

export async function approveEmail(id: string): Promise<void> {
  await api.post(`/emails/${id}/approve`);
}

export async function rejectEmail(id: string, feedback: string): Promise<void> {
  await api.post(`/emails/${id}/reject`, { feedback });
}

export const oauthStartUrl = () => `${API_BASE}/oauth/google/start`;
