const browserApiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const serverApiUrl =
  process.env.INTERNAL_API_URL ?? browserApiUrl;

export const API_URL =
  typeof window === "undefined" ? serverApiUrl : browserApiUrl;

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

function createApiUrl(path: string): string {
  return `${API_URL}${path}`;
}

async function getErrorMessage(
  response: Response,
  fallbackMessage: string,
): Promise<string> {
  try {
    const payload = await response.json();
    const detail = payload?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (typeof detail?.message === "string") {
      return detail.message;
    }
  } catch {
    return fallbackMessage;
  }

  return fallbackMessage;
}

function getAdminRequestInit(init?: RequestInit): RequestInit {
  return {
    ...init,
    credentials: "include",
  };
}

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  user: AuthUser;
};

export async function loginAdmin({
  email,
  password,
}: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(
    createApiUrl("/auth/login"),
    getAdminRequestInit({
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        password,
      }),
    }),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Erro ao fazer login."));
  }

  return response.json();
}

export async function getCurrentAdmin(): Promise<AuthUser> {
  const response = await fetch(
    createApiUrl("/auth/me"),
    getAdminRequestInit({
      cache: "no-store",
    }),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Sessao administrativa invalida."));
  }

  return response.json();
}

export async function logoutAdmin(): Promise<void> {
  const response = await fetch(
    createApiUrl("/auth/logout"),
    getAdminRequestInit({
      method: "POST",
    }),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Erro ao encerrar sessao."));
  }
}

export type DocumentItem = {
  document_id: string;
  collection_name: string;
  original_filename: string;
  stored_filename?: string;
  file_path?: string;
  chunks_file?: string;
  enriched_chunks_file?: string;
  enriched_collection_name?: string;
  retrieval_mode?: string;
  total_pages: number;
  total_chars: number;
  total_chunks: number;
  theme_id?: string;
  theme_name?: string;
  created_at?: string;
  document_summary?: string;
  document_type?: string;
  main_topics?: string[];
  suggested_questions?: string[];
  summary_limitations?: string[];
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
  const response = await fetch(createApiUrl("/documents"), {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Erro ao buscar documentos.");
  }

  return response.json();
}

export async function deleteDocument(
  documentId: string,
): Promise<DeleteDocumentResponse> {
  const response = await fetch(
    createApiUrl(`/documents/${documentId}`),
    getAdminRequestInit({
      method: "DELETE",
    }),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Erro ao apagar documento."));
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
  const response = await fetch(createApiUrl("/chat/ask"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: params.documentId,
      question: params.question,
      k: params.k ?? 4,
    }),
  });

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Erro ao enviar pergunta."),
    );
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
  payload: Record<string, JsonValue>;
  partial_result?: Record<string, JsonValue> | null;
  result?: {
    document?: DocumentItem;
    retrieval_backend?: string;
    total_enriched_chunks?: number;
    total_embeddings?: number;
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

export type UsageLog = {
  id: string;
  project: string;
  event_type: string;
  ip_address: string | null;
  user_id: string | null;
  document_id: string | null;
  metadata: Record<string, JsonValue>;
  created_at: string;
};

export type UsageLogsResponse = {
  total: number;
  logs: UsageLog[];
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
  const response = await fetch(createApiUrl("/themes"));

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

  const response = await fetch(
    createApiUrl("/documents/smart-ingest/start"),
    getAdminRequestInit({
      method: "POST",
      body: formData,
    }),
  );

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(
        response,
        "Erro ao iniciar processamento inteligente.",
      ),
    );
  }

  return response.json();
}

export async function getProcessingJobs(): Promise<ProcessingJobsResponse> {
  const response = await fetch(
    createApiUrl("/processing-jobs"),
    getAdminRequestInit(),
  );

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Erro ao buscar jobs de processamento."),
    );
  }

  return response.json();
}

export async function getProcessingJob(jobId: string): Promise<ProcessingJob> {
  const response = await fetch(
    createApiUrl(`/processing-jobs/${jobId}`),
    getAdminRequestInit(),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Erro ao buscar status do job."));
  }

  return response.json();
}

export async function getUsageLogs(limit = 50): Promise<UsageLogsResponse> {
  const response = await fetch(
    createApiUrl(`/usage-logs?limit=${limit}`),
    getAdminRequestInit({
      cache: "no-store",
    }),
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Erro ao buscar logs de uso."));
  }

  return response.json();
}
