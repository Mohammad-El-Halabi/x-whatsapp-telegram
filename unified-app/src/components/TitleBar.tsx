'use client';

import { getCurrentWindow } from '@tauri-apps/api/window';

export default function TitleBar() {
  const isTauri = Boolean((window as any).__TAURI_INTERNALS__);
  const appWindow = isTauri ? getCurrentWindow() : null;

  return (
    <div className="flex justify-between items-center h-8 bg-bg-secondary border-b border-border select-none title-bar-drag">
      <div className="flex items-center pl-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
          <span className="brand-cluster small" aria-hidden="true"><i>T</i><i>W</i></span>
          <span>Staff Communications Control</span>
        </div>
      </div>
      {appWindow && <div className="flex title-bar-controls">
        <button onClick={() => appWindow.minimize()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-bg-hover hover:text-text-primary transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect y="5" width="12" height="1" fill="currentColor"/></svg>
        </button>
        <button onClick={() => appWindow.toggleMaximize()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-bg-hover hover:text-text-primary transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="10" height="10" stroke="currentColor" strokeWidth="1" fill="none"/></svg>
        </button>
        <button onClick={() => appWindow.close()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-danger hover:text-white transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><path d="M1 1L11 11M11 1L1 11" stroke="currentColor" strokeWidth="1.5"/></svg>
        </button>
      </div>}
    </div>
  );
}
