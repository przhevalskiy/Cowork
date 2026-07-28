/**
 * ChibiAvatars — same sprite sheet as Cowork, same animation.
 * Used on the CoSight overview empty state and chat empty state.
 */
import './ChibiAvatars.css';

// Sprite sheet is 4 cols × 4 rows — same positions as Cowork
const AVATARS = [
  { label: 'Analytics',    col: 2, row: 0 },
  { label: 'Search',       col: 1, row: 1 },
  { label: 'Web',          col: 0, row: 0 },
  { label: 'Social',       col: 0, row: 1 },
  { label: 'Email',        col: 3, row: 3 },
  { label: 'Reports',      col: 1, row: 0 },
  { label: 'Insights',     col: 2, row: 1 },
];

function spritePos(col: number, row: number) {
  const x = col === 0 ? '0%' : col === 3 ? '100%' : `${(col / 3) * 100}%`;
  const y = row === 0 ? '0%' : row === 3 ? '100%' : `${(row / 3) * 100}%`;
  return `${x} ${y}`;
}

export function ChibiAvatars({ count }: { count?: number } = {}) {
  const list = count != null ? AVATARS.slice(0, count) : AVATARS;
  return (
    <div className="chibi-avatars">
      {list.map((avatar, i) => (
        <div
          key={avatar.label}
          className="chibi-avatar"
          title={avatar.label}
          style={{
            backgroundImage: `url(/chibis.png)`,
            backgroundPosition: spritePos(avatar.col, avatar.row),
            '--i': i,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
