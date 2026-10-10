import { useCallback, useEffect, useRef, useState } from 'react';

const TICK_MS = 16;
const BASE_STEP = 2;
const CATCHUP_THRESHOLD = 48;
const CATCHUP_STEP = 10;

/**
 * Buffers incoming SSE chunks and reveals text at a steady pace so large
 * network bursts feel like a continuous typewriter flow.
 */
export function useSmoothStream(onDrain?: () => void) {
  const [text, setText] = useState('');
  const bufferRef = useRef('');
  const indexRef = useRef(0);
  const doneRef = useRef(false);
  const drainedRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const onDrainRef = useRef(onDrain);
  onDrainRef.current = onDrain;

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const maybeDrain = useCallback(() => {
    if (drainedRef.current || !doneRef.current) return;
    if (indexRef.current < bufferRef.current.length) return;
    drainedRef.current = true;
    stop();
    onDrainRef.current?.();
  }, [stop]);

  const tick = useCallback(() => {
    const buf = bufferRef.current;
    let i = indexRef.current;

    if (i >= buf.length) {
      maybeDrain();
      return;
    }

    const backlog = buf.length - i;
    let step = BASE_STEP;

    if (backlog > CATCHUP_THRESHOLD) {
      step = Math.min(CATCHUP_STEP, backlog);
    } else {
      const window = buf.slice(i, i + 28);
      const spaceIdx = window.indexOf(' ');
      if (spaceIdx > 0 && spaceIdx <= step + 3) {
        step = spaceIdx + 1;
      }
    }

    i = Math.min(i + step, buf.length);
    indexRef.current = i;
    setText(buf.slice(0, i));
    maybeDrain();
  }, [maybeDrain]);

  const start = useCallback(() => {
    if (timerRef.current !== null) return;
    timerRef.current = window.setInterval(tick, TICK_MS);
  }, [tick]);

  const append = useCallback((chunk: string) => {
    if (!chunk) return;
    bufferRef.current += chunk;
    start();
  }, [start]);

  const finish = useCallback(() => {
    doneRef.current = true;
    if (indexRef.current >= bufferRef.current.length) {
      setText(bufferRef.current);
      maybeDrain();
    } else {
      start();
    }
  }, [maybeDrain, start]);

  const reset = useCallback(() => {
    stop();
    bufferRef.current = '';
    indexRef.current = 0;
    doneRef.current = false;
    drainedRef.current = false;
    setText('');
  }, [stop]);

  useEffect(() => () => stop(), [stop]);

  return { text, append, finish, reset, isDraining: doneRef.current && !drainedRef.current };
}
