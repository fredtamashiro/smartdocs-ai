const API_URL =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const APP_API_KEY = process.env.NEXT_PUBLIC_APP_API_KEY;

function getAuthHeaders(): Record<string, string> {
  if (!APP_API_KEY) {
    return {};
  }

  return {
    "X-API-Key": APP_API_KEY,
  };
}

export type DocumentItem = {
  document_id: string;
  collection_name: string;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  chunks_file: string;
  total_pages: number;
  total_chars: number;
  total_chunks: number;
  created_at: string;
};

export type DocumentsResponse = {
  total: number;
  documents: DocumentItem[];
};

export async function fetchDocuments(): Promise<DocumentsResponse> {
  const response = await fetch(`${API_URL}/documents`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar documentos.");
  }

  return response.json();
}

export type ChatSource = {
  page: number;
  chunk_index: number;
  score: number;
  matched_query?: string;
  preview: string;
};

export type ChatResponse = {
  question: string;
  answer: string;
  sources: ChatSource[];
};

export async function askQuestion(params: {
  documentId: string;
  question: string;
  k?: number;
}): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/chat/ask`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: params.documentId,
      question: params.question,
      k: params.k ?? 4,
    }),
  });

  if (!response.ok) {
    throw new Error("Erro ao enviar pergunta.");
  }

  return response.json();
}

export type IngestDocumentResponse = {
  message: string;
  document: DocumentItem;
  vectorstore_dir: string;
};

export async function uploadDocument(file: File): Promise<IngestDocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/documents/ingest`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Erro ao enviar documento.");
  }

  return response.json();
}
