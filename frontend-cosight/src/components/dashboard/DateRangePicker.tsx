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
  /** Days to subtract from today for the latest selectable end date (default: 1). */
  endLagDays?: number;
}

function daysAgo(n: number, endLagDays = 1): DateRange {
  const end = new Date();
  end.setDate(end.getDate() - endLagDays);
  const start = new Date(end);
  start.setDate(start.getDate() - (n - 1));
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

const PRESETS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

export const DateRangePicker: React.FC<Props> = ({ value, onChange, endLagDays = 1 }) => {
  const [custom, setCustom] = useState(false);
  const maxEnd = (() => {
    const end = new Date();
    end.setDate(end.getDate() - endLagDays);
    return end.toISOString().split('T')[0];
  })();

  return (
    <div className="date-range-picker">
      {PRESETS.map(p => (
        <button
          key={p.label}
          className="drp-preset"
          onClick={() => { onChange(daysAgo(p.days, endLagDays)); setCustom(false); }}
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
          <input type="date" value={value.end} min={value.start} max={maxEnd}
            onChange={e => onChange({ ...value, end: e.target.value > maxEnd ? maxEnd : e.target.value })} />
        </div>
      )}
      <span className="drp-current">{value.start} → {value.end}</span>
    </div>
  );
};
