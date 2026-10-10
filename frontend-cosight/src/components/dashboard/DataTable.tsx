/**
 * DataTable — sortable, filterable, paginated table with CSV download.
 */
import React, { useState, useMemo } from 'react';
import { formatCount } from '../../utils/formatNumber';
import './DataTable.css';

interface Props {
  headers: string[];
  rows: Record<string, unknown>[];
  title?: string;
  csvUrl?: string;
  pageSize?: number;
}

export const DataTable: React.FC<Props> = ({ headers, rows, title, csvUrl, pageSize = 15 }) => {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!filter.trim()) return rows;
    const q = filter.toLowerCase();
    return rows.filter(row =>
      headers.some(h => String(row[h] ?? '').toLowerCase().includes(q))
    );
  }, [rows, headers, filter]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paginated = sorted.slice(page * pageSize, (page + 1) * pageSize);

  const formatCell = (key: string, value: unknown): React.ReactNode => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'number') return formatCount(value);
    if (key === 'link' && typeof value === 'string' && value.startsWith('http')) {
      return (
        <a href={value} target="_blank" rel="noopener noreferrer" className="data-table__link">
          View
        </a>
      );
    }
    return String(value);
  };

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
    setPage(0);
  };

  return (
    <div className="data-table">
      <div className="data-table__toolbar">
        {title && <span className="data-table__title">{title}</span>}
        <input
          className="data-table__filter"
          placeholder="Filter…"
          value={filter}
          onChange={e => { setFilter(e.target.value); setPage(0); }}
        />
        {csvUrl && (
          <a className="data-table__csv" href={csvUrl} download>
            ↓ CSV
          </a>
        )}
      </div>
      <div className="data-table__scroll">
        <table>
          <thead>
            <tr>
              {headers.map(h => (
                <th key={h} onClick={() => handleSort(h)} className={sortKey === h ? 'sorted' : ''}>
                  {h.replace(/_/g, ' ')}
                  {sortKey === h && <span>{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr><td colSpan={headers.length} className="empty">No data</td></tr>
            ) : (
              paginated.map((row, i) => (
                <tr key={i}>
                  {headers.map(h => (
                    <td key={h}>{formatCell(h, row[h])}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="data-table__pagination">
          <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>‹ Prev</button>
          <span>{page + 1} / {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next ›</button>
        </div>
      )}
    </div>
  );
};
