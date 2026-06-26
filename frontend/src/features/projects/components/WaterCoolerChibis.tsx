import chibis from '@/assets/chibis.png';
import './WaterCoolerChibis.css';

// Sprite sheet is 4 cols × 4 rows (same mapping as ChibiAvatars).
function spritePos(col: number, row: number) {
  const x = col === 0 ? '0%' : col === 3 ? '100%' : `${(col / 3) * 100}%`;
  const y = row === 0 ? '0%' : row === 3 ? '100%' : `${(row / 3) * 100}%`;
  return `${x} ${y}`;
}

/** Two chibis chatting by a water cooler — a friendly empty-state scene. */
export function WaterCoolerChibis() {
  return (
    <div className="wc-scene" aria-hidden="true">
      {/* Speech bubble (left chibi is talking) */}
      <div className="wc-bubble">
        <span /><span /><span />
      </div>

      {/* Left chibi — faces right toward the cooler */}
      <div className="wc-chibi wc-chibi-left">
        <span
          className="wc-face"
          style={{ backgroundImage: `url(${chibis})`, backgroundPosition: spritePos(0, 0) }}
        />
      </div>

      {/* Water cooler */}
      <div className="wc-cooler">
        <span className="wc-bottle" />
        <span className="wc-body" />
      </div>

      {/* Right chibi — faces left toward the cooler */}
      <div className="wc-chibi wc-chibi-right">
        <span
          className="wc-face wc-face-flip"
          style={{ backgroundImage: `url(${chibis})`, backgroundPosition: spritePos(1, 1) }}
        />
      </div>
    </div>
  );
}
