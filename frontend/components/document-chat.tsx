"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { normalizeUtf8Text } from "@/lib/text";
import { askQuestion, ChatResponse } from "@/services/api";

type DocumentChatProps = {
  documentId: string;
  initialQuestion?: string;
  initialQuestionRequestId?: number;
};

type ChatMessage = ChatResponse & {
  id: string;
};

export function DocumentChat({
  documentId,
  initialQuestion,
  initialQuestionRequestId,
}: DocumentChatProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const lastInitialQuestionRequestId = useRef<number | undefined>(undefined);

  const submitQuestion = useCallback(
    async (questionToSubmit: string) => {
      const trimmedQuestion = questionToSubmit.trim();

      if (!trimmedQuestion) {
        setErrorMessage("Digite uma pergunta.");
        return;
      }

      try {
        setIsLoading(true);
        setErrorMessage("");

        const result = await askQuestion({
          documentId,
          question: trimmedQuestion,
          k: 4,
        });

        setMessages((currentMessages) => [
          {
            ...result,
            id: crypto.randomUUID(),
          },
          ...currentMessages,
        ]);

        setQuestion("");
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Não foi possível obter uma resposta.",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [documentId],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitQuestion(question);
  }

  useEffect(() => {
    if (!initialQuestion || initialQuestionRequestId === undefined) {
      return;
    }

    if (lastInitialQuestionRequestId.current === initialQuestionRequestId) {
      return;
    }

    lastInitialQuestionRequestId.current = initialQuestionRequestId;
    setQuestion(initialQuestion);
    void submitQuestion(initialQuestion);
  }, [initialQuestion, initialQuestionRequestId, submitQuestion]);

  return (
    <div className="mt-5 rounded-xl border border-blue-100 bg-white p-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 md:flex-row">
        <Input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Digite sua pergunta sobre este documento"
          className="min-h-11 flex-1"
        />

        <Button type="submit" disabled={isLoading}>
          {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
          {isLoading ? "Perguntando..." : "Perguntar"}
        </Button>
      </form>

      {errorMessage && (
        <p className="mt-3 text-sm text-red-700">{errorMessage}</p>
      )}

      {messages.length > 0 && (
        <div className="mt-5 space-y-5">
          {messages.map((message) => (
            <div key={message.id} className="space-y-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Pergunta
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {normalizeUtf8Text(message.question)}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Resposta
                </p>
                <div className="mt-2 text-sm leading-6 text-slate-700">
                  <ReactMarkdown
                    components={{
                      h1: ({ children }) => (
                        <h1 className="mb-2 mt-4 text-lg font-semibold text-slate-950">
                          {children}
                        </h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="mb-2 mt-4 text-base font-semibold text-slate-950">
                          {children}
                        </h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="mb-2 mt-4 text-sm font-semibold text-slate-950">
                          {children}
                        </h3>
                      ),
                      p: ({ children }) => (
                        <p className="mb-3 last:mb-0">{children}</p>
                      ),
                      ul: ({ children }) => (
                        <ul className="mb-3 list-outside list-disc space-y-1 pl-5 marker:text-slate-500">
                          {children}
                        </ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="mb-3 list-outside list-decimal space-y-1 pl-5 marker:text-slate-500">
                          {children}
                        </ol>
                      ),
                      li: ({ children }) => (
                        <li className="pl-1 [&>p]:mb-1 [&>p]:inline">
                          {children}
                        </li>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-slate-950">
                          {children}
                        </strong>
                      ),
                    }}
                  >
                    {normalizeUtf8Text(message.answer)}
                  </ReactMarkdown>
                </div>
              </div>

              {message.sources.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    Fontes
                  </p>

                  <div className="mt-3 space-y-3">
                    {message.sources.map((source, index) => (
                      <div
                        key={`${source.page}-${source.chunk_index}-${index}`}
                        className="rounded-lg border border-slate-200 bg-white p-3"
                      >
                        <div className="mb-2 flex flex-wrap gap-3 text-xs text-slate-500">
                          <span>Página: {source.page}</span>
                          <span>Chunk: {source.chunk_index}</span>
                          <span>Score: {source.score.toFixed(4)}</span>

                          {source.relevance_score !== undefined && (
                            <span>
                              Relevância: {source.relevance_score.toFixed(2)}
                            </span>
                          )}
                        </div>

                        {source.matched_query && (
                          <p className="mb-2 text-xs text-blue-700">
                            Query usada: {normalizeUtf8Text(source.matched_query)}
                          </p>
                        )}

                        {source.relevance_reason && (
                          <p className="mb-2 text-xs leading-5 text-emerald-700">
                            Motivo da relevância:{" "}
                            {normalizeUtf8Text(source.relevance_reason)}
                          </p>
                        )}

                        <p className="text-xs leading-5 text-slate-600">
                          {normalizeUtf8Text(source.preview)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

