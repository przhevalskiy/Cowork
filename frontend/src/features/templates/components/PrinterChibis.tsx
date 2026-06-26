import chibis from '@/assets/chibis.png';
import './PrinterChibis.css';

// Sprite sheet is 4 cols × 4 rows (same mapping as ChibiAvatars).
function spritePos(col: number, row: number) {
  const x = col === 0 ? '0%' : col === 3 ? '100%' : `${(col / 3) * 100}%`;
  const y = row === 0 ? '0%' : row === 3 ? '100%' : `${(row / 3) * 100}%`;
  return `${x} ${y}`;
}

/** A chibi by a copy machine printing template pages — a friendly empty-state scene. */
export function PrinterChibis() {
  return (
    <div className="pc-scene" aria-hidden="true">
      {/* Chibi watching the printer */}
      <div className="pc-chibi">
        <span className="pc-bubble"><span /><span /><span /></span>
        <span
          className="pc-face"
          style={{ backgroundImage: `url(${chibis})`, backgroundPosition: spritePos(2, 0) }}
        />
      </div>

      {/* Copy machine printing template pages */}
      <div className="pc-printer">
        <span className="pc-sheet pc-sheet-1">
          <i /><i /><i />
        </span>
        <span className="pc-sheet pc-sheet-2">
          <i /><i /><i />
        </span>
        <span className="pc-top" />
        <span className="pc-body">
          <span className="pc-led" />
          <span className="pc-slot" />
        </span>
      </div>
    </div>
  );
}
