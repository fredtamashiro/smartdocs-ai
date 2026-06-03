"use client";

import { useEffect, useState } from "react";

import { DocumentChat } from "@/components/document-chat";
import { DocumentUpload } from "@/components/document-upload";
import { SmartDocumentUpload } from "@/components/smart-document-upload";
import { DocumentItem, deleteDocument, fetchDocuments } from "@/services/api";

export function DocumentsPanel() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadDocuments() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const data = await fetchDocuments();
      setDocuments(data.documents);
    } catch {
      setErrorMessage("Não foi possível carregar os documentos.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchDocuments()
      .then((data) => {
        setDocuments(data.documents);
      })
      .catch(() => {
        setErrorMessage("Não foi possível carregar os documentos.");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  async function handleDeleteDocument(documentId: string) {
    const confirmed = window.confirm(
      "Tem certeza que deseja apagar este documento?",
    );

    if (!confirmed) {
      return;
    }

    try {
      await deleteDocument(documentId);
      await loadDocuments();
    } catch {
      setErrorMessage("Não foi possível apagar o documento.");
    }
  }

  return (
    <>
      <SmartDocumentUpload onCompleted={loadDocuments} />
      <DocumentUpload onUploadSuccess={loadDocuments} />

      <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
        <div className="mb-6">
          <h2 className="text-xl font-semibold">Manuais cadastrados</h2>
          <p className="text-sm text-slate-400">
            Total de documentos: {documents.length}
          </p>
        </div>

        {isLoading && (
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
            Carregando documentos...
          </div>
        )}

        {errorMessage && (
          <div className="rounded-xl border border-red-900 bg-red-950/40 p-8 text-center text-red-300">
            {errorMessage}
          </div>
        )}

        {!isLoading && !errorMessage && documents.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
            Nenhum manual cadastrado ainda.
          </div>
        )}

        {!isLoading && !errorMessage && documents.length > 0 && (
          <div className="grid gap-4">
            {documents.map((document) => (
              <article
                key={document.document_id}
                className="rounded-xl border border-slate-800 bg-slate-950 p-5"
              >
                <h3 className="font-medium text-slate-100">
                  {document.original_filename}
                </h3>

                <div className="mt-3 grid gap-2 text-sm text-slate-400 md:grid-cols-3">
                  <p>
                    <span className="text-slate-500">Páginas:</span>{" "}
                    {document.total_pages}
                  </p>
                  <p>
                    <span className="text-slate-500">Chunks:</span>{" "}
                    {document.total_chunks}
                  </p>
                  <p>
                    <span className="text-slate-500">Criado em:</span>{" "}
                    {new Date(document.created_at).toLocaleString("pt-BR")}
                  </p>
                </div>

                <p className="mt-3 break-all text-xs text-slate-600">
                  ID: {document.document_id}
                </p>

                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={() => handleDeleteDocument(document.document_id)}
                    className="rounded-lg border border-red-900/60 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-950/40"
                  >
                    Apagar
                  </button>
                </div>

                <DocumentChat documentId={document.document_id} />
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
