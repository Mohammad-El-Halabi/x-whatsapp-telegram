'use client';

import { getCurrentWindow } from '@tauri-apps/api/window';

export default function TitleBar() {
  const appWindow = getCurrentWindow();

  return (
    <div className="flex justify-between items-center h-8 bg-bg-secondary border-b border-border select-none title-bar-drag">
      <div className="flex items-center pl-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" fill="#25D366"/>
            <path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.37 0-4.567-.82-6.293-2.192l-.44-.36-2.893.967.967-2.893-.36-.44A9.935 9.935 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z" fill="#25D366"/>
          </svg>
          <span>X-WhatsApp</span>
        </div>
      </div>
      <div className="flex title-bar-controls">
        <button onClick={() => appWindow.minimize()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-bg-hover hover:text-text-primary transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect y="5" width="12" height="1" fill="currentColor"/></svg>
        </button>
        <button onClick={() => appWindow.toggleMaximize()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-bg-hover hover:text-text-primary transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="10" height="10" stroke="currentColor" strokeWidth="1" fill="none"/></svg>
        </button>
        <button onClick={() => appWindow.close()} className="w-[46px] h-8 border-none bg-transparent text-text-secondary cursor-pointer flex items-center justify-center hover:bg-danger hover:text-white transition-all">
          <svg width="12" height="12" viewBox="0 0 12 12"><path d="M1 1L11 11M11 1L1 11" stroke="currentColor" strokeWidth="1.5"/></svg>
        </button>
      </div>
    </div>
  );
}
