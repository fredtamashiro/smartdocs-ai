const API_URL =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

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
