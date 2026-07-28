/**
 * CoSight glyph — minimal lens/aperture mark used as the assistant identity.
 * Three states: idle (steady), loading (animated pulse), done (steady bright).
 * Conveys analytical authority. Not a mascot.
 */
import React from 'react';
import './CoSightGlyph.css';

type GlyphState = 'idle' | 'loading' | 'done';

interface Props {
  state?: GlyphState;
  size?: number;
}

export const CoSightGlyph: React.FC<Props> = ({ state = 'idle', size = 28 }) => (
  <div
    className={`cs-glyph cs-glyph--${state}`}
    style={{ width: size, height: size }}
    title="CoSight"
  >
    <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Outer ring */}
      <circle cx="14" cy="14" r="12" stroke="currentColor" strokeWidth="1.5" />
      {/* Inner aperture blades */}
      <circle cx="14" cy="14" r="5" stroke="currentColor" strokeWidth="1.5" />
      {/* Sight crosshairs */}
      <line x1="14" y1="2" x2="14" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="14" y1="20" x2="14" y2="26" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2" y1="14" x2="8" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="20" y1="14" x2="26" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  </div>
);
