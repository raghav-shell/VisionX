"use client";

import type { EvidenceRecord } from "./workspace-data";

type Scalar = string | number | boolean | null;

const isScalar = (value: unknown): value is Scalar =>
  value === null || ["string", "number", "boolean"].includes(typeof value);

function formatScalar(value: Scalar): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return value === null ? "-" : String(value);
}

/** A confusion matrix or any other table shaped as { columns: string[], rows: unknown[][] }. */
function asTable(data: Record<string, unknown>): { columns: string[]; rows: Scalar[][] } | null {
  const { columns, rows } = data;
  if (!Array.isArray(columns) || !Array.isArray(rows) || !rows.length) return null;
  if (!columns.every(item => typeof item === "string")) return null;
  if (!rows.every(row => Array.isArray(row) && row.every(isScalar))) return null;
  return { columns: columns as string[], rows: rows as Scalar[][] };
}

function EvidenceTable({ columns, rows }: { columns: string[]; rows: Scalar[][] }) {
  // In a confusion matrix, a non-zero count where a row's class meets a different class column is the evidence.
  const classes = new Set(rows.map(row => String(row[0])));
  const confusion = (row: Scalar[], cellIndex: number) => typeof row[cellIndex] === "number" && (row[cellIndex] as number) > 0 && classes.has(columns[cellIndex]) && columns[cellIndex] !== String(row[0]);
  return (
    <div className="vx-evidence-table-wrap">
      <table className="vx-evidence-table">
        <thead><tr>{columns.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={index}>{row.map((cell, cellIndex) => cellIndex === 0
            ? <th key={cellIndex} scope="row">{formatScalar(cell)}</th>
            : <td key={cellIndex} data-zero={cell === 0 || undefined} data-confusion={confusion(row, cellIndex) || undefined}>{formatScalar(cell)}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function EvidenceFacts({ data }: { data: Record<string, unknown> }) {
  const flat = Object.entries(data).filter(([, value]) => isScalar(value)) as [string, Scalar][];
  const nested = Object.fromEntries(Object.entries(data).filter(([, value]) => !isScalar(value)));
  return (
    <>
      {flat.length > 0 && <dl className="vx-evidence-facts">{flat.map(([key, value]) => (
        <div key={key}><dt>{key.replace(/_/g, " ")}</dt><dd>{formatScalar(value)}</dd></div>
      ))}</dl>}
      {Object.keys(nested).length > 0 && (
        <details className="vx-evidence-raw"><summary>Supporting data</summary><pre>{JSON.stringify(nested, null, 2)}</pre></details>
      )}
    </>
  );
}

/**
 * The body of one evidence record in the inspector. Image evidence is shown as the image itself,
 * fetched from the local evidence store (which verifies its SHA-256 on read); tables render as
 * tables, flat statistics as labelled values, anything else as JSON.
 */
export function EvidenceBody({ item, canFetchBlobs }: { item: EvidenceRecord; canFetchBlobs: boolean }) {
  const image = item.blob && item.blob.media_type.startsWith("image/") && canFetchBlobs ? item.blob : null;
  const table = item.data ? asTable(item.data) : null;
  return (
    <>
      {image && (
        <a className="vx-evidence-image" href={`/api/evidence/${encodeURIComponent(image.digest)}/raw`} target="_blank" rel="noreferrer">
          {/* eslint-disable-next-line @next/next/no-img-element -- served by the local API, not a Next static asset */}
          <img src={`/api/evidence/${encodeURIComponent(image.digest)}/raw`} alt={item.title} loading="lazy" />
        </a>
      )}
      {table ? <EvidenceTable {...table} /> : item.data ? (image
        ? <details className="vx-evidence-raw"><summary>Supporting data</summary><pre>{JSON.stringify(item.data, null, 2)}</pre></details>
        : <EvidenceFacts data={item.data} />) : null}
    </>
  );
}
