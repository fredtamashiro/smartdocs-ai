import { fetchDocuments } from "@/services/api";

export default async function Home() {
  const data = await fetchDocuments();

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <div className="mx-auto max-w-5xl">
        <header className="mb-10">
          <h1 className="text-3xl font-bold tracking-tight">AutoManual AI</h1>
          <p className="mt-2 text-slate-400">
            Assistente inteligente para consulta de manuais automotivos.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
          <div className="mb-6">
            <h2 className="text-xl font-semibold">Manuais cadastrados</h2>
            <p className="text-sm text-slate-400">
              Total de documentos: {data.total}
            </p>
          </div>

          {data.documents.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
              Nenhum manual cadastrado ainda.
            </div>
          ) : (
            <div className="grid gap-4">
              {data.documents.map((document) => (
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
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
