"use client";

import { FormEvent, useMemo, useState } from "react";

type UploadResult = {
  status: string;
  dataset?: {
    dataset_id: string;
    original_name: string;
    sha256: string;
    archive_bytes: number;
    assets: Array<{
      path: string;
      size_bytes: number;
      extension: string;
      rows?: number | null;
      columns?: string[] | null;
    }>;
  };
  detail?: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function UrbanLabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sizeLabel = useMemo(() => {
    if (!file) return "";
    return `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  }, [file]);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_URL}/v1/datasets/upload`, {
        method: "POST",
        body: form,
      });
      const payload = (await response.json()) as UploadResult;
      if (!response.ok) throw new Error(payload.detail ?? "No se pudo procesar el ZIP");
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">URBAN</div>
        <nav>
          <a className="active" href="#ingesta">Ingesta</a>
          <a href="#datos">Datos</a>
          <a href="#territorio">Territorio</a>
          <a href="#modelos">Modelos</a>
          <a href="#corridas">Corridas</a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Urban Data Science Workspace</p>
            <h1>Ingesta y laboratorio econométrico</h1>
          </div>
          <span className="env">development</span>
        </header>

        <div className="grid" id="ingesta">
          <section className="panel upload-panel">
            <div className="panel-heading">
              <div>
                <span className="step">01</span>
                <h2>Subir dataset inmobiliario</h2>
              </div>
              <span className="status-dot">ZIP</span>
            </div>
            <p className="muted">
              El archivo se registra con hash, manifiesto y perfil de variables antes de entrar al esquema analítico.
            </p>
            <form onSubmit={upload}>
              <label className="dropzone">
                <input
                  type="file"
                  accept=".zip,application/zip"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <strong>{file ? file.name : "Selecciona el ZIP inmobiliario"}</strong>
                <span>{file ? sizeLabel : "CSV, Parquet, GeoJSON, GPKG, SHP o XLSX dentro del ZIP"}</span>
              </label>
              <button type="submit" disabled={!file || loading}>
                {loading ? "Validando…" : "Ingerir y perfilar"}
              </button>
            </form>
            {error && <div className="alert error">{error}</div>}
          </section>

          <section className="panel" id="datos">
            <div className="panel-heading">
              <div>
                <span className="step">02</span>
                <h2>Control de datos</h2>
              </div>
            </div>
            {!result?.dataset ? (
              <p className="empty">Aún no hay una ingesta activa en esta sesión.</p>
            ) : (
              <div className="dataset-summary">
                <dl>
                  <div><dt>ID</dt><dd>{result.dataset.dataset_id}</dd></div>
                  <div><dt>Archivo</dt><dd>{result.dataset.original_name}</dd></div>
                  <div><dt>Activos</dt><dd>{result.dataset.assets.length}</dd></div>
                  <div><dt>SHA-256</dt><dd className="mono">{result.dataset.sha256.slice(0, 20)}…</dd></div>
                </dl>
              </div>
            )}
          </section>
        </div>

        <section className="panel" id="modelos">
          <div className="panel-heading">
            <div>
              <span className="step">03</span>
              <h2>Pipeline analítico</h2>
            </div>
          </div>
          <div className="pipeline">
            {[
              ["Validación", "tipos, nulos, duplicados, coordenadas"],
              ["Normalización", "esquema canónico, geocodificación, precios/m²"],
              ["Territorio", "AGEB, manzana, colonia, grids, accesibilidad"],
              ["Econometría", "OLS robusto, panel FE, Moran, SAR"],
              ["ML", "validación geográfica, RF y comparación OOS"],
            ].map(([title, subtitle], index) => (
              <div className="pipeline-node" key={title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{title}</strong>
                <small>{subtitle}</small>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
