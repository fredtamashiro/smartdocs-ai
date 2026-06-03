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
  theme_id?: string;
  theme_name?: string;
  created_at: string;
};

export type DocumentsResponse = {
  total: number;
  documents: DocumentItem[];
};

export type DeleteDocumentResponse = {
  message: string;
  document_id: string;
  deleted_files: Array<{
    field: string;
    path: string;
  }>;
  removed_document: DocumentItem;
  warning?: string;
};

export async function fetchDocuments(): Promise<DocumentsResponse> {
  const response = await fetch(`${API_URL}/documents`, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar documentos.");
  }

  return response.json();
}

export async function deleteDocument(
  documentId: string,
): Promise<DeleteDocumentResponse> {
  const response = await fetch(`${API_URL}/documents/${documentId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Erro ao apagar documento.");
  }

  return response.json();
}

export type ChatSource = {
  page: number;
  chunk_index: number;
  score: number;
  matched_query?: string;
  relevance_score?: number;
  relevance_reason?: string;
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

export async function uploadDocument(
  file: File,
  themeId = "automotive_manual",
): Promise<IngestDocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("theme_id", themeId);

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

export type Theme = {
  theme_id: string;
  name: string;
  description: string;
  enrichment_rules: string[];
  query_rules: string[];
  answer_rules: string[];
};

export type ThemesResponse = {
  themes: Theme[];
};

export type ProcessingJobStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export type ProcessingJob = {
  job_id: string;
  job_type: string;
  status: ProcessingJobStatus;
  progress: number;
  current_step: string;
  payload: Record<string, unknown>;
  partial_result?: Record<string, unknown> | null;
  result?: {
    document?: DocumentItem;
    vectorstore_dir?: string;
    total_indexed_documents?: number;
    total_skipped_chunks?: number;
  } | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProcessingJobsResponse = {
  total: number;
  jobs: ProcessingJob[];
};

export type StartSmartIngestParams = {
  file: File;
  themeId: string;
  chunkSize?: number;
  chunkOverlap?: number;
  batchSize?: number;
};

export type StartSmartIngestResponse = {
  message: string;
  job: ProcessingJob;
};

export async function getThemes(): Promise<ThemesResponse> {
  const response = await fetch(`${API_URL}/themes`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar temas.");
  }

  return response.json();
}

export async function startSmartIngest({
  file,
  themeId,
  chunkSize = 1000,
  chunkOverlap = 200,
  batchSize = 10,
}: StartSmartIngestParams): Promise<StartSmartIngestResponse> {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("theme_id", themeId);
  formData.append("chunk_size", String(chunkSize));
  formData.append("chunk_overlap", String(chunkOverlap));
  formData.append("batch_size", String(batchSize));

  const response = await fetch(`${API_URL}/documents/smart-ingest/start`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Erro ao iniciar processamento inteligente.");
  }

  return response.json();
}

export async function getProcessingJobs(): Promise<ProcessingJobsResponse> {
  const response = await fetch(`${API_URL}/processing-jobs`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar jobs de processamento.");
  }

  return response.json();
}

export async function getProcessingJob(jobId: string): Promise<ProcessingJob> {
  const response = await fetch(`${API_URL}/processing-jobs/${jobId}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar status do job.");
  }

  return response.json();
}
