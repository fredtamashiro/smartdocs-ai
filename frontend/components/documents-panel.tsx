"use client";

import { useEffect, useState } from "react";
import { FileText, MessageCircle, Plus, Trash2 } from "lucide-react";

import { DocumentChat } from "@/components/document-chat";
import { SmartDocumentUpload } from "@/components/smart-document-upload";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AuthUser,
  DocumentItem,
  deleteDocument,
  fetchDocuments,
} from "@/services/api";

type SelectedQuestion = {
  question: string;
  requestId: number;
};

type DocumentsPanelProps = {
  adminUser: AuthUser | null;
};

export function DocumentsPanel({ adminUser }: DocumentsPanelProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [activeChatDocumentId, setActiveChatDocumentId] = useState<string | null>(
    null,
  );
  const [selectedQuestionsByDocument, setSelectedQuestionsByDocument] =
    useState<Record<string, SelectedQuestion>>({});

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

  function handleSuggestedQuestionClick(
    documentId: string,
    suggestedQuestion: string,
  ) {
    setActiveChatDocumentId(documentId);
    setSelectedQuestionsByDocument((currentQuestions) => ({
      ...currentQuestions,
      [documentId]: {
        question: suggestedQuestion,
        requestId: (currentQuestions[documentId]?.requestId ?? 0) + 1,
      },
    }));
  }

  return (
    <>
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-950">
            SmartDocs IA
          </h1>
          <p className="mt-2 text-slate-600">
            Assistente inteligente para consulta de documentos em PDF.
          </p>
        </div>

        {adminUser && (
          <Button type="button" onClick={() => setIsImportOpen(true)}>
            <Plus className="h-4 w-4" />
            Importar documento
          </Button>
        )}
      </header>

      {adminUser && (
        <SmartDocumentUpload
          isOpen={adminUser ? isImportOpen : false}
          onOpenChange={setIsImportOpen}
          onCompleted={loadDocuments}
        />
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-slate-950">
            Documentos cadastrados
          </h2>
          <p className="text-sm text-slate-500">
            Total de documentos: {documents.length}
          </p>
        </div>

        {isLoading && (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">
            Carregando documentos...
          </div>
        )}

        {errorMessage && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-red-700">
            {errorMessage}
          </div>
        )}

        {!isLoading && !errorMessage && documents.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">
            Nenhum documento cadastrado ainda.
          </div>
        )}

        {!isLoading && !errorMessage && documents.length > 0 && (
          <div className="grid gap-4">
            {documents.map((document) => (
              <article
                key={document.document_id}
                className="rounded-xl border border-slate-200 bg-slate-50 p-5"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="flex items-center gap-2 font-semibold text-slate-950">
                      <FileText className="h-4 w-4 text-blue-600" />
                      {document.original_filename}
                    </h3>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {document.document_type && (
                        <Badge className="border-blue-200 bg-blue-50 text-blue-700">
                          {document.document_type}
                        </Badge>
                      )}

                      {document.theme_name && <Badge>{document.theme_name}</Badge>}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setActiveChatDocumentId((currentDocumentId) =>
                          currentDocumentId === document.document_id
                            ? null
                            : document.document_id,
                        )
                      }
                    >
                      <MessageCircle className="h-3.5 w-3.5" />
                      Conversar
                    </Button>

                    {adminUser && (
                      <Button
                        type="button"
                        onClick={() => handleDeleteDocument(document.document_id)}
                        variant="destructive"
                        size="sm"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Apagar
                      </Button>
                    )}
                  </div>
                </div>

                <div className="mt-4 grid gap-2 text-sm text-slate-600 md:grid-cols-3">
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
                    {document.created_at
                      ? new Date(document.created_at).toLocaleString("pt-BR")
                      : "-"}
                  </p>
                </div>

                {document.document_summary && (
                  <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Resumo automático
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {document.document_summary}
                    </p>
                  </div>
                )}

                {document.main_topics && document.main_topics.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Tópicos principais
                    </p>

                    <div className="mt-2 flex flex-wrap gap-2">
                      {document.main_topics.map((topic) => (
                        <Badge key={topic}>{topic}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {document.suggested_questions &&
                  document.suggested_questions.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        Perguntas sugeridas
                      </p>

                      <div className="mt-2 space-y-2">
                        {document.suggested_questions.map((suggestedQuestion) => (
                          <button
                            key={suggestedQuestion}
                            type="button"
                            onClick={() =>
                              handleSuggestedQuestionClick(
                                document.document_id,
                                suggestedQuestion,
                              )
                            }
                            className="block w-full rounded-lg border border-slate-200 bg-white p-3 text-left text-sm text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
                          >
                            {suggestedQuestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                {document.summary_limitations &&
                  document.summary_limitations.length > 0 && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-amber-700">
                        Limitações identificadas
                      </p>

                      <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-5 text-amber-800">
                        {document.summary_limitations.map((limitation) => (
                          <li key={limitation}>{limitation}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                <p className="mt-3 break-all text-xs text-slate-400">
                  ID: {document.document_id}
                </p>

                {activeChatDocumentId === document.document_id && (
                  <DocumentChat
                    documentId={document.document_id}
                    initialQuestion={
                      selectedQuestionsByDocument[document.document_id]?.question
                    }
                    initialQuestionRequestId={
                      selectedQuestionsByDocument[document.document_id]?.requestId
                    }
                  />
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
