/**
 * DateRangePicker — presets 7d / 30d / 90d + custom input.
 * One source of truth for all queries on a page — passed down via the metrics store.
 */
import React, { useState } from 'react';
import type { DateRange } from '../../types';
import './DateRangePicker.css';

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

function daysAgo(n: number): DateRange {
  const end = new Date();
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - (n - 1));
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

const PRESETS = [
  { label: '7d', range: () => daysAgo(7) },
  { label: '30d', range: () => daysAgo(30) },
  { label: '90d', range: () => daysAgo(90) },
];

export const DateRangePicker: React.FC<Props> = ({ value, onChange }) => {
  const [custom, setCustom] = useState(false);

  return (
    <div className="date-range-picker">
      {PRESETS.map(p => (
        <button
          key={p.label}
          className="drp-preset"
          onClick={() => { onChange(p.range()); setCustom(false); }}
        >
          {p.label}
        </button>
      ))}
      <button className="drp-preset drp-custom-btn" onClick={() => setCustom(v => !v)}>
        Custom
      </button>
      {custom && (
        <div className="drp-custom">
          <input type="date" value={value.start} max={value.end}
            onChange={e => onChange({ ...value, start: e.target.value })} />
          <span>–</span>
          <input type="date" value={value.end} min={value.start}
            onChange={e => onChange({ ...value, end: e.target.value })} />
        </div>
      )}
      <span className="drp-current">{value.start} → {value.end}</span>
    </div>
  );
};
