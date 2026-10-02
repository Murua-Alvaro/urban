"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./denue.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Municipality = {
  municipality_code: string;
  name: string;
  latitude: number | null;
  longitude: number | null;
  editions: string[];
};

type Edition = {
  source_edition: string;
  edition_date: string;
  is_rebenchmark: boolean;
};

type Observation = {
  source_edition: string;
  edition_date: string;
  is_rebenchmark: boolean;
  establishments: number;
  active_agebs: number;
  active_grids: number;
};

type Sector = {
  sector: string;
  establishments: number;
  municipality_share: number;
  state_share: number;
  lq_state: number;
};

type GridFeature = {
  id: string;
  properties: {
    grid_id: string;
    establishments: number;
    sector_count: number;
    scian6_count: number;
    phone_share: number | null;
    email_share: number | null;
    web_share: number | null;
  };
};

function formatInt(value?: number) {
  return new Intl.NumberFormat("es-MX").format(value ?? 0);
}

function formatPct(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("es-MX", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

function Sparkline({ data }: { data: Observation[] }) {
  if (data.length < 2) return <div className={styles.chartEmpty}>Serie insuficiente</div>;
  const width = 760;
  const height = 210;
  const pad = 18;
  const values = data.map((d) => d.establishments);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const points = data
    .map((d, index) => {
      const x = pad + (index / (data.length - 1)) * (width - pad * 2);
      const y = height - pad - ((d.establishments - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Serie histórica DENUE">
      <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} className={styles.axis} />
      <polyline points={points} className={styles.line} />
      {data.map((d, index) => {
        const x = pad + (index / (data.length - 1)) * (width - pad * 2);
        const y = height - pad - ((d.establishments - min) / span) * (height - pad * 2);
        return <circle key={d.source_edition} cx={x} cy={y} r={d.is_rebenchmark ? 4.2 : 2.7} className={d.is_rebenchmark ? styles.breakPoint : styles.point} />;
      })}
    </svg>
  );
}

export default function DenuePage() {
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [editions, setEditions] = useState<Edition[]>([]);
  const [municipality, setMunicipality] = useState("25_012");
  const [edition, setEdition] = useState("2026-05");
  const [series, setSeries] = useState<Observation[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [grids, setGrids] = useState<GridFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/v1/denue/municipalities`).then((r) => {
        if (!r.ok) throw new Error("No se pudo cargar el catálogo municipal");
        return r.json();
      }),
      fetch(`${API_URL}/v1/denue/editions`).then((r) => {
        if (!r.ok) throw new Error("No se pudieron cargar las ediciones DENUE");
        return r.json();
      }),
    ])
      .then(([m, e]) => {
        setMunicipalities(m.municipalities ?? []);
        setEditions(e.editions ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Error de API"));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`${API_URL}/v1/denue/municipalities/${municipality}/timeseries`),
      fetch(`${API_URL}/v1/denue/municipalities/${municipality}/sectors?edition=${encodeURIComponent(edition)}&limit=20`),
      fetch(`${API_URL}/v1/denue/municipalities/${municipality}/grids?edition=${encodeURIComponent(edition)}&min_establishments=1`),
    ])
      .then(async ([seriesResponse, sectorResponse, gridResponse]) => {
        if (!seriesResponse.ok || !sectorResponse.ok || !gridResponse.ok) {
          throw new Error("No hay información DENUE disponible para la selección");
        }
        const [seriesPayload, sectorPayload, gridPayload] = await Promise.all([
          seriesResponse.json(),
          sectorResponse.json(),
          gridResponse.json(),
        ]);
        setSeries(seriesPayload.observations ?? []);
        setSectors(sectorPayload.sectors ?? []);
        setGrids(gridPayload.features ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Error de API"))
      .finally(() => setLoading(false));
  }, [municipality, edition]);

  const selectedMunicipality = municipalities.find((m) => m.municipality_code === municipality);
  const availableEditions = selectedMunicipality?.editions?.length
    ? editions.filter((e) => selectedMunicipality.editions.includes(e.source_edition))
    : editions;

  useEffect(() => {
    if (availableEditions.length && !availableEditions.some((e) => e.source_edition === edition)) {
      setEdition(availableEditions[availableEditions.length - 1].source_edition);
    }
  }, [availableEditions, edition]);

  const current = series.find((row) => row.source_edition === edition) ?? series[series.length - 1];
  const first = series[0];
  const cumulativeGrowth = useMemo(() => {
    if (!first || !current || first.establishments <= 0) return null;
    return current.establishments / first.establishments - 1;
  }, [first, current]);
  const topGrids = useMemo(
    () => [...grids].sort((a, b) => b.properties.establishments - a.properties.establishments).slice(0, 10),
    [grids],
  );

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">URBAN</div>
        <nav>
          <a href="/">Ingesta</a>
          <a className="active" href="/denue">DENUE histórico</a>
          <a href="/#territorio">Territorio</a>
          <a href="/#modelos">Modelos</a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Urban · Territorial Intelligence</p>
            <h1>DENUE histórico</h1>
          </div>
          <span className="env">2010–2026</span>
        </header>

        <section className={`panel ${styles.controls}`}>
          <label>
            <span>Municipio</span>
            <select value={municipality} onChange={(e) => setMunicipality(e.target.value)}>
              {municipalities.map((item) => (
                <option key={item.municipality_code} value={item.municipality_code}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Edición DENUE</span>
            <select value={edition} onChange={(e) => setEdition(e.target.value)}>
              {availableEditions.map((item) => (
                <option key={item.source_edition} value={item.source_edition}>
                  {item.source_edition}{item.is_rebenchmark ? " · rebenchmark" : ""}
                </option>
              ))}
            </select>
          </label>
          <div className={styles.provenance}>
            <span>Fuente</span>
            <strong>DENUE derivado · archivo auditado por SHA-256</strong>
          </div>
        </section>

        {error && <div className="alert error">{error}</div>}
        {loading && <p className="empty">Consultando PostGIS…</p>}

        {!loading && current && (
          <>
            <section className={styles.kpis}>
              <article className="panel"><span>Establecimientos</span><strong>{formatInt(current.establishments)}</strong><small>{edition}</small></article>
              <article className="panel"><span>AGEB activas</span><strong>{formatInt(current.active_agebs)}</strong><small>con presencia empresarial</small></article>
              <article className="panel"><span>Cuadrículas activas</span><strong>{formatInt(current.active_grids)}</strong><small>malla territorial</small></article>
              <article className="panel"><span>Cambio desde {first?.source_edition}</span><strong>{formatPct(cumulativeGrowth)}</strong><small>stock registrado, no aperturas netas</small></article>
            </section>

            <section className={`panel ${styles.section}`}>
              <div className="panel-heading"><div><span className="step">01</span><h2>Serie histórica</h2></div></div>
              <p className="muted">Los puntos mayores marcan ediciones de rebenchmark censal; los saltos en esos cortes no deben interpretarse automáticamente como crecimiento empresarial.</p>
              <Sparkline data={series} />
              <div className={styles.timelineLabels}><span>{series[0]?.source_edition}</span><span>{series[series.length - 1]?.source_edition}</span></div>
            </section>

            <div className={styles.twoCols}>
              <section className={`panel ${styles.section}`}>
                <div className="panel-heading"><div><span className="step">02</span><h2>Estructura sectorial</h2></div></div>
                <div className={styles.tableWrap}>
                  <table>
                    <thead><tr><th>Sector</th><th>Est.</th><th>Participación</th><th>LQ estatal</th></tr></thead>
                    <tbody>
                      {sectors.map((row) => (
                        <tr key={row.sector}><td>{row.sector}</td><td>{formatInt(row.establishments)}</td><td>{formatPct(row.municipality_share)}</td><td>{row.lq_state?.toFixed(2) ?? "—"}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className={`panel ${styles.section}`}>
                <div className="panel-heading"><div><span className="step">03</span><h2>Cuadrículas con mayor stock</h2></div></div>
                <div className={styles.tableWrap}>
                  <table>
                    <thead><tr><th>Grid</th><th>Est.</th><th>Sectores</th><th>Web</th></tr></thead>
                    <tbody>
                      {topGrids.map((feature) => (
                        <tr key={feature.id}><td className="mono">{feature.properties.grid_id}</td><td>{formatInt(feature.properties.establishments)}</td><td>{feature.properties.sector_count}</td><td>{formatPct(feature.properties.web_share)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
